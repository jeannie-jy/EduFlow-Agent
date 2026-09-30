"""Privileged worker ↔ credential-free sandbox indexing handshake."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.material_sandbox import process_one_request
from services.task_worker import PermanentTaskError, _extract_index_via_sandbox


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", [False, True])
async def test_long_index_spool_exchange_and_integrity_rejection(tmp_path: Path, tamper: bool):
    text = "# 开始\n原创长讲义。\n" + "段落材料。" * 25_000 + "\n# 末章\n末尾独特定位词。\n"
    material = SimpleNamespace(stored_filename="lecture.md")
    settings = SimpleNamespace(
        material_sandbox_dir=tmp_path,
        material_parse_timeout_seconds=5,
        task_worker_poll_seconds=0.01,
        material_parse_result_max_bytes=4096,
        material_index_result_max_bytes=4 * 1024 * 1024,
        upload_max_size_bytes=4 * 1024 * 1024,
    )

    async def copy_fixture(_material, destination: Path) -> None:
        destination.write_text(text, encoding="utf-8")

    async def sidecar() -> None:
        for _ in range(200):
            completed = await asyncio.to_thread(process_one_request, tmp_path)
            if completed:
                if tamper:
                    spool = next(tmp_path.glob("*/index-chunks.json"))
                    data = bytearray(spool.read_bytes())
                    data[0] = ord("[")
                    spool.write_bytes(data)
                return
            await asyncio.sleep(0.01)
        raise AssertionError("sandbox request never arrived")

    job = {"job_id": str(uuid.uuid4()), "attempt_no": 1}
    with (
        patch("services.task_worker.get_settings", return_value=settings),
        patch("services.material_sandbox.get_settings", return_value=settings),
        patch("api.materials._copy_material_to", side_effect=copy_fixture),
    ):
        consumer = asyncio.create_task(sidecar())
        try:
            if tamper:
                with pytest.raises(PermanentTaskError, match="integrity check failed"):
                    await _extract_index_via_sandbox(material, job)
            else:
                result = await _extract_index_via_sandbox(material, job)
                assert result["total_chars"] > 100_000
                assert len(result["chunks"]) > 100
                assert any("末尾独特定位词" in chunk["content"] for chunk in result["chunks"])
        finally:
            await consumer
