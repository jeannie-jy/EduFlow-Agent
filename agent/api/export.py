"""导出 API 路由。

POST   /api/projects/{id}/export/manim          创建视频导出任务
GET    /api/export/{job_id}                     查询导出状态
GET    /api/export/{job_id}/download/{filename} 下载产物
"""

from __future__ import annotations

import asyncio
import os
import json
import logging
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import get_session
from schema.project import ExportManimRequest
from .deps import parse_project_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])

# Redis 客户端（延迟初始化，asyncio.Lock 保护）
_redis_client = None
_redis_lock = asyncio.Lock()


async def _get_redis():
    """获取 Redis 客户端（线程安全）。"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    async with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        try:
            import redis as redis_lib
            settings = get_settings()
            _redis_client = redis_lib.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            logger.warning("Redis 不可用")
            _redis_client = None
    return _redis_client


# ============================================================================
# 创建导出任务
# ============================================================================


@router.post("/projects/{project_id}/export/manim", status_code=201)
async def create_export_job(
    project_id: str,
    body: ExportManimRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """创建 Manim 视频导出任务。"""
    from db.models import Project, ExportJobModel

    pid = parse_project_id(project_id)
    project = await session.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.dsl_snapshot or not project.dsl_snapshot.get("frames"):
        raise HTTPException(status_code=400, detail="Project has no frames to export")

    job_id = uuid.uuid4()

    # 持久化到 DB
    export_job = ExportJobModel(
        id=job_id,
        project_id=pid,
        target="manim_video",
        status="queued",
        config={
            "quality": body.quality,
            "format": body.format,
            "fps": body.fps,
            "include_subtitles": body.include_subtitles,
        },
    )
    session.add(export_job)
    await session.flush()
    await session.commit()

    # 推送任务到 Redis 队列
    r = await _get_redis()
    if r is not None:
        task = {
            "job_id": str(job_id),
            "dsl": project.dsl_snapshot,
            "config": export_job.config,
        }
        try:
            r.rpush("manim:queue", json.dumps(task, ensure_ascii=False))
            logger.info("导出任务入队: job=%s", job_id)
        except Exception as exc:
            logger.error("Redis 入队失败: %s", exc)
            export_job.status = "failed"
            export_job.error_log = f"Redis 入队失败: {exc}"

    # 启动后台 fallback：3s 内若 Worker 没消费则自己处理
    asyncio.create_task(_fallback_export(str(job_id), project.dsl_snapshot, export_job.config))

    return {
        "job_id": str(job_id),
        "status": "queued",
    }


# ponytail: global pool, per-job pools if concurrent exports become a bottleneck
_pool = ThreadPoolExecutor(max_workers=2)


def _do_export_sync(job_id: str, dsl: dict, config: dict, redis_url: str) -> None:
    """同步导出逻辑，在独立线程中运行，避免阻塞 FastAPI 事件循环。"""
    import redis as redis_lib
    import shutil as _shutil

    r = redis_lib.from_url(redis_url, decode_responses=True)

    _update_redis_status(r, job_id, "rendering", progress=5)
    logger.info("导出开始: job=%s", job_id)

    try:
        # 1. DSL → Manim 脚本（LLM 生成，在新 event loop 中运行）
        # 注意：asyncio.run() 在线程池中创建新事件循环是临时方案，
        # 未来应重构为纯异步以避免事件循环嵌套问题。
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        from adapters.manim_llm_adapter import convert_dsl_to_manim_llm
        from adapters.manim_validator import validate_script, has_errors

        files = asyncio.run(convert_dsl_to_manim_llm(dsl, dsl.get("teaching_plan")))

        issues = validate_script(files["main.py"])
        if has_errors(issues):
            detail = "; ".join(
                f"[{i['rule']}] {i['detail']}" for i in issues if i["severity"] == "error"
            )
            logger.warning("Manim 脚本校验发现问题: %s", detail)
        elif issues:
            for i in issues:
                logger.info("Manim 脚本校验 warn: [%s] %s", i["rule"], i["detail"])

        # 2. 写入临时目录
        export_dir = Path(get_settings().export_dir) / job_id
        scripts_dir = export_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "main.py").write_text(files["main.py"], encoding="utf-8")
        (scripts_dir / "render_config.json").write_text(files["render_config.json"], encoding="utf-8")
        (scripts_dir / "subtitles.srt").write_text(files["subtitles.srt"], encoding="utf-8")

        for src_name in ["main.py", "render_config.json", "subtitles.srt"]:
            src = scripts_dir / src_name
            if src.exists():
                _shutil.copy2(src, export_dir / src_name)

        _update_redis_status(r, job_id, "rendering", progress=30)

        # 3. 渲染视频
        quality = config.get("quality", "h")
        fps = config.get("fps", 30)
        quality_flags = {"l": "-ql", "m": "-qm", "h": "-qh", "k": "-qk"}
        artifacts: list[dict] = []
        mp4_output_dir = export_dir / "videos"

        _update_redis_status(r, job_id, "rendering", progress=50)

        real_mp4 = _render_manim_sync(
            str(scripts_dir / "main.py"), export_dir, scripts_dir,
            quality_flags.get(quality, "-qh"), fps, str(mp4_output_dir),
        )

        artifacts.append({
            "type": "manim_source", "filename": "main.py",
            "size_bytes": (scripts_dir / "main.py").stat().st_size,
        })
        srt = scripts_dir / "subtitles.srt"
        if srt.exists():
            artifacts.append({
                "type": "subtitle", "filename": "subtitles.srt",
                "size_bytes": srt.stat().st_size,
            })

        if real_mp4:
            artifacts.insert(0, real_mp4)
            _update_redis_status(r, job_id, "completed", progress=100, artifacts=artifacts)
            logger.info("导出完成: job=%s | artifacts=%d", job_id, len(artifacts))
        else:
            _update_redis_status(r, job_id, "failed", error="渲染完成但未找到 MP4 产物，请检查 Manim 脚本")
            logger.warning("渲染未产出 MP4: job=%s", job_id)

    except Exception as exc:
        logger.exception("导出失败: job=%s", job_id)
        _update_redis_status(r, job_id, "failed", error=str(exc)[:500])
        try:
            asyncio.run(_update_db_export_status(job_id, "failed", error_log=str(exc)[:500]))
        except Exception:
            pass


async def _fallback_export(job_id: str, dsl: dict, config: dict) -> None:
    """后台导出 fallback：等 3s 给 Worker 机会，未消费则在独立线程中处理。"""
    await asyncio.sleep(3)

    r = await _get_redis()
    if r is None:
        await _update_db_export_status(job_id, "failed", error_log="Redis 不可用，无法处理导出")
        return

    # 检查 Worker 是否已消费（优先检查 claimed 标记）
    if r.get(f"manim:job:{job_id}:claimed") or r.get(f"manim:job:{job_id}"):
        return

    settings = get_settings()
    loop = asyncio.get_running_loop()
    loop.run_in_executor(_pool, _do_export_sync, job_id, dsl, config, settings.redis_url)


def _render_manim_sync(
    script_path: str, export_dir: Path, scripts_dir: Path,
    quality_flag: str, fps: int, media_dir: str,
) -> dict | None:
    """渲染 DSL 生成的 Manim 脚本（同步版本）。"""
    import shutil as _shutil

    env = os.environ.copy()
    from adapters.manim_adapter import _find_ffmpeg
    ffmpeg_dir = _find_ffmpeg()
    if ffmpeg_dir:
        env["PATH"] = ffmpeg_dir + os.pathsep + env.get("PATH", "")

    media_abs = str(Path(media_dir).resolve())
    result = subprocess.run(
        [sys.executable, "-m", "manim", str(Path(script_path).resolve()),
         quality_flag, f"--fps={fps}", "--format=mp4", f"--media_dir={media_abs}"],
        capture_output=True, text=True, timeout=600,
        cwd=str(export_dir),
        env=env,
    )

    if result.returncode != 0:
        logger.warning("Manim 渲染失败 (returncode=%d): %s",
                       result.returncode, result.stderr[:300])
        return None

    for base in [Path(media_abs), export_dir, scripts_dir]:
        if not base.exists():
            continue
        for mp4 in base.rglob("*.mp4"):
            if "partial_movie_files" in str(mp4) or mp4.name == "preview.mp4":
                continue
            dest = export_dir / mp4.name
            _shutil.copy2(mp4, dest)
            return {"type": "mp4", "filename": mp4.name,
                    "size_bytes": dest.stat().st_size}

    # Manim 未产出最终 MP4，尝试手动合并 partial_movie_files
    ffmpeg_bin = os.path.join(ffmpeg_dir, "ffmpeg.exe") if ffmpeg_dir else "ffmpeg"
    merged = _merge_partial_movies(export_dir, ffmpeg_bin)
    if merged:
        return merged
    logger.warning("DSL 渲染完成但未找到 MP4 产物")
    return None


def _merge_partial_movies(export_dir: Path, ffmpeg_bin: str) -> dict | None:
    """合并 Manim 生成的 partial_movie_files 为最终 MP4。"""
    partial_dirs = list(export_dir.rglob("partial_movie_files"))
    if not partial_dirs:
        return None

    for pd_dir in partial_dirs:
        mp4s = sorted(pd_dir.rglob("*.mp4"))
        if not mp4s:
            continue
        concat_list = export_dir / "_concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for mp4 in mp4s:
                f.write(f"file '{mp4}'\n")

        output = export_dir / "output.mp4"
        try:
            result = subprocess.run(
                [ffmpeg_bin, "-f", "concat", "-safe", "0", "-i", str(concat_list),
                 "-c", "copy", str(output), "-y"],
                capture_output=True, text=True, timeout=120,
            )
            concat_list.unlink(missing_ok=True)
            if result.returncode == 0 and output.exists():
                logger.info("手动合并部分视频: %d 分片 → %s (%.1f MB)",
                           len(mp4s), output.name, output.stat().st_size / 1e6)
                return {"type": "mp4", "filename": output.name,
                        "size_bytes": output.stat().st_size}
        except Exception as exc:
            logger.warning("手动合并部分视频失败: %s", exc)
            concat_list.unlink(missing_ok=True)
        # 继续尝试下一个 partial_movie_files 目录

    return None


def _update_redis_status(
    r,
    job_id: str,
    status: str,
    progress: float = 0,
    artifacts: list[dict] | None = None,
    error: str | None = None,
) -> None:
    """写入任务状态到 Redis（worker 和 fallback 共用）。"""
    import time
    data: dict = {"job_id": job_id, "status": status,
                  "progress_pct": progress, "updated_at": time.time()}
    if artifacts is not None:
        data["artifacts"] = artifacts
    if error is not None:
        data["error_log"] = error
    r.setex(f"manim:job:{job_id}", 86400, json.dumps(data))


async def _update_db_export_status(job_id: str, status: str, *, error_log: str = "") -> None:
    """同步导出状态到 DB（供没有 Redis 时回退）。"""
    try:
        from db.database import async_session_factory
        from db.models import ExportJobModel
        jid = uuid.UUID(job_id)
        async with async_session_factory() as session:
            job = await session.get(ExportJobModel, jid)
            if job:
                job.status = status
                if error_log:
                    job.error_log = error_log
                await session.commit()
    except Exception:
        logger.warning("导出状态 DB 同步失败")


# ============================================================================
# 查询导出状态
# ============================================================================


@router.get("/export/{job_id}")
async def get_export_status(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """查询导出任务状态。先查 Redis（实时进度），再查 DB（持久记录）。"""
    from db.models import ExportJobModel

    jid = uuid.UUID(job_id) if _is_uuid(job_id) else None

    # 1. 尝试从 Redis 获取实时进度
    r = await _get_redis()
    if r is not None:
        redis_data = r.get(f"manim:job:{job_id}")
        if redis_data:
            data = json.loads(redis_data)
            status = data.get("status", "queued")

            result = {
                "job_id": job_id,
                "status": status,
                "progress_pct": data.get("progress_pct", 0),
                "artifacts": None,
                "error_log": data.get("error_log"),
                "duration_ms": None,
                "total_frames": None,
            }

            if status == "completed":
                artifacts = data.get("artifacts", [])
                result["artifacts"] = [
                    {
                        "type": a.get("type", "mp4"),
                        "url": f"/api/export/{job_id}/download/{a.get('filename', 'output.mp4')}",
                        "size_bytes": a.get("size_bytes", 0),
                    }
                    for a in artifacts
                ]

                # 同步状态到 DB
                if jid:
                    job = await session.get(ExportJobModel, jid)
                    if job:
                        job.status = "completed"
                        job.progress_pct = 100
                        job.artifacts = artifacts
                        await session.commit()

            return result

    # 2. 回退到 DB 查询
    if jid:
        job = await session.get(ExportJobModel, jid)
        if job:
            db_artifacts = job.artifacts or []
            return {
                "job_id": str(job.id),
                "status": job.status,
                "progress_pct": job.progress_pct or 0,
                "artifacts": [
                    {
                        "type": a.get("type", "mp4"),
                        "url": f"/api/export/{job_id}/download/{a.get('filename', 'output.mp4')}",
                        "size_bytes": a.get("size_bytes", 0),
                    }
                    for a in db_artifacts
                ],
                "error_log": job.error_log,
                "duration_ms": None,
                "total_frames": None,
            }

    raise HTTPException(status_code=404, detail="Export job not found")


# ============================================================================
# 下载产物
# ============================================================================


@router.get("/export/{job_id}/download/{filename}")
async def download_artifact(
    job_id: str,
    filename: str,
) -> FileResponse:
    """下载导出的产物文件。

    搜索顺序：
    1. settings.export_dir / job_id（本地开发）
    2. /app/data/exports / job_id（Docker 共享卷）
    3. 递归搜索 mp4 文件（Manim 会创建视频子目录）
    """
    settings = get_settings()
    export_dir = Path(settings.export_dir) / job_id

    # 候选搜索目录
    search_dirs = [
        export_dir,
        Path("/app/data/exports") / job_id,   # Docker 共享卷
        Path("data/exports") / job_id,         # 相对路径回退
    ]

    file_path = None
    for base_dir in search_dirs:
        candidate = base_dir / filename
        if candidate.exists():
            file_path = candidate
            break
        # mp4 文件可能在 Manim 创建的子目录中
        if not candidate.exists() and filename.endswith(".mp4"):
            mp4_candidates = list(base_dir.rglob(filename)) if base_dir.exists() else []
            if mp4_candidates:
                file_path = mp4_candidates[0]
                break

    if file_path is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # 安全检查：防止路径遍历
    try:
        resolved = file_path.resolve()
        allowed_bases = [d.resolve() for d in search_dirs if d.exists()]
        if not any(resolved.is_relative_to(base) for base in allowed_bases):
            raise HTTPException(status_code=403, detail="Access denied")
    except (ValueError, OSError):
        raise HTTPException(status_code=403, detail="Access denied")

    media_type_map = {
        ".mp4": "video/mp4",
        ".py": "text/x-python",
        ".srt": "text/plain",
        ".json": "application/json",
    }

    suffix = file_path.suffix
    media_type = media_type_map.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )


# ── Helpers ─────────────────────────────────────────────────


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError):
        return False
