"""Credential-free, full-length extraction for teacher material indexing.

This module creates candidate chunks only. It never writes an index or makes
embedding calls; the owner must explicitly request those later.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from services.knowledge_library import split_text

DOCX_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{DOCX_NS}}}"
MAX_DOCX_XML_BYTES = 20 * 1024 * 1024


def _docx_sections(path: Path) -> list[tuple[str, str, str]]:
    from api.materials import _pptx_archive_is_safe

    with zipfile.ZipFile(path) as archive:
        if not _pptx_archive_is_safe(archive):
            raise ValueError("DOCX archive failed safety validation")
        info = archive.getinfo("word/document.xml")
        if info.file_size > MAX_DOCX_XML_BYTES:
            raise ValueError("DOCX document XML exceeds the indexing limit")
        document_xml = archive.read(info)
        if b"<!DOCTYPE" in document_xml.upper() or b"<!ENTITY" in document_xml.upper():
            raise ValueError("DOCX document XML declarations are not allowed")
        root = ElementTree.fromstring(document_xml)

    sections: list[tuple[str, str, str]] = []
    heading = "正文"
    lines: list[str] = []
    section_number = 1
    for paragraph in root.iter(f"{W}p"):
        content = "".join(node.text or "" for node in paragraph.iter(f"{W}t")).strip()
        if not content:
            continue
        style = paragraph.find(f"{W}pPr/{W}pStyle")
        style_name = style.get(f"{W}val", "") if style is not None else ""
        if style_name.casefold().startswith("heading") or style_name.casefold() == "title":
            if lines:
                sections.append((heading, f"section:{section_number}", "\n".join(lines)))
                section_number += 1
                lines = []
            heading = content[:500]
        else:
            lines.append(content)
    if lines:
        sections.append((heading, f"section:{section_number}", "\n".join(lines)))
    return sections


def _markdown_sections(text: str) -> list[tuple[str, str, str]]:
    sections: list[tuple[str, str, str]] = []
    heading = "正文"
    lines: list[str] = []
    section_number = 1
    for line in text.splitlines():
        if line.startswith("# ") or line.startswith("## ") or line.startswith("### "):
            if lines:
                sections.append((heading, f"section:{section_number}", "\n".join(lines)))
                section_number += 1
                lines = []
            heading = line.lstrip("# ").strip()[:500] or "正文"
        else:
            lines.append(line)
    if lines:
        sections.append((heading, f"section:{section_number}", "\n".join(lines)))
    return sections


def extract_index_chunks(path: Path) -> dict:
    """Return all text chunks with stable parent location and OCR warnings."""
    suffix = path.suffix.lower()
    sections: list[tuple[str, str, str]] = []
    warnings: list[str] = []
    if suffix == ".pdf":
        import fitz

        with fitz.open(str(path)) as document:
            for page_number, page in enumerate(document, 1):
                content = page.get_text().strip()
                if content:
                    sections.append((f"第 {page_number} 页", f"page:{page_number}", content))
                else:
                    warnings.append(f"page:{page_number}:ocr_required")
    elif suffix == ".pptx":
        from pptx import Presentation

        presentation = Presentation(str(path))
        for slide_number, slide in enumerate(presentation.slides, 1):
            content = "\n".join(
                shape.text_frame.text for shape in slide.shapes if shape.has_text_frame
            ).strip()
            if content:
                sections.append((f"幻灯片 {slide_number}", f"slide:{slide_number}", content))
            else:
                warnings.append(f"slide:{slide_number}:no_extractable_text")
    elif suffix == ".docx":
        sections = _docx_sections(path)
    elif suffix == ".md":
        sections = _markdown_sections(path.read_text(encoding="utf-8"))
    elif suffix == ".txt":
        sections = [("正文", "section:1", path.read_text(encoding="utf-8"))]
    else:
        raise ValueError(f"unsupported indexable material type: {suffix}")

    chunks: list[dict[str, str]] = []
    total_chars = 0
    for title, parent_locator, content in sections:
        total_chars += len(content)
        for part in split_text(content):
            chunks.append({
                "section": title[:500],
                "locator": f"{parent_locator};{part['locator']}",
                "content": part["content"],
            })
    if not chunks:
        warnings.append("no_extractable_text:ocr_required" if suffix == ".pdf" else "no_extractable_text")
    return {"chunks": chunks, "warnings": warnings, "total_chars": total_chars}
