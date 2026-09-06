"""素材 API 路由。

POST   /api/materials/upload                      上传课件文件
POST   /api/materials/{id}/parse                  解析为结构化内容
GET    /api/materials/{id}/preview                预览解析结果
"""

from __future__ import annotations

import asyncio
import io
import logging
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import get_session
from db.models import Material, User
from services.artifact_store import get_artifact_store
from services.audit import record_audit

from .auth import get_current_user, is_admin, require_editor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/materials", tags=["materials"])

# 文件类型白名单（扩展名 → MIME）
ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".py": "text/x-python",
    ".c": "text/x-csrc",
    ".java": "text/x-java-source",
    ".cpp": "text/x-c++src",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
MAX_PPTX_MEMBERS = 5_000
MAX_PPTX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_PPTX_COMPRESSION_RATIO = 200


@router.post("/upload", status_code=201)
async def upload_material(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
    _editor: Annotated[User | None, Depends(require_editor)] = None,
) -> dict:
    """上传课件文件。

    支持: PDF, PPTX, Markdown, TXT, Python/C/Java/C++ 代码。
    最大: 50 MB。
    """
    settings = get_settings()

    # 文件名安全检查
    original_name = file.filename or "unknown"
    suffix = Path(original_name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {suffix}。支持: {', '.join(ALLOWED_EXTENSIONS.keys())}",
        )

    # Read incrementally so an oversized request cannot be fully buffered first.
    contents = await _read_upload_bounded(file, settings.upload_max_size_bytes)
    if not _matches_file_signature(suffix, contents):
        raise HTTPException(
            status_code=400, detail="文件内容与扩展名不匹配或文件已损坏"
        )

    material_id = uuid.uuid4()
    safe_filename = f"uploaded_{material_id.hex[:8]}{suffix}"
    storage_key = f"materials/{material_id}/source{suffix}"
    store = get_artifact_store()
    with tempfile.TemporaryDirectory(prefix="eduflow-material-") as temp_dir:
        file_path = Path(temp_dir) / safe_filename
        await asyncio.to_thread(file_path.write_bytes, contents)
        await store.put_file(storage_key, file_path, ALLOWED_EXTENSIONS[suffix])

    material = Material(
        id=material_id,
        owner_id=current_user.id if current_user is not None else None,
        original_filename=original_name[:500],
        stored_filename=safe_filename,
        storage_key=storage_key,
        media_type=ALLOWED_EXTENSIONS[suffix],
        size_bytes=len(contents),
        status="uploaded",
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.material_retention_days),
    )
    session.add(material)
    record_audit(
        session,
        action="material.upload",
        resource_type="material",
        resource_id=str(material_id),
        actor_id=current_user.id if current_user is not None else None,
        details={"size_bytes": len(contents), "media_type": ALLOWED_EXTENSIONS[suffix]},
    )
    try:
        await session.flush()
        await session.commit()
    except Exception:
        # Object stores are not transactional; compensate if metadata cannot persist.
        await session.rollback()
        try:
            await store.delete(storage_key)
        except Exception:
            logger.exception("material upload compensation failed: key=%s", storage_key)
        raise

    logger.info(
        "文件上传: id=%s | name=%s | size=%d | type=%s",
        material_id,
        original_name,
        len(contents),
        suffix,
    )

    return {
        "id": str(material_id),
        "filename": original_name,
        "type": suffix.lstrip("."),
        "size_bytes": len(contents),
    }


def parse_material_file(material_id: str) -> dict | None:
    """解析已上传素材文件，返回 {topics, raw_text}。找不到文件返回 None。

    供 parse 端点与生成流程复用（file_upload 素材接线）。
    """
    settings = get_settings()
    upload_dir = settings.upload_dir / material_id
    if not upload_dir.exists():
        return None

    files = list(upload_dir.glob("uploaded_*"))
    if not files:
        return None

    return _parse_material_path(files[0])


