"""Artifact storage abstraction with local and MinIO implementations."""

from __future__ import annotations

import asyncio
import hashlib
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from config import get_settings


@dataclass(frozen=True)
class StoredArtifact:
    key: str
    size_bytes: int
    sha256: str
    content_type: str


class ArtifactStore(Protocol):
    async def put_file(
        self, key: str, source: Path, content_type: str
    ) -> StoredArtifact: ...
    async def presigned_get_url(
        self, key: str, expires_seconds: int = 900
    ) -> str | None: ...
    async def get_file(self, key: str, destination: Path) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def ready(self) -> None: ...


def normalize_artifact_key(key: str) -> str:
    normalized = PurePosixPath(key)
    if normalized.is_absolute() or ".." in normalized.parts or not normalized.parts:
        raise ValueError("Invalid artifact key")
    return str(normalized)


def _sha256_file(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LocalArtifactStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    async def put_file(
        self, key: str, source: Path, content_type: str
    ) -> StoredArtifact:
        safe_key = normalize_artifact_key(key)
        destination = (self.root / Path(*PurePosixPath(safe_key).parts)).resolve()
        if not destination.is_relative_to(self.root):
            raise ValueError("Artifact path escapes storage root")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != destination:
            await asyncio.to_thread(shutil.copy2, source, destination)
        sha256 = await asyncio.to_thread(_sha256_file, destination)
        return StoredArtifact(
            safe_key, destination.stat().st_size, sha256, content_type
        )

    async def presigned_get_url(
        self, key: str, expires_seconds: int = 900
    ) -> str | None:
        del key, expires_seconds

    async def get_file(self, key: str, destination: Path) -> None:
        source = (
            self.root / Path(*PurePosixPath(normalize_artifact_key(key)).parts)
        ).resolve()
        if not source.is_relative_to(self.root) or not source.is_file():
            raise FileNotFoundError(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, source, destination)

    async def delete(self, key: str) -> None:
        target = (
            self.root / Path(*PurePosixPath(normalize_artifact_key(key)).parts)
        ).resolve()
        if target.is_relative_to(self.root):
            target.unlink(missing_ok=True)

    async def ready(self) -> None:
        await asyncio.to_thread(self.root.mkdir, parents=True, exist_ok=True)


class MinioArtifactStore:
    def __init__(self, client_factory: Callable[..., Any] | None = None):
        settings = get_settings()
        if not settings.minio_access_key or not settings.minio_secret_key:
            raise RuntimeError(
                "MinIO credentials are required when ARTIFACT_STORE_BACKEND=minio"
            )
        if client_factory is None:
            from minio import Minio

            client_factory = Minio
        credentials = {
            "access_key": settings.minio_access_key,
            "secret_key": settings.minio_secret_key,
            "secure": settings.minio_secure,
        }
        self.bucket = settings.minio_bucket
        self.client = client_factory(settings.minio_endpoint, **credentials)
        self.public_client = client_factory(settings.minio_public_endpoint, **credentials)

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    async def put_file(
        self, key: str, source: Path, content_type: str
    ) -> StoredArtifact:
        safe_key = normalize_artifact_key(key)

        def upload() -> None:
            self._ensure_bucket()
            self.client.fput_object(
                self.bucket, safe_key, str(source), content_type=content_type
            )

        sha256 = await asyncio.to_thread(_sha256_file, source)
        await asyncio.to_thread(upload)
        return StoredArtifact(safe_key, source.stat().st_size, sha256, content_type)

    async def presigned_get_url(self, key: str, expires_seconds: int = 900) -> str:
        safe_key = normalize_artifact_key(key)
        return await asyncio.to_thread(
            self.public_client.presigned_get_object,
            self.bucket,
            safe_key,
            expires=timedelta(seconds=expires_seconds),
        )

    async def get_file(self, key: str, destination: Path) -> None:
        safe_key = normalize_artifact_key(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            self.client.fget_object, self.bucket, safe_key, str(destination)
        )

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self.client.remove_object, self.bucket, normalize_artifact_key(key)
        )

    async def ready(self) -> None:
        await asyncio.to_thread(self._ensure_bucket)


def get_artifact_store() -> ArtifactStore:
    settings = get_settings()
    if settings.artifact_store_backend == "minio":
        return MinioArtifactStore()
    return LocalArtifactStore(settings.artifact_store_dir)
