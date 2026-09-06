"""Safety checks for the explicit legacy owner/material migration."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.migrate_legacy_data import legacy_material_source


def test_legacy_material_source_is_scoped_to_upload_root(tmp_path: Path):
    material = SimpleNamespace(id="material-id", stored_filename="lesson.md")
    assert legacy_material_source(material, tmp_path) == (
        tmp_path / "material-id" / "lesson.md"
    ).resolve()


def test_legacy_material_source_rejects_path_traversal(tmp_path: Path):
    material = SimpleNamespace(id="material-id", stored_filename="../../secret.txt")
    with pytest.raises(ValueError, match="escapes upload root"):
        legacy_material_source(material, tmp_path)
