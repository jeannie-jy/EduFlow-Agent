"""导出 API 路由。

POST   /api/projects/{id}/export/manim          创建视频导出任务
GET    /api/export/{job_id}                     查询导出状态
GET    /api/export/{job_id}/download/{filename} 下载产物
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import get_session
from db.models import User
from schema.project import ExportManimRequest
from services.audit import record_audit

from .auth import get_current_user, is_admin, require_editor
from .deps import parse_project_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])

# Redis 客户端（延迟初始化，asyncio.Lock 保护）
_redis_client = None
_redis_lock = asyncio.Lock()


class ExportWorkspaceLimitError(RuntimeError):
    """The renderer exceeded its per-job file-count or byte budget."""


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
            _redis_client = redis_lib.from_url(
                settings.redis_url, decode_responses=True
            )
        except Exception:
            logger.warning("Redis 不可用")
            _redis_client = None
    return _redis_client


async def close_export_resources() -> None:
    """Close the lazily-created Redis client during application shutdown."""
    global _redis_client
    client = _redis_client
    _redis_client = None
    if client is not None:
        await asyncio.to_thread(client.close)


async def _owned_export_job(
    session: AsyncSession,
    job_id: uuid.UUID,
    current_user: User | None,
):
    """Resolve an export by owner, with an explicit administrator bypass."""
    from db.models import ExportJobModel, Project

    if current_user is None or is_admin(current_user):
        return await session.get(ExportJobModel, job_id)
    return await session.scalar(
        select(ExportJobModel)
        .join(Project, Project.id == ExportJobModel.project_id)
        .where(
            ExportJobModel.id == job_id,
            Project.owner_id == str(current_user.id),
        )
    )


def _source_version_ref(job) -> str | None:
    value = getattr(job, "source_version_id", None)
    return str(value) if isinstance(value, uuid.UUID) else None


# ============================================================================
# 创建导出任务
# ============================================================================


@router.post("/projects/{project_id}/export/manim", status_code=201)
async def create_export_job(
    project_id: str,
    body: ExportManimRequest,
    session: AsyncSession = Depends(get_session),
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
    _editor: Annotated[User | None, Depends(require_editor)] = None,
) -> dict:
    """创建 Manim 视频导出任务。"""
    settings = get_settings()
    if settings.manim_execution_mode != "queue":
        raise HTTPException(
            status_code=503,
            detail=(
                "Manim execution is disabled because an isolated render worker is not configured. "
                "Start the isolated render worker and set MANIM_EXECUTION_MODE=queue."
            ),
        )
    from db.models import ExportJobModel, Project

    pid = parse_project_id(project_id)
    project = await session.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    normalized_key = idempotency_key.strip() if idempotency_key else None
    if normalized_key:
        existing = await session.scalar(
            select(ExportJobModel).where(
                ExportJobModel.project_id == pid,
                ExportJobModel.target == "manim_video",
                ExportJobModel.idempotency_key == normalized_key,
            )
        )
        if existing is not None:
            return {
                "job_id": str(existing.id),
                "status": existing.status,
                "source_version_id": _source_version_ref(existing),
            }

    from services.project_persistence import load_canonical_project_dsl

    # frames 可能在快照顶层（全量流）或 module_outputs.frames（模块流）
    dsl = await load_canonical_project_dsl(project, session)
    if dsl is None:
        raise HTTPException(status_code=400, detail="Project has no frames to export")

    # Freeze the canonical Frames-table view before enqueueing. The worker must
    # render this immutable version instead of whichever project state happens
    # to be current when it eventually acquires the job.
    from .versions import save_version

    source_version = await save_version(
        project_id,
        dsl,
        "Manim export source snapshot",
        session,
    )
    job_id = uuid.uuid4()

    # 持久化到 DB
    export_job = ExportJobModel(
        id=job_id,
        project_id=pid,
        source_version_id=uuid.UUID(source_version["id"]),
        target="manim_video",
        status="queued",
        idempotency_key=normalized_key,
        config={
            "quality": body.quality,
            "format": body.format,
            "fps": body.fps,
            "include_subtitles": body.include_subtitles,
        },
    )
    session.add(export_job)
    record_audit(
        session,
        action="export.queue",
        resource_type="export_job",
        resource_id=str(job_id),
        actor_id=current_user.id if current_user is not None else None,
        details={
            "target": "manim_video",
            "source_version_id": source_version["id"],
        },
    )
    try:
        await session.flush()
        await session.commit()
    except IntegrityError:
        await session.rollback()
        if not normalized_key:
            raise
        existing = await session.scalar(
            select(ExportJobModel).where(
                ExportJobModel.project_id == pid,
                ExportJobModel.target == "manim_video",
                ExportJobModel.idempotency_key == normalized_key,
            )
        )
        if existing is None:
            raise
        return {
            "job_id": str(existing.id),
            "status": existing.status,
            "source_version_id": _source_version_ref(existing),
        }

    # 只持久化任务；独立 Worker 通过 SELECT ... FOR UPDATE SKIP LOCKED 领取。

    return {
        "job_id": str(job_id),
        "status": "queued",
        "source_version_id": source_version["id"],
    }


@router.delete("/export/{job_id}")
async def cancel_export_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
    _editor: Annotated[User | None, Depends(require_editor)] = None,
) -> dict:
    """Idempotently cancel a queued/running export without leaking its owner."""
    from datetime import datetime, timezone

    from db.models import ExportJobAttempt

    jid = uuid.UUID(job_id) if _is_uuid(job_id) else None
    if jid is None:
        raise HTTPException(status_code=404, detail="Export job not found")
    job = await _owned_export_job(session, jid, current_user)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job not found")
    if job.status in {"completed", "failed"}:
        raise HTTPException(status_code=409, detail="Export job is already terminal")
    if job.status != "cancelled":
        job.status = "cancelled"
        job.worker_id = None
        job.lease_expires_at = None
        job.completed_at = datetime.now(timezone.utc)
        await session.execute(
            update(ExportJobAttempt)
            .where(
                ExportJobAttempt.job_id == jid,
                ExportJobAttempt.status == "rendering",
            )
            .values(
                status="cancelled",
                finished_at=job.completed_at,
                error_class="cancelled",
            )
        )
        record_audit(
            session,
            action="export.cancel",
            resource_type="export_job",
            resource_id=str(jid),
            actor_id=current_user.id if current_user is not None else None,
        )
        await session.commit()
    redis_client = await _get_redis()
    if redis_client is not None:
        _try_update_redis_status(redis_client, job_id, "cancelled", progress=0)
    return {"job_id": job_id, "status": "cancelled"}


# ponytail: global pool, per-job pools if concurrent exports become a bottleneck
_pool = ThreadPoolExecutor(max_workers=2)


def _do_export_sync(job_id: str, dsl: dict, config: dict, redis_url: str) -> None:
    """同步导出入口（线程池线程中运行）。

    线程内创建独立事件循环 + 独立 DB engine：
    - 模块级 asyncpg 连接池与模块级 LLM 客户端都绑定主事件循环，
      跨 loop 使用会抛 InternalClientError / Task attached to a different loop；
    - 因此线程内一律使用线程本地资源（LLM 客户端已线程本地化，见 llm_client.py）。
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    engine = None
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        from config import get_settings

        engine = create_async_engine(get_settings().database_url)
        loop.run_until_complete(
            _do_export_async(job_id, dsl, config, redis_url, engine)
        )
    finally:
        if engine is not None:
            try:
                loop.run_until_complete(engine.dispose())
            except Exception:
                pass
        loop.close()