def _parse_material_path(file_path: Path) -> dict:
    """Parse one trusted local copy of an uploaded material."""
    suffix = file_path.suffix.lower()

    raw_text = ""
    topics: list[str] = []
    if suffix == ".pdf":
        raw_text, topics = _parse_pdf(file_path)
    elif suffix == ".pptx":
        raw_text, topics = _parse_pptx(file_path)
    elif suffix in (".txt", ".md", ".py", ".c", ".java", ".cpp"):
        raw_text = file_path.read_text(encoding="utf-8")
        topics = _extract_topics_from_text(raw_text)
    else:
        raw_text = f"Unsupported format: {suffix}"

    return _validate_parsed_result({"topics": topics, "raw_text": raw_text[:100000]})


def _validate_parsed_result(value: object) -> dict[str, object]:
    """Validate the credential-free parser result before database persistence."""
    if not isinstance(value, dict):
        raise ValueError("Material parse result must be an object")
    raw_text = value.get("raw_text")
    topics = value.get("topics")
    if not isinstance(raw_text, str) or len(raw_text) > 100_000:
        raise ValueError("Material raw text exceeds its schema boundary")
    if (
        not isinstance(topics, list)
        or len(topics) > 100
        or any(not isinstance(topic, str) or len(topic) > 200 for topic in topics)
    ):
        raise ValueError("Material topics exceed their schema boundary")
    return {"topics": topics, "raw_text": raw_text}


async def _copy_material_to(material: Material, destination: Path) -> None:
    """Materialize an object-store source, with a bounded legacy local fallback."""
    if material.storage_key:
        await get_artifact_store().get_file(material.storage_key, destination)
        return

    settings = get_settings()
    root = settings.upload_dir.resolve()
    legacy = (root / str(material.id) / material.stored_filename).resolve()
    if not legacy.is_relative_to(root) or not legacy.is_file():
        raise FileNotFoundError(str(material.id))
    await asyncio.to_thread(shutil.copy2, legacy, destination)


async def parse_material_record(material: Material) -> dict:
    """Download a material to an isolated temp directory and parse off-loop."""
    suffix = Path(material.stored_filename).suffix.lower()
    with tempfile.TemporaryDirectory(prefix="eduflow-parse-") as temp_dir:
        local_path = Path(temp_dir) / f"source{suffix}"
        await _copy_material_to(material, local_path)
        return await asyncio.to_thread(_parse_material_path, local_path)


@router.post("/{material_id}/parse", status_code=202)
async def parse_material(
    material_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
    _editor: Annotated[User | None, Depends(require_editor)] = None,
) -> dict:
    """Queue durable parsing; CPU-heavy parsing never runs in the API process."""
    from sqlalchemy import select

    from db.models import BackgroundJob

    material = await _authorize_material(material_id, current_user, session)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    if material.status == "parsed" and material.parsed_result is not None:
        return {
            "id": material_id,
            "status": "done",
            "job_id": None,
            "status_url": None,
            "parsed_result": material.parsed_result,
        }

    existing = await session.scalar(
        select(BackgroundJob).where(
            BackgroundJob.kind == "material_parse",
            BackgroundJob.idempotency_key == material_id,
        )
    )
    if existing is None:
        existing = BackgroundJob(
            id=uuid.uuid4(),
            project_id=None,
            owner_id=material.owner_id,
            kind="material_parse",
            idempotency_key=material_id,
            payload={"material_id": material_id},
            status="queued",
        )
        session.add(existing)
        material.status = "parse_queued"
        record_audit(
            session,
            action="material.parse_queued",
            resource_type="material",
            resource_id=material_id,
            actor_id=current_user.id if current_user is not None else None,
            details={"job_id": str(existing.id)},
        )
        await session.flush()
    elif (
        existing.status == "cancelled"
        and existing.attempt_count < get_settings().task_worker_max_attempts
    ):
        existing.status = "queued"
        existing.completed_at = None
        existing.error_class = None
        existing.next_attempt_at = None
        material.status = "parse_queued"

    logger.info("文件解析已排队: material=%s | job=%s", material_id, existing.id)

    return {
        "id": material_id,
        "status": existing.status,
        "job_id": str(existing.id),
        "status_url": f"/api/background-jobs/{existing.id}",
        "parsed_result": None,
    }


