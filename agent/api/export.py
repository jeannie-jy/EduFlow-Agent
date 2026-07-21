"""导出 API 路由。

POST   /api/projects/{id}/export/manim          创建视频导出任务
GET    /api/export/{job_id}                     查询导出状态
GET    /api/export/{job_id}/download/{filename} 下载产物
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
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

    return {
        "job_id": str(job_id),
        "status": "queued",
    }


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
                        await session.flush()

            return result

    # 2. 回退到 DB 查询
    if jid:
        job = await session.get(ExportJobModel, jid)
        if job:
            return {
                "job_id": str(job.id),
                "status": job.status,
                "progress_pct": job.progress_pct or 0,
                "artifacts": job.artifacts,
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
