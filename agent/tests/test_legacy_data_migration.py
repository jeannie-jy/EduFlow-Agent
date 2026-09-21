"""Safety checks for the explicit legacy owner/material migration."""

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from scripts.migrate_legacy_data import legacy_material_source, migrate_legacy_data
from services.artifact_store import StoredArtifact


def test_legacy_material_source_is_scoped_to_upload_root(tmp_path: Path):
    material = SimpleNamespace(id="material-id", stored_filename="lesson.md")
    assert legacy_material_source(material, tmp_path) == (
        tmp_path / "material-id" / "lesson.md"
    ).resolve()


def test_legacy_material_source_rejects_path_traversal(tmp_path: Path):
    material = SimpleNamespace(id="material-id", stored_filename="../../secret.txt")
    with pytest.raises(ValueError, match="escapes upload root"):
        legacy_material_source(material, tmp_path)


@pytest.mark.asyncio
async def test_migration_compensates_uploaded_objects_when_later_upload_fails(
    tmp_path: Path,
):
    owner = SimpleNamespace(id=uuid4(), email="owner@example.test", is_active=True)
    project = SimpleNamespace(owner_id=None)
    first = SimpleNamespace(
        id=uuid4(),
        owner_id=None,
        stored_filename="first.md",
        storage_key=None,
        media_type="text/markdown",
        size_bytes=5,
    )
    second = SimpleNamespace(
        id=uuid4(),
        owner_id=None,
        stored_filename="second.md",
        storage_key=None,
        media_type="text/markdown",
        size_bytes=6,
    )
    (tmp_path / str(first.id)).mkdir()
    (tmp_path / str(second.id)).mkdir()
    (tmp_path / str(first.id) / "first.md").write_text("first", encoding="utf-8")
    (tmp_path / str(second.id) / "second.md").write_text("second", encoding="utf-8")

    class Result:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return self

        def all(self):
            return self._rows

    class Session:
        def __init__(self):
            self.calls = 0

        async def scalar(self, _query):
            return owner

        async def execute(self, _query):
            self.calls += 1
            return Result(
                {
                    1: [project],
                    2: [first, second],
                    3: [],
                    4: [first, second],
                }[self.calls]
            )

        async def rollback(self):
            return None

        async def flush(self):
            return None

    class Store:
        def __init__(self):
            self.deleted: list[str] = []

        async def put_file(self, key, source, content_type):
            del source, content_type
            if key.endswith(str(second.id) + "/source.md"):
                raise RuntimeError("simulated MinIO outage")
            return StoredArtifact(key, 5, "sha256", "text/markdown")

        async def delete(self, key):
            self.deleted.append(key)

    store = Store()
    with pytest.raises(RuntimeError, match="simulated MinIO outage"):
        await migrate_legacy_data(
            Session(),
            owner_email=owner.email,
            apply=True,
            migrate_material_files=True,
            upload_root=tmp_path,
            store=store,
        )

    assert store.deleted == [f"materials/{first.id}/source.md"]