@router.get("/{material_id}/preview")
async def preview_material(
    material_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
) -> dict:
    """预览文件解析结果（只读，不触发重新解析）。"""
    material = await _authorize_material(material_id, current_user, session)
    if material is None:
        settings = get_settings()
        upload_dir = settings.upload_dir / material_id
        files = list(upload_dir.glob("uploaded_*")) if upload_dir.exists() else []
        if not files:
            raise HTTPException(status_code=404, detail="Material not found")
        file_path = files[0]
        filename = file_path.name
        suffix = file_path.suffix.lower()
        size_bytes = file_path.stat().st_size
        preview_text = (
            file_path.read_text(encoding="utf-8")[:5000]
            if suffix in (".txt", ".md", ".py", ".c", ".java", ".cpp")
            else f"Binary file: {filename} ({suffix})"
        )
    else:
        filename = material.original_filename
        suffix = Path(material.stored_filename).suffix.lower()
        size_bytes = material.size_bytes
        parsed = material.parsed_result or {}
        preview_text = str(parsed.get("raw_text", ""))[:5000]
        if not preview_text:
            preview_text = (
                f"{suffix.lstrip('.').upper()} file; parse it to preview text"
            )

    return {
        "id": material_id,
        "filename": filename,
        "type": suffix.lstrip("."),
        "size_bytes": size_bytes,
        "preview": preview_text,
    }


@router.delete("/{material_id}", status_code=204)
async def delete_material(
    material_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
    _editor: Annotated[User | None, Depends(require_editor)] = None,
) -> None:
    """Delete owned material metadata and its bounded storage directory."""
    material = await _authorize_material(material_id, current_user, session)
    settings = get_settings()
    if material is not None and material.storage_key:
        await get_artifact_store().delete(material.storage_key)
    else:
        root = settings.upload_dir.resolve()
        target = (root / material_id).resolve()
        if not target.is_relative_to(root):
            raise HTTPException(status_code=403, detail="Access denied")
        if target.exists():
            shutil.rmtree(target)
    if material is not None:
        await session.delete(material)
    record_audit(
        session,
        action="material.delete",
        resource_type="material",
        resource_id=material_id,
        actor_id=current_user.id if current_user is not None else None,
    )


async def _authorize_material(
    material_id: str,
    current_user: User | None,
    session: AsyncSession,
) -> Material | None:
    """Return metadata for the owner; anonymous compatibility mode uses legacy files."""
    try:
        material_uuid = uuid.UUID(material_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Material not found") from exc
    material = await session.get(Material, material_uuid)
    if current_user is None or is_admin(current_user):
        return material
    if material is None or material.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


async def _read_upload_bounded(file: UploadFile, max_bytes: int) -> bytes:
    contents = bytearray()
    while True:
        chunk = await file.read(min(1024 * 1024, max_bytes + 1))
        if not chunk:
            return bytes(contents)
        contents.extend(chunk)
        if len(contents) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"文件过大（最大 {max_bytes // 1048576} MB）",
            )


