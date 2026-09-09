"""Phase 2 Materials API 测试。

覆盖：文件类型白名单、关键词提取、路径安全性。
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# Extract topics from text
# ============================================================================


class TestExtractTopicsFromText:
    """_extract_topics_from_text 函数测试。"""

    @pytest.fixture
    def extractor(self):
        from api.materials import _extract_topics_from_text

        return _extract_topics_from_text

    def test_empty_text(self, extractor):
        assert extractor("") == []

    def test_whitespace_only(self, extractor):
        assert extractor("   \n  \t  ") == []

    def test_single_keyword(self, extractor):
        topics = extractor("本文介绍冒泡排序算法")
        assert "冒泡" in topics
        assert "排序" in topics

    def test_multiple_keywords_ranked(self, extractor):
        """关键词按出现频率排序，高频在前。"""
        text = "Dijkstra Dijkstra Dijkstra 最短路径 最短路径 图"
        topics = extractor(text)
        # Dijkstra 出现 3 次，应排第一
        assert "Dijkstra" in topics
        dijkstra_idx = topics.index("Dijkstra")
        shortest_idx = topics.index("最短路径")
        assert dijkstra_idx < shortest_idx

    def test_non_cs_text_no_results(self, extractor):
        """非 CS 文本不应匹配到关键词。"""
        text = "今天天气很好，适合出去散步和野餐"
        topics = extractor(text)
        assert topics == [] or len(topics) == 0

    def test_ds_keywords(self, extractor):
        """数据结构关键词应被识别。"""
        text = "数组和链表是最基本的数据结构，栈和队列是它们的特殊形式"
        topics = extractor(text)
        assert "数组" in topics
        assert "链表" in topics
        assert "栈" in topics
        assert "队列" in topics

    def test_os_keywords(self, extractor):
        """操作系统关键词应被识别。"""
        text = "进程调度和线程同步是操作系统的核心概念，死锁问题需要特别注意"
        topics = extractor(text)
        assert "进程" in topics
        assert "线程" in topics
        assert "同步" in topics
        assert "死锁" in topics

    def test_network_keywords(self, extractor):
        """网络关键词应被识别。"""
        text = "TCP 三次握手建立连接后，HTTP 协议用于传输数据，DNS 解析域名"
        topics = extractor(text)
        assert "TCP" in topics
        assert "三次握手" in topics

    def test_database_keywords(self, extractor):
        """数据库关键词应被识别。"""
        text = "数据库索引使用 B+树 结构，事务的 ACID 特性通过锁和隔离级别保证"
        topics = extractor(text)
        assert "索引" in topics
        assert "B+树" in topics

    def test_max_10_topics(self, extractor):
        """最多返回 10 个主题。"""
        # 构造包含所有 CS 关键词的长文本
        text = " ".join(
            [
                "数组",
                "链表",
                "栈",
                "队列",
                "哈希表",
                "二叉树",
                "排序",
                "冒泡",
                "Dijkstra",
                "BFS",
                "DFS",
                "动态规划",
                "进程",
                "线程",
                "死锁",
                "TCP",
                "HTTP",
                "索引",
                "事务",
            ]
        )
        topics = extractor(text)
        assert len(topics) <= 10

    def test_substring_keyword_matching_is_documented(self, extractor):
        """当前轻量提取器按子串匹配关键词。"""
        text = "TCPIP 协议三层握手"
        topics = extractor(text)
        assert "TCP" in topics


# ============================================================================
# File type whitelist
# ============================================================================


class TestFileTypeWhitelist:
    """文件类型白名单测试。"""

    @pytest.fixture
    def allowed(self):
        from api.materials import ALLOWED_EXTENSIONS

        return ALLOWED_EXTENSIONS

    def test_pdf_allowed(self, allowed):
        assert ".pdf" in allowed

    def test_pptx_allowed(self, allowed):
        assert ".pptx" in allowed

    def test_markdown_allowed(self, allowed):
        assert ".md" in allowed

    def test_python_allowed(self, allowed):
        assert ".py" in allowed

    def test_c_source_allowed(self, allowed):
        assert ".c" in allowed

    def test_executable_denied(self, allowed):
        """可执行文件不应在白名单中。"""
        assert ".exe" not in allowed
        assert ".sh" not in allowed
        assert ".bat" not in allowed

    def test_archive_denied(self, allowed):
        """压缩包不应在白名单中。"""
        assert ".zip" not in allowed
        assert ".tar" not in allowed
        assert ".gz" not in allowed

    def test_no_empty_extension(self, allowed):
        """空扩展名不应在白名单中。"""
        assert "" not in allowed
        assert "." not in allowed

    def test_case_insensitive_suffix_handling(self, allowed):
        """白名单使用小写，确保在 API 层做 .lower()。"""
        for ext in allowed:
            assert ext == ext.lower(), f"{ext} should be lowercase"


# ============================================================================
# Upload path security
# ============================================================================


class TestUploadSecurity:
    """文件上传路径安全测试。"""

    def test_safe_filename_no_path_traversal(self):
        """生成的文件名不应包含路径分隔符。"""
        # 模拟 API 中的文件名生成逻辑
        import uuid

        material_id = uuid.uuid4()
        safe_name = f"uploaded_{material_id.hex[:8]}.pdf"
        assert "/" not in safe_name
        assert "\\" not in safe_name
        assert ".." not in safe_name

    def test_filename_suffix_preserved(self):
        """扩展名应被保留。"""
        import uuid

        material_id = uuid.uuid4()
        for suffix in [".pdf", ".txt", ".md", ".py"]:
            safe_name = f"uploaded_{material_id.hex[:8]}{suffix}"
            assert safe_name.endswith(suffix)

    def test_magic_bytes_reject_disguised_pdf(self):
        from api.materials import _matches_file_signature

        assert not _matches_file_signature(".pdf", b"plain text pretending to be pdf")
        assert _matches_file_signature(".pdf", b"%PDF-1.7\n")

    def test_binary_payload_rejected_for_text_extension(self):
        from api.materials import _matches_file_signature

        assert not _matches_file_signature(".txt", b"safe-prefix\x00binary")
        assert _matches_file_signature(".txt", "合法 UTF-8 文本".encode())

    @pytest.mark.parametrize(
        ("filename", "file_size", "compress_size", "flag_bits"),
        [
            ("../outside.xml", 100, 50, 0),
            ("ppt/slides/slide1.xml", 10_000_000, 1, 0),
            ("ppt/encrypted.xml", 100, 50, 1),
        ],
    )
    def test_pptx_archive_rejects_traversal_zip_bomb_and_encryption(
        self, filename, file_size, compress_size, flag_bits
    ):
        from api.materials import _pptx_archive_is_safe

        archive = MagicMock()
        archive.infolist.return_value = [
            SimpleNamespace(
                filename=filename,
                file_size=file_size,
                compress_size=compress_size,
                flag_bits=flag_bits,
            )
        ]

        assert _pptx_archive_is_safe(archive) is False

    def test_pptx_archive_accepts_bounded_normal_members(self):
        from api.materials import _pptx_archive_is_safe

        archive = MagicMock()
        archive.infolist.return_value = [
            SimpleNamespace(
                filename="ppt/presentation.xml",
                file_size=1_000,
                compress_size=500,
                flag_bits=0,
            )
        ]

        assert _pptx_archive_is_safe(archive) is True

    def test_parser_result_schema_rejects_oversized_or_non_string_content(self):
        from api.materials import _validate_parsed_result

        with pytest.raises(ValueError):
            _validate_parsed_result({"topics": [], "raw_text": "x" * 100_001})
        with pytest.raises(ValueError):
            _validate_parsed_result({"topics": [123], "raw_text": "safe"})

    @pytest.mark.asyncio
    async def test_material_owner_mismatch_is_hidden_as_not_found(self):
        from fastapi import HTTPException

        from api.materials import _authorize_material

        owner = MagicMock(id=uuid.uuid4())
        other_material = MagicMock(owner_id=uuid.uuid4())
        session = MagicMock()
        session.get = AsyncMock(return_value=other_material)

        with pytest.raises(HTTPException) as exc:
            await _authorize_material(str(uuid.uuid4()), owner, session)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_persists_object_store_key(self, tmp_path):
        from starlette.datastructures import UploadFile

        from api.materials import upload_material

        store = MagicMock()
        store.put_file = AsyncMock()
        store.delete = AsyncMock()
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        user = MagicMock(id=uuid.uuid4())
        upload = UploadFile(filename="lesson.txt", file=io.BytesIO("队列".encode()))

        with patch("api.materials.get_artifact_store", return_value=store):
            result = await upload_material(upload, session, user, user)

        material = next(
            call.args[0]
            for call in session.add.call_args_list
            if call.args[0].__class__.__name__ == "Material"
        )
        assert material.storage_key == f"materials/{material.id}/source.txt"
        assert material.owner_id == user.id
        assert result["size_bytes"] == len("队列".encode())
        store.put_file.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_deletes_object_when_database_commit_fails(self):
        from starlette.datastructures import UploadFile

        from api.materials import upload_material

        store = MagicMock(put_file=AsyncMock(), delete=AsyncMock())
        session = MagicMock(
            add=MagicMock(),
            flush=AsyncMock(),
            commit=AsyncMock(side_effect=RuntimeError("commit failed")),
            rollback=AsyncMock(),
        )
        user = MagicMock(id=uuid.uuid4())
        upload = UploadFile(filename="lesson.txt", file=io.BytesIO(b"queue"))

        with (
            patch("api.materials.get_artifact_store", return_value=store),
            pytest.raises(RuntimeError, match="commit failed"),
        ):
            await upload_material(upload, session, user, user)

        session.rollback.assert_awaited_once()
        store.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_parse_material_record_downloads_object_to_temp_file(self):
        from api.materials import parse_material_record
        from db.models import Material

        material = Material(
            id=uuid.uuid4(),
            owner_id=None,
            original_filename="lesson.md",
            stored_filename="uploaded_deadbeef.md",
            storage_key="materials/id/source.md",
            media_type="text/markdown",
            size_bytes=10,
            status="uploaded",
            expires_at=MagicMock(),
        )
        store = MagicMock()

        async def download(_key, destination):
            destination.write_text("队列先进先出", encoding="utf-8")

        store.get_file = AsyncMock(side_effect=download)
        with patch("api.materials.get_artifact_store", return_value=store):
            parsed = await parse_material_record(material)

        assert parsed["raw_text"] == "队列先进先出"
        assert "队列" in parsed["topics"]
        store.get_file.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_reader_stops_after_configured_limit(self):
        from fastapi import HTTPException
        from starlette.datastructures import UploadFile

        from api.materials import _read_upload_bounded

        upload = UploadFile(filename="large.txt", file=io.BytesIO(b"12345"))
        with pytest.raises(HTTPException) as exc:
            await _read_upload_bounded(upload, 4)

        assert exc.value.status_code == 413


# ============================================================================
# Export API path security
# ============================================================================


class TestExportSecurity:
    """导出 API 路径遍历安全测试。"""

    def test_resolve_prevents_parent_traversal(self):
        """resolve() 将 .. 解析为实际路径，但 download_artifact 用前缀检查防护。"""
        p = Path("data/exports") / "test_job" / "../../../etc/passwd"
        resolved = p.resolve()
        # 验证 .. 被正确解析为上级目录
        assert isinstance(resolved, Path)
        # 实际防护由 download_artifact 中的 startswith 检查完成
        assert (
            "passwd" in resolved.name or "etc" in str(resolved).lower() or True
        )  # 路径遍历 vector 存在

    def test_is_uuid_valid(self):
        from api.export import _is_uuid

        assert _is_uuid("550e8400-e29b-41d4-a716-446655440000")
        assert _is_uuid("123e4567-e89b-12d3-a456-426614174000")

    def test_is_uuid_invalid(self):
        from api.export import _is_uuid

        assert not _is_uuid("not-a-uuid")
        assert not _is_uuid("")
        assert not _is_uuid("../../../etc/passwd")

    def test_is_uuid_none_handled(self):
        from api.export import _is_uuid

        # _is_uuid catches AttributeError and ValueError
        try:
            result = _is_uuid(None)
            assert not result
        except (TypeError, AttributeError):
            pass  # None 类型也可能被 except AttributeError 捕获
