"""ArtifactStore contract tests for local and MinIO-backed exports."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import RedirectResponse

from services.artifact_store import (
    LocalArtifactStore,
    MinioArtifactStore,
    StoredArtifact,
    normalize_artifact_key,
)


def test_artifact_key_rejects_absolute_and_parent_traversal():
    with pytest.raises(ValueError):
        normalize_artifact_key("../secret")
    with pytest.raises(ValueError):
        normalize_artifact_key("/absolute/file")
    assert normalize_artifact_key("exports/job/video.mp4") == "exports/job/video.mp4"


def test_minio_store_rejects_missing_credentials():
    settings = SimpleNamespace(minio_access_key="", minio_secret_key="")
    with patch("services.artifact_store.get_settings", return_value=settings):
        with pytest.raises(RuntimeError, match="credentials are required"):
            MinioArtifactStore()


@pytest.mark.asyncio
async def test_local_store_copies_to_bounded_key(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    store = LocalArtifactStore(tmp_path / "objects")

    stored = await store.put_file("exports/job/video.mp4", source, "video/mp4")

    assert stored == StoredArtifact(
        "exports/job/video.mp4",
        5,
        "0cab1c9617404faf2b24e221e189ca5945813e14d3f766345b09ca13bbe28ffc",
        "video/mp4",
    )
    assert (tmp_path / "objects/exports/job/video.mp4").read_bytes() == b"video"

    downloaded = tmp_path / "downloaded.mp4"
    await store.get_file("exports/job/video.mp4", downloaded)
    assert downloaded.read_bytes() == b"video"


@pytest.mark.asyncio
async def test_minio_store_creates_bucket_uploads_and_presigns(tmp_path):
    source = tmp_path / "lesson.mp4"
    source.write_bytes(b"video")
    internal = MagicMock()
    internal.bucket_exists.return_value = False
    public = MagicMock()
    public.presigned_get_object.return_value = "http://public/signed"
    settings = SimpleNamespace(
        minio_access_key="access",
        minio_secret_key="secret",
        minio_secure=False,
        minio_bucket="artifacts",
        minio_endpoint="minio:9000",
        minio_public_endpoint="localhost:9000",
    )
    client_factory = MagicMock(side_effect=[internal, public])
    with patch("services.artifact_store.get_settings", return_value=settings):
        store = MinioArtifactStore(client_factory=client_factory)
        stored = await store.put_file("exports/job/lesson.mp4", source, "video/mp4")
        url = await store.presigned_get_url(stored.key)

    internal.make_bucket.assert_called_once_with("artifacts")
    internal.fput_object.assert_called_once()
    assert stored.sha256 == (
        "0cab1c9617404faf2b24e221e189ca5945813e14d3f766345b09ca13bbe28ffc"
    )
    assert stored.content_type == "video/mp4"
    assert url == "http://public/signed"

    destination = tmp_path / "downloaded.mp4"
    await store.get_file(stored.key, destination)
    internal.fget_object.assert_called_once_with(
        "artifacts", "exports/job/lesson.mp4", str(destination)
    )


@pytest.mark.asyncio
async def test_export_publisher_records_storage_keys(tmp_path):
    from api.export import _publish_export_artifacts

    export_dir = tmp_path / "job"
    export_dir.mkdir()
    (export_dir / "main.py").write_text("print('safe')", encoding="utf-8")
    store = MagicMock()
    store.put_file = AsyncMock(
        return_value=StoredArtifact(
            "exports/job/main.py", 13, "content-hash", "text/x-python"
        )
    )
    with patch("services.artifact_store.get_artifact_store", return_value=store):
        result = await _publish_export_artifacts(
            export_dir,
            "job",
            [{"type": "manim_source", "filename": "main.py", "size_bytes": 0}],
        )

    assert result[0]["storage_key"] == "exports/job/main.py"
    assert result[0]["size_bytes"] == 13
    assert result[0]["sha256"] == "content-hash"
    assert result[0]["content_type"] == "text/x-python"


@pytest.mark.asyncio
async def test_authorized_download_redirects_to_presigned_object_url():
    from api.export import download_artifact

    job_id = "00000000-0000-0000-0000-000000000001"
    job = MagicMock(
        artifacts=[
            {
                "filename": "lesson.mp4",
                "storage_key": f"exports/{job_id}/lesson.mp4",
            }
        ]
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=job)
    # Owner-scoped export lookup returns the authorized job in one joined query.
    session.scalar = AsyncMock(return_value=job)
    store = MagicMock()
    store.presigned_get_url = AsyncMock(return_value="http://public/signed")

    with patch("services.artifact_store.get_artifact_store", return_value=store):
        response = await download_artifact(
            job_id,
            "lesson.mp4",
            session,
            MagicMock(id="owner-id"),
        )

    assert isinstance(response, RedirectResponse)
    assert response.status_code == 307
    assert response.headers["location"] == "http://public/signed"
    store.presigned_get_url.assert_awaited_once_with(f"exports/{job_id}/lesson.mp4")


@pytest.mark.asyncio
async def test_cross_owner_download_does_not_issue_presigned_url():
    from api.export import download_artifact

    job_id = "00000000-0000-0000-0000-000000000001"
    session = MagicMock()
    session.get = AsyncMock(
        return_value=MagicMock(
            artifacts=[
                {
                    "filename": "lesson.mp4",
                    "storage_key": f"exports/{job_id}/lesson.mp4",
                }
            ]
        )
    )
    session.scalar = AsyncMock(return_value=None)

    with patch("services.artifact_store.get_artifact_store") as get_store:
        with pytest.raises(HTTPException) as exc:
            await download_artifact(
                job_id,
                "lesson.mp4",
                session,
                MagicMock(id="other-owner"),
            )

    assert exc.value.status_code == 404
    get_store.assert_not_called()