def _matches_file_signature(suffix: str, contents: bytes) -> bool:
    if not contents:
        return False
    if suffix == ".pdf":
        return contents.startswith(b"%PDF-")
    if suffix == ".pptx":
        try:
            with zipfile.ZipFile(io.BytesIO(contents)) as archive:
                if not _pptx_archive_is_safe(archive):
                    return False
                names = set(archive.namelist())
            return "[Content_Types].xml" in names and "ppt/presentation.xml" in names
        except zipfile.BadZipFile:
            return False
    if b"\x00" in contents[:8192]:
        return False
    try:
        contents.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _pptx_archive_is_safe(archive: zipfile.ZipFile) -> bool:
    """Reject traversal, encrypted entries and bounded ZIP-bomb patterns."""
    infos = archive.infolist()
    if len(infos) > MAX_PPTX_MEMBERS:
        return False
    total_uncompressed = 0
    for info in infos:
        normalized = info.filename.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        if normalized.startswith("/") or ".." in parts or info.flag_bits & 0x1:
            return False
        total_uncompressed += max(info.file_size, 0)
        if total_uncompressed > MAX_PPTX_UNCOMPRESSED_BYTES:
            return False
        if info.file_size > 0:
            if info.compress_size <= 0:
                return False
            if info.file_size / info.compress_size > MAX_PPTX_COMPRESSION_RATIO:
                return False
    return True


# ============================================================================
# 解析器实现
# ============================================================================


def _parse_pdf(file_path: Path) -> tuple[str, list[str]]:
    """解析 PDF 文件，提取文本和候选主题。"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ("PDF 解析器未安装 (pip install PyMuPDF)", [])

    doc = fitz.open(str(file_path))
    pages_text = []
    for page in doc:
        pages_text.append(page.get_text())

    full_text = "\n".join(pages_text)
    topics = _extract_topics_from_text(full_text)
    doc.close()
    return full_text, topics


def _parse_pptx(file_path: Path) -> tuple[str, list[str]]:
    """解析 PPTX 文件。"""
    try:
        from pptx import Presentation
    except ImportError:
        return ("PPTX 解析器未安装 (pip install python-pptx)", [])

    prs = Presentation(str(file_path))
    slides_text = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                slides_text.append(shape.text_frame.text)

    full_text = "\n---\n".join(slides_text)
    topics = _extract_topics_from_text(full_text)
    return full_text, topics


def _extract_topics_from_text(text: str) -> list[str]:
    """从文本中提取候选知识主题（基于 CS 关键词匹配）。

    MVP: 简单的关键词密度匹配。
    完整版: 使用 LLM 的 extract_concepts Tool。
    """
    if not text.strip():
        return []

    # CS 关键词库
    cs_keywords = [
        # 数据结构
        "数组",
        "链表",
        "栈",
        "队列",
        "哈希表",
        "堆",
        "二叉树",
        "AVL",
        "红黑树",
        "B树",
        "B+树",
        "图",
        "邻接表",
        "邻接矩阵",
        # 算法
        "排序",
        "冒泡",
        "快速排序",
        "归并排序",
        "二分",
        "递归",
        "动态规划",
        "贪心",
        "BFS",
        "DFS",
        "Dijkstra",
        "最小生成树",
        "拓扑排序",
        "最短路径",
        "松弛操作",
        # 操作系统
        "进程",
        "线程",
        "调度",
        "同步",
        "互斥",
        "死锁",
        "分页",
        "缓存",
        "虚拟内存",
        "TLB",
        "缺页",
        "信号量",
        "管程",
        # 网络
        "TCP",
        "UDP",
        "IP",
        "HTTP",
        "DNS",
        "路由",
        "拥塞控制",
        "三次握手",
        "四次挥手",
        "OSI",
        "子网",
        # 数据库
        "索引",
        "事务",
        "锁",
        "隔离级别",
        "B+树",
        "查询优化",
        "ACID",
        "连接",
        "SQL",
        # 软件工程
        "设计模式",
        "架构",
        "微服务",
        "CI/CD",
        "测试",
        "敏捷",
    ]

    # 计算每个关键词在文本中出现的次数
    scored = []
    for kw in cs_keywords:
        count = text.count(kw)
        if count > 0:
            scored.append((kw, count))

    # 按出现频率排序，取前 10
    scored.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in scored[:10]]
