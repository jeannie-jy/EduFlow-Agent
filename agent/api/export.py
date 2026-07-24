"""导出 API 路由。

POST   /api/projects/{id}/export/manim          创建视频导出任务
GET    /api/export/{job_id}                     查询导出状态
GET    /api/export/{job_id}/download/{filename} 下载产物
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import get_session
from schema.project import ExportManimRequest
from .deps import CurrentUser
from .ownership import get_owned_project

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
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """创建 Manim 视频导出任务。"""
    from db.models import ExportJobModel

    project = await get_owned_project(
        session, project_id, current_user.id, for_update=True
    )
    pid = project.id

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


async def _fallback_export(job_id: str, dsl: dict, config: dict) -> None:
    """后台导出 fallback：Worker 不可用时直接调用 manim_adapter 渲染。

    先等 3s 给 Worker 机会消费；若 Worker 已处理则不做任何事。
    """
    await asyncio.sleep(3)

    r = await _get_redis()
    if r is None:
        await _update_db_export_status(job_id, "failed", error_log="Redis 不可用，无法处理导出")
        return

    # Worker 已处理？
    if r.get(f"manim:job:{job_id}"):
        return

    _update_redis_status(r, job_id, "rendering", progress=5)
    logger.info("fallback 导出开始: job=%s", job_id)

    try:
        # 1. DSL → Manim 脚本
        from adapters.manim_adapter import convert_dsl_to_manim
        files = convert_dsl_to_manim(dsl)

        # 2. 写入临时目录
        export_dir = Path(get_settings().export_dir) / job_id
        scripts_dir = export_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "main.py").write_text(files["main.py"], encoding="utf-8")
        (scripts_dir / "render_config.json").write_text(files["render_config.json"], encoding="utf-8")
        (scripts_dir / "subtitles.srt").write_text(files["subtitles.srt"], encoding="utf-8")

        # 复制脚本产物到 job 根目录（download 端点从根目录查找）
        import shutil as _shutil
        for src_name in ["main.py", "render_config.json", "subtitles.srt"]:
            src = scripts_dir / src_name
            if src.exists():
                _shutil.copy2(src, export_dir / src_name)

        _update_redis_status(r, job_id, "rendering", progress=30)

        # 3. 尝试渲染（manim CLI 不可用时只返回脚本）
        quality = config.get("quality", "h")
        fps = config.get("fps", 30)
        quality_flags = {"l": "-ql", "m": "-qm", "h": "-qh", "k": "-qk"}
        artifacts: list[dict] = []

        try:
            manim_path = _shutil.which("manim")
            if manim_path is None:
                raise FileNotFoundError("manim not found")

            _update_redis_status(r, job_id, "rendering", progress=50)

            mp4_output_dir = export_dir / "videos"
            result = subprocess.run(
                [sys.executable, "-m", "manim", str(scripts_dir / "main.py"),
                 quality_flags.get(quality, "-qh"), f"--fps={fps}",
                 "--format=mp4", f"--media_dir={mp4_output_dir}"],
                capture_output=True, text=True, timeout=300,
                cwd=str(export_dir),
            )

            if result.returncode == 0:
                mp4_dir = mp4_output_dir / "videos" / "main"
                if mp4_dir.exists():
                    for mp4 in mp4_dir.rglob("*.mp4"):
                        artifacts.append({"type": "mp4", "filename": mp4.name,
                                          "size_bytes": mp4.stat().st_size})
                        _shutil.copy2(mp4, export_dir / mp4.name)
            else:
                logger.warning("Manim 渲染失败 (returncode=%d): %s",
                               result.returncode, result.stderr[:500])
        except FileNotFoundError:
            logger.info("manim 未安装，仅导出脚本")
        except Exception as exc:
            logger.warning("Manim 渲染异常: %s", exc)

        _update_redis_status(r, job_id, "rendering", progress=85)

        # 脚本文件始终作为产物
        artifacts.append({"type": "manim_source", "filename": "main.py",
                          "size_bytes": (scripts_dir / "main.py").stat().st_size})
        srt = scripts_dir / "subtitles.srt"
        if srt.exists():
            artifacts.append({"type": "subtitle", "filename": "subtitles.srt",
                              "size_bytes": srt.stat().st_size})

        _update_redis_status(r, job_id, "completed", progress=100, artifacts=artifacts)
        logger.info("fallback 导出完成: job=%s | artifacts=%d", job_id, len(artifacts))

    except Exception as exc:
        logger.exception("fallback 导出失败: job=%s", job_id)
        _update_redis_status(r, job_id, "failed", error=str(exc)[:500])


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
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """查询导出任务状态。先查 Redis（实时进度），再查 DB（持久记录）。"""
    from sqlalchemy import select

    from db.models import ExportJobModel, Project

    jid = uuid.UUID(job_id) if _is_uuid(job_id) else None
    job = None
    if jid:
        job = await session.scalar(
            select(ExportJobModel)
            .join(Project, Project.id == ExportJobModel.project_id)
            .where(
                ExportJobModel.id == jid,
                Project.owner_id == current_user.id,
            )
        )
    if job is None:
        raise HTTPException(status_code=404, detail="Export job not found")

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
                job.status = "completed"
                job.progress_pct = 100
                job.artifacts = artifacts
                await session.flush()

            return result

    # 2. 回退到已授权的 DB 记录
    return {
        "job_id": str(job.id),
        "status": job.status,
        "progress_pct": job.progress_pct or 0,
        "artifacts": job.artifacts,
        "error_log": job.error_log,
        "duration_ms": None,
        "total_frames": None,
    }


# ============================================================================
# 下载产物
# ============================================================================


@router.get("/export/{job_id}/download/{filename}")
async def download_artifact(
    job_id: str,
    filename: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """下载导出的产物文件。

    搜索顺序：
    1. settings.export_dir / job_id（本地开发）
    2. /app/data/exports / job_id（Docker 共享卷）
    3. 递归搜索 mp4 文件（Manim 会创建视频子目录）
    """
    from sqlalchemy import select
    from db.models import ExportJobModel, Project

    jid = uuid.UUID(job_id) if _is_uuid(job_id) else None
    job = None
    if jid:
        job = await session.scalar(
            select(ExportJobModel)
            .join(Project, Project.id == ExportJobModel.project_id)
            .where(
                ExportJobModel.id == jid,
                Project.owner_id == current_user.id,
            )
        )
    if job is None:
        raise HTTPException(status_code=404, detail="Export job not found")

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