async def _do_export_async(
    job_id: str,
    dsl: dict,
    config: dict,
    redis_url: str,
    engine,
) -> None:
    """异步导出核心逻辑（在线程独立事件循环中执行）。"""
    import shutil as _shutil

    import redis as redis_lib

    r = redis_lib.from_url(redis_url, decode_responses=True)
    # 提前计算，失败落盘（except 分支）也需要该目录
    export_dir = Path(get_settings().export_dir) / job_id

    _try_update_redis_status(r, job_id, "rendering", progress=5)
    logger.info("导出开始: job=%s", job_id)

    try:
        # 1. DSL → Manim 脚本（LLM 生成，使用线程本地 LLM 客户端）
        from adapters.manim_llm_adapter import convert_dsl_to_manim_llm
        from adapters.manim_validator import has_errors, validate_script

        files = await convert_dsl_to_manim_llm(dsl, dsl.get("teaching_plan"))

        issues = validate_script(files["main.py"])
        if has_errors(issues):
            detail = "; ".join(
                f"[{i['rule']}] {i['detail']}"
                for i in issues
                if i["severity"] == "error"
            )
            logger.warning("Manim 脚本校验发现问题: %s", detail)
        elif issues:
            for i in issues:
                logger.info("Manim 脚本校验 warn: [%s] %s", i["rule"], i["detail"])

        # 2. 写入临时目录
        scripts_dir = export_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "main.py").write_text(files["main.py"], encoding="utf-8")
        (scripts_dir / "render_config.json").write_text(
            files["render_config.json"], encoding="utf-8"
        )
        (scripts_dir / "subtitles.srt").write_text(
            files["subtitles.srt"], encoding="utf-8"
        )

        for src_name in ["main.py", "render_config.json", "subtitles.srt"]:
            src = scripts_dir / src_name
            if src.exists():
                _shutil.copy2(src, export_dir / src_name)

        _try_update_redis_status(r, job_id, "rendering", progress=30)

        # 3. 将已校验脚本交给无网络、无凭证的沙箱容器。
        quality = config.get("quality", "h")
        fps = config.get("fps", 30)
        artifacts: list[dict] = []

        _try_update_redis_status(r, job_id, "rendering", progress=50)
        render_result = await _submit_and_wait_for_sandbox(
            export_dir, quality=quality, fps=fps
        )

        artifacts.append(
            {
                "type": "manim_source",
                "filename": "main.py",
                "size_bytes": (scripts_dir / "main.py").stat().st_size,
            }
        )
        srt = scripts_dir / "subtitles.srt"
        if srt.exists():
            artifacts.append(
                {
                    "type": "subtitle",
                    "filename": "subtitles.srt",
                    "size_bytes": srt.stat().st_size,
                }
            )

        real_mp4 = render_result.get("artifact")
        if render_result.get("status") == "completed" and real_mp4:
            artifact_path = (export_dir / str(real_mp4.get("filename", ""))).resolve()
            if (
                not artifact_path.is_relative_to(export_dir.resolve())
                or artifact_path.suffix.lower() != ".mp4"
                or not artifact_path.is_file()
                or artifact_path.stat().st_size
                > get_settings().export_max_artifact_bytes
            ):
                raise RuntimeError("Sandbox returned an invalid or oversized artifact")
            real_mp4["size_bytes"] = artifact_path.stat().st_size
            artifacts.insert(0, real_mp4)
            persisted, artifacts = await _publish_and_persist_export_artifacts(
                export_dir,
                job_id,
                artifacts,
                engine=engine,
            )
            if persisted:
                _try_update_redis_status(
                    r, job_id, "completed", progress=100, artifacts=artifacts
                )
            logger.info("导出完成: job=%s | artifacts=%d", job_id, len(artifacts))
        else:
            retryable = render_result.get("retryable", True) is not False
            error_code = str(render_result.get("error_code") or "render_failed")
            try:
                persisted = await _update_db_export_status(
                    job_id,
                    "failed",
                    error_log="视频渲染失败，请重试",
                    retryable_failure=retryable,
                    error_class=error_code,
                    engine=engine,
                )
                if persisted:
                    _try_update_redis_status(
                        r,
                        job_id,
                        "failed",
                        error="视频渲染失败，请重试",
                    )
            except Exception:
                pass
            logger.warning("渲染未产出 MP4: job=%s", job_id)

    except Exception as exc:
        logger.exception("导出失败: job=%s", job_id)
        from services.redaction import public_failure_message

        error_log = public_failure_message("export")
        # LLM 校验失败时落盘失败脚本 + 校验问题，供复现调试
        # （此前 main.py 未写盘，失败样本无法复现）
        from adapters.manim_llm_adapter import ManimCodeValidationError

        if isinstance(exc, ManimCodeValidationError):
            try:
                debug_dir = export_dir / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                (debug_dir / "main.py").write_text(exc.script, encoding="utf-8")
                (debug_dir / "validation_errors.json").write_text(
                    json.dumps(exc.issues, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                error_log = "生成的视频脚本未通过安全校验，请重试"
                logger.info("校验失败脚本已落盘: %s", debug_dir)
            except Exception:
                pass
        # 先同步 DB（前端轮询的最终依据），Redis 状态写入单独容错——
        # 否则 Redis 不可用时 _update_redis_status 抛异常会吞掉 DB 同步
        try:
            persisted = await _update_db_export_status(
                job_id,
                "failed",
                error_log=error_log,
                retryable_failure=not isinstance(exc, ManimCodeValidationError),
                error_class=(
                    "script_validation_failed"
                    if isinstance(exc, ManimCodeValidationError)
                    else "export_failed"
                ),
                engine=engine,
            )
        except Exception:
            persisted = False
        try:
            if persisted:
                _try_update_redis_status(r, job_id, "failed", error=error_log)
        except Exception:
            pass


async def _fallback_export(job_id: str, dsl: dict, config: dict) -> None:
    """Worker 内导出：在线程中运行同步 Manim 工具链。

    Redis 仅用于实时进度追踪（get_export_status 优先读 Redis、回退 DB），
    渲染本身不依赖 Redis；Redis 不可用时由 DB 状态同步兜底。
    此函数只应由独立 render worker 调用，API 路由只负责持久化排队。
    """
    settings = get_settings()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        _pool, _do_export_sync, job_id, dsl, config, settings.redis_url
    )


async def _submit_and_wait_for_sandbox(
    export_dir: Path, *, quality: str, fps: int
) -> dict:
    """Exchange a render request/result through the shared job directory."""
    settings = get_settings()
    export_dir.mkdir(parents=True, exist_ok=True)
    attempt_id = uuid.uuid4().hex
    request_path = export_dir / "render-request.json"
    request_tmp = export_dir / f".render-request-{attempt_id}.tmp"
    result_path = export_dir / "render-result.json"
    result_path.unlink(missing_ok=True)
    script_path = export_dir / "scripts" / "main.py"
    script_sha256 = hashlib.sha256(script_path.read_bytes()).hexdigest()
    request_tmp.write_text(
        json.dumps(
            {
                "attempt_id": attempt_id,
                "quality": quality,
                "fps": fps,
                "script_sha256": script_sha256,
            }
        ),
        encoding="utf-8",
    )
    request_tmp.replace(request_path)

    deadline = asyncio.get_running_loop().time() + settings.manim_timeout_seconds + 30
    while asyncio.get_running_loop().time() < deadline:
        if result_path.exists():
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                result = None
            if isinstance(result, dict) and result.get("attempt_id") == attempt_id:
                return result
        await asyncio.sleep(min(settings.export_worker_poll_seconds, 2.0))
    raise TimeoutError("Render sandbox did not return a result before the deadline")


async def _publish_export_artifacts(
    export_dir: Path, job_id: str, artifacts: list[dict]
) -> list[dict]:
    """Publish verified outputs through the configured ArtifactStore."""
    from services.artifact_store import get_artifact_store

    store = get_artifact_store()
    media_types = {
        ".mp4": "video/mp4",
        ".py": "text/x-python",
        ".srt": "text/plain",
        ".json": "application/json",
    }
    published: list[dict] = []
    root = export_dir.resolve()
    for artifact in artifacts:
        filename = str(artifact.get("filename", ""))
        source = (root / filename).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise RuntimeError(
                "Artifact source is missing or outside the job directory"
            )
        stored = await store.put_file(
            f"exports/{job_id}/{filename}",
            source,
            media_types.get(source.suffix.lower(), "application/octet-stream"),
        )
        published.append(
            {
                **artifact,
                "storage_key": stored.key,
                "size_bytes": stored.size_bytes,
                "sha256": stored.sha256,
                "content_type": stored.content_type,
            }
        )
    return published


async def _delete_published_export_artifacts(artifacts: list[dict]) -> None:
    """Best-effort compensation for objects whose DB transaction did not commit."""
    from services.artifact_store import get_artifact_store

    store = get_artifact_store()
    for artifact in artifacts:
        key = artifact.get("storage_key")
        if not key:
            continue
        try:
            await store.delete(str(key))
        except Exception:
            logger.exception("export artifact compensation failed: key=%s", key)


async def _publish_and_persist_export_artifacts(
    export_dir: Path,
    job_id: str,
    artifacts: list[dict],
    *,
    engine=None,
) -> tuple[bool, list[dict]]:
    """Publish artifacts and compensate if the authoritative DB write loses."""
    published = await _publish_export_artifacts(export_dir, job_id, artifacts)
    try:
        persisted = await _update_db_export_status(
            job_id,
            "completed",
            artifacts=published,
            progress=100,
            engine=engine,
        )
    except Exception:
        await _delete_published_export_artifacts(published)
        raise
    if not persisted:
        await _delete_published_export_artifacts(published)
    return persisted, published


def _render_manim_sync(
    script_path: str,
    export_dir: Path,
    scripts_dir: Path,
    quality_flag: str,
    fps: int,
    media_dir: str,
) -> dict | None:
    """渲染 DSL 生成的 Manim 脚本（同步版本）。"""
    import shutil as _shutil

    env = os.environ.copy()
    from adapters.manim_adapter import _find_ffmpeg

    ffmpeg_dir = _find_ffmpeg()
    if ffmpeg_dir:
        env["PATH"] = ffmpeg_dir + os.pathsep + env.get("PATH", "")

    media_abs = str(Path(media_dir).resolve())
    result = _run_subprocess_group(
        [
            sys.executable,
            "-m",
            "manim",
            str(Path(script_path).resolve()),
            quality_flag,
            f"--fps={fps}",
            "--format=mp4",
            f"--media_dir={media_abs}",
        ],
        cwd=str(export_dir),
        env=env,
        timeout=get_settings().manim_timeout_seconds,
        quota_root=export_dir,
        max_workspace_bytes=get_settings().export_max_workspace_bytes,
        max_workspace_files=get_settings().export_max_workspace_files,
    )

    if result.returncode != 0:
        # 完整记录渲染错误：日志打关键尾部，同时落盘完整 stderr（此前 [:300] 截断
        # 会丢掉真正的错误信息，如 NameError: font_size is not defined）
        logger.warning(
            "Manim 渲染失败 (returncode=%d): %s",
            result.returncode,
            result.stderr[-2000:],
        )
        try:
            error_log_path = export_dir / "render_error.log"
            error_log_path.write_text(result.stderr or "(no stderr)", encoding="utf-8")
            logger.info("Manim 渲染错误已落盘: %s", error_log_path)
        except Exception:
            pass
        return None

    for base in [Path(media_abs), export_dir, scripts_dir]:
        if not base.exists():
            continue
        for mp4 in base.rglob("*.mp4"):
            if "partial_movie_files" in str(mp4) or mp4.name == "preview.mp4":
                continue
            dest = export_dir / mp4.name
            _shutil.copy2(mp4, dest)
            return {
                "type": "mp4",
                "filename": mp4.name,
                "size_bytes": dest.stat().st_size,
            }

    # Manim 未产出最终 MP4，尝试手动合并 partial_movie_files
    ffmpeg_bin = os.path.join(ffmpeg_dir, "ffmpeg.exe") if ffmpeg_dir else "ffmpeg"
    merged = _merge_partial_movies(export_dir, ffmpeg_bin)
    if merged:
        return merged
    logger.warning("DSL 渲染完成但未找到 MP4 产物")
    return None


def _run_subprocess_group(
    command: list[str],
    *,
    cwd: str,
    env: dict[str, str],
    timeout: int,
    quota_root: Path | None = None,
    max_workspace_bytes: int | None = None,
    max_workspace_files: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command in its own process group and kill the whole group on timeout."""
    popen_kwargs: dict = {
        "cwd": cwd,
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **popen_kwargs)
    import time

    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _terminate_process_group(process)
            process.communicate()
            raise TimeoutError(f"Manim exceeded {timeout}s and was terminated")
        try:
            stdout, stderr = process.communicate(timeout=min(1.0, remaining))
            if quota_root is not None and _workspace_exceeds_limit(
                quota_root,
                max_bytes=max_workspace_bytes,
                max_files=max_workspace_files,
            ):
                raise ExportWorkspaceLimitError(
                    "Render workspace exceeded its configured quota"
                )
            break
        except subprocess.TimeoutExpired:
            if quota_root is not None and _workspace_exceeds_limit(
                quota_root,
                max_bytes=max_workspace_bytes,
                max_files=max_workspace_files,
            ):
                _terminate_process_group(process)
                process.communicate()
                raise ExportWorkspaceLimitError(
                    "Render workspace exceeded its configured quota"
                )
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _terminate_process_group(process: subprocess.Popen) -> None:
    if os.name == "nt":
        process.kill()
    else:
        os.killpg(process.pid, signal.SIGKILL)


def _workspace_exceeds_limit(
    root: Path,
    *,
    max_bytes: int | None,
    max_files: int | None,
) -> bool:
    """Bounded scan that does not follow symlinks outside the job directory."""
    total_bytes = 0
    total_files = 0
    try:
        for current_root, directories, filenames in os.walk(root, followlinks=False):
            directories[:] = [
                name
                for name in directories
                if not (Path(current_root) / name).is_symlink()
            ]
            for filename in filenames:
                total_files += 1
                if max_files is not None and total_files > max_files:
                    return True
                try:
                    total_bytes += os.stat(
                        Path(current_root) / filename, follow_symlinks=False
                    ).st_size
                except OSError:
                    continue
                if max_bytes is not None and total_bytes > max_bytes:
                    return True
    except OSError:
        return True
    return False


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
                [
                    ffmpeg_bin,
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_list),
                    "-c",
                    "copy",
                    str(output),
                    "-y",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            concat_list.unlink(missing_ok=True)
            if result.returncode == 0 and output.exists():
                logger.info(
                    "手动合并部分视频: %d 分片 → %s (%.1f MB)",
                    len(mp4s),
                    output.name,
                    output.stat().st_size / 1e6,
                )
                return {
                    "type": "mp4",
                    "filename": output.name,
                    "size_bytes": output.stat().st_size,
                }
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

    data: dict = {
        "job_id": job_id,
        "status": status,
        "progress_pct": progress,
        "updated_at": time.time(),
    }
    if artifacts is not None:
        data["artifacts"] = artifacts
    if error is not None:
        data["error_log"] = error
    r.setex(f"manim:job:{job_id}", 86400, json.dumps(data))


def _try_update_redis_status(r, job_id: str, status: str, **kwargs) -> None:
    """Publish best-effort progress without making Redis a render dependency."""
    try:
        _update_redis_status(r, job_id, status, **kwargs)
    except Exception:
        logger.warning("导出状态 Redis 同步失败: job=%s status=%s", job_id, status)


async def _update_db_export_status(
    job_id: str,
    status: str,
    *,
    error_log: str = "",
    artifacts: list[dict] | None = None,
    progress: float | None = None,
    retryable_failure: bool = True,
    error_class: str = "export_failed",
    engine=None,
) -> bool:
    """同步导出状态到 DB（供没有 Redis 时回退）。

    Args:
        engine: 可选。导出线程内传入独立 engine（模块级连接池绑定主事件循环，
            跨 loop 使用会抛 InternalClientError）；主事件循环调用时省略。
    """
    try:
        from db.models import ExportJobAttempt, ExportJobModel

        jid = uuid.UUID(job_id)

        async def apply_status(session) -> bool:
            from datetime import datetime, timezone

            job = await session.get(ExportJobModel, jid)
            if job is None or (job.status == "cancelled" and status != "cancelled"):
                return False
            job.status = status
            job.worker_id = None
            job.lease_expires_at = None
            if error_log:
                job.error_log = error_log
            if artifacts is not None:
                job.artifacts = artifacts
            if progress is not None:
                job.progress_pct = progress
            if status in {"completed", "failed", "cancelled"}:
                job.completed_at = datetime.now(timezone.utc)
                job.next_attempt_at = None
                if status == "failed":
                    job.failure_retryable = retryable_failure
                await session.execute(
                    update(ExportJobAttempt)
                    .where(
                        ExportJobAttempt.job_id == jid,
                        ExportJobAttempt.status == "rendering",
                    )
                    .values(
                        status=status,
                        finished_at=job.completed_at,
                        error_class=error_class if status == "failed" else None,
                    )
                )
            await session.commit()
            return True

        if engine is not None:
            from sqlalchemy.ext.asyncio import AsyncSession

            async with AsyncSession(engine) as session:
                return await apply_status(session)
        else:
            from db.database import async_session_factory

            async with async_session_factory() as session:
                return await apply_status(session)
    except Exception:
        logger.warning("导出状态 DB 同步失败")
        return False


# ============================================================================
# 查询导出状态
# ============================================================================


@router.get("/export/{job_id}")
async def get_export_status(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
) -> dict:
    """查询导出任务状态。先查 Redis（实时进度），再查 DB（持久记录）。"""
    jid = uuid.UUID(job_id) if _is_uuid(job_id) else None
    authorized_job = None
    if current_user is not None:
        if jid is None:
            raise HTTPException(status_code=404, detail="Export job not found")
        authorized_job = await _owned_export_job(session, jid, current_user)
        if authorized_job is None:
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
                "error_log": _public_export_error(data.get("error_log")),
                "duration_ms": None,
                "total_frames": None,
                "next_attempt_at": None,
                "source_version_id": _source_version_ref(authorized_job),
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
                    job = authorized_job or await _owned_export_job(
                        session, jid, current_user
                    )
                    if job:
                        job.status = "completed"
                        job.progress_pct = 100
                        job.artifacts = artifacts
                        await session.commit()

            return result

    # 2. 回退到 DB 查询
    if jid:
        job = authorized_job or await _owned_export_job(session, jid, current_user)
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
                "error_log": _public_export_error(job.error_log),
                "duration_ms": None,
                "total_frames": None,
                "next_attempt_at": (
                    job.next_attempt_at.isoformat()
                    if isinstance(job.next_attempt_at, datetime)
                    else None
                ),
                "source_version_id": _source_version_ref(job),
            }

    raise HTTPException(status_code=404, detail="Export job not found")


def _public_export_error(error_log: object) -> str | None:
    """Never expose persisted worker diagnostics through the API boundary."""
    if not error_log:
        return None
    from services.redaction import public_failure_message

    return public_failure_message("render")


# ============================================================================
# 下载产物
# ============================================================================


@router.get("/export/{job_id}/download/{filename}")
async def download_artifact(
    job_id: str,
    filename: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
):
    """下载导出的产物文件。

    搜索顺序：
    1. settings.export_dir / job_id（本地开发）
    2. /app/data/exports / job_id（Docker 共享卷）
    3. 递归搜索 mp4 文件（Manim 会创建视频子目录）
    """
    jid = uuid.UUID(job_id) if _is_uuid(job_id) else None
    job = (
        await _owned_export_job(session, jid, current_user)
        if jid is not None
        else None
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    artifact = (
        next(
            (
                item
                for item in (job.artifacts or [])
                if item.get("filename") == filename
            ),
            None,
        )
        if job is not None
        else None
    )
    if artifact and artifact.get("storage_key"):
        from services.artifact_store import get_artifact_store

        url = await get_artifact_store().presigned_get_url(artifact["storage_key"])
        if url:
            return RedirectResponse(url=url, status_code=307)

    settings = get_settings()
    export_dir = Path(settings.export_dir) / job_id

    # 候选搜索目录
    search_dirs = [
        export_dir,
        Path("/app/data/exports") / job_id,  # Docker 共享卷
        Path("data/exports") / job_id,  # 相对路径回退
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
