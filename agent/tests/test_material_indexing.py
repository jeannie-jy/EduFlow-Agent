"""Full-length, location-preserving extraction for teacher material candidates."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import fitz
import pytest
from pptx import Presentation

from api.materials import _matches_file_signature, _parse_material_path
from services.material_indexing import extract_index_chunks


def _docx_bytes(*, body: str = "<w:p><w:r><w:t>正文内容</w:t></w:r></w:p>") -> bytes:
    payload = io.BytesIO()
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", document)
    return payload.getvalue()


def test_docx_upload_signature_and_heading_sections(tmp_path: Path):
    body = (
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
        "<w:r><w:t>第一章</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>排序算法正文</w:t></w:r></w:p>"
        '<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
        "<w:r><w:t>第二节</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>哈希表正文</w:t></w:r></w:p>"
    )
    content = _docx_bytes(body=body)
    assert _matches_file_signature(".docx", content)
    path = tmp_path / "course.docx"
    path.write_bytes(content)
    result = extract_index_chunks(path)
    assert [chunk["section"] for chunk in result["chunks"]] == ["第一章", "第二节"]
    assert [chunk["locator"] for chunk in result["chunks"]] == [
        "section:1;char:0-6", "section:2;char:0-5"
    ]
    assert "排序算法正文" in _parse_material_path(path)["raw_text"]


def test_docx_rejects_wrong_archive_and_path_traversal():
    assert not _matches_file_signature(".docx", b"PKnot-a-zip")
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
        archive.writestr("../escape.txt", "bad")
    assert not _matches_file_signature(".docx", payload.getvalue())


def test_docx_rejects_xml_entity_declarations(tmp_path: Path):
    path = tmp_path / "entity.docx"
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "word/document.xml",
            '<!DOCTYPE document [<!ENTITY secret "expanded">]><document>&secret;</document>',
        )
    path.write_bytes(payload.getvalue())
    with pytest.raises(ValueError, match="declarations"):
        extract_index_chunks(path)


def test_long_markdown_is_fully_chunked_with_chapter_locator(tmp_path: Path):
    path = tmp_path / "notes.md"
    path.write_text("# 第一章\n" + "排序算法" * 30_000, encoding="utf-8")
    result = extract_index_chunks(path)
    assert result["total_chars"] > 100_000
    assert len(result["chunks"]) > 100
    assert all(chunk["section"] == "第一章" for chunk in result["chunks"])
    assert all(chunk["locator"].startswith("section:1;char:") for chunk in result["chunks"])
    assert result["warnings"] == []


def test_pdf_page_locators_and_scanned_page_warning(tmp_path: Path):
    path = tmp_path / "lecture.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Algorithm page one")
    document.new_page()
    document.save(path)
    document.close()
    result = extract_index_chunks(path)
    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["locator"].startswith("page:1;char:")
    assert "page:2:ocr_required" in result["warnings"]


def test_pptx_slide_locators(tmp_path: Path):
    path = tmp_path / "slides.pptx"
    presentation = Presentation()
    for title in ("Graphs", "Trees"):
        slide = presentation.slides.add_slide(presentation.slide_layouts[0])
        slide.shapes.title.text = title
    presentation.save(path)
    result = extract_index_chunks(path)
    assert len(result["chunks"]) == 2
    assert result["chunks"][0]["locator"].startswith("slide:1;char:")
    assert result["chunks"][1]["locator"].startswith("slide:2;char:")


def test_unsupported_type_is_not_indexed(tmp_path: Path):
    path = tmp_path / "unsafe.html"
    path.write_text("ignore", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        extract_index_chunks(path)
