"""素材 API 路由。

POST   /api/materials/upload                      上传课件文件
POST   /api/materials/{id}/parse                  解析为结构化内容
GET    /api/materials/{id}/preview                预览解析结果
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import get_session

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


@router.post("/upload", status_code=201)
async def upload_material(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
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

    # 大小检查
    contents = await file.read()
    if len(contents) > settings.upload_max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大（最大 {settings.upload_max_size_bytes // 1048576} MB）",
        )

    material_id = uuid.uuid4()
    upload_dir = settings.upload_dir / str(material_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 保存文件
    safe_filename = f"uploaded_{material_id.hex[:8]}{suffix}"
    file_path = upload_dir / safe_filename
    file_path.write_bytes(contents)

    # 持久化到 DB
    from db.models import Project as ProjectModel

    # TODO: 创建 SourceMaterial ORM 模型后替换为 SourceMaterial 表写入
    # 当前阶段存储文件即可，parse 时读取

    logger.info("文件上传: id=%s | name=%s | size=%d | type=%s",
                material_id, original_name, len(contents), suffix)

    return {
        "id": str(material_id),
        "filename": original_name,
        "type": suffix.lstrip("."),
        "size_bytes": len(contents),
    }


@router.post("/{material_id}/parse")
async def parse_material(material_id: str) -> dict:
    """解析上传的课件文件，提取结构化内容。"""
    settings = get_settings()
    upload_dir = settings.upload_dir / material_id

    if not upload_dir.exists():
        raise HTTPException(status_code=404, detail="Material not found")

    # 找到上传的文件
    files = list(upload_dir.glob("uploaded_*"))
    if not files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = files[0]
    suffix = file_path.suffix.lower()

    raw_text = ""
    topics: list[str] = []

    try:
        if suffix == ".pdf":
            raw_text, topics = _parse_pdf(file_path)
        elif suffix == ".pptx":
            raw_text, topics = _parse_pptx(file_path)
        elif suffix in (".txt", ".md", ".py", ".c", ".java", ".cpp"):
            raw_text = file_path.read_text(encoding="utf-8")
            topics = _extract_topics_from_text(raw_text)
        else:
            raw_text = f"Unsupported format: {suffix}"

    except Exception as exc:
        logger.exception("文件解析失败: %s", file_path)
        raise HTTPException(status_code=500, detail=f"解析失败: {exc}")

    logger.info("文件解析完成: id=%s | topics=%d | text_len=%d",
                material_id, len(topics), len(raw_text))

    return {
        "id": material_id,
        "status": "done",
        "parsed_result": {
            "topics": topics,
            "raw_text": raw_text[:100000],  # 截断到 100K 字符
        },
    }


@router.get("/{material_id}/preview")
async def preview_material(material_id: str) -> dict:
    """预览文件解析结果（只读，不触发重新解析）。"""
    settings = get_settings()
    upload_dir = settings.upload_dir / material_id

    if not upload_dir.exists():
        raise HTTPException(status_code=404, detail="Material not found")

    files = list(upload_dir.glob("uploaded_*"))
    if not files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = files[0]
    suffix = file_path.suffix.lower()

    preview_text = ""
    if suffix in (".txt", ".md", ".py", ".c", ".java", ".cpp"):
        preview_text = file_path.read_text(encoding="utf-8")[:5000]
    else:
        preview_text = f"Binary file: {file_path.name} ({suffix})"

    return {
        "id": material_id,
        "filename": file_path.name,
        "type": suffix.lstrip("."),
        "size_bytes": file_path.stat().st_size,
        "preview": preview_text,
    }


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
        "数组", "链表", "栈", "队列", "哈希表", "堆", "二叉树", "AVL",
        "红黑树", "B树", "B+树", "图", "邻接表", "邻接矩阵",
        # 算法
        "排序", "冒泡", "快速排序", "归并排序", "二分", "递归", "动态规划",
        "贪心", "BFS", "DFS", "Dijkstra", "最小生成树", "拓扑排序",
        "最短路径", "松弛操作",
        # 操作系统
        "进程", "线程", "调度", "同步", "互斥", "死锁", "分页", "缓存",
        "虚拟内存", "TLB", "缺页", "信号量", "管程",
        # 网络
        "TCP", "UDP", "IP", "HTTP", "DNS", "路由", "拥塞控制", "三次握手",
        "四次挥手", "OSI", "子网",
        # 数据库
        "索引", "事务", "锁", "隔离级别", "B+树", "查询优化", "ACID",
        "连接", "SQL",
        # 软件工程
        "设计模式", "架构", "微服务", "CI/CD", "测试", "敏捷",
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
