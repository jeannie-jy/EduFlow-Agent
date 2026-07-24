"""Static checks for backend CI configuration required by application startup."""

from pathlib import Path

import yaml


def test_ci_auth_jwt_secret_satisfies_backend_minimum_length() -> None:
    """The CI migration step must be able to construct application settings."""
    workflow_path = Path(__file__).resolve().parents[2] / ".github/workflows/backend-ci.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    secret = workflow["jobs"]["test"]["env"]["AUTH_JWT_SECRET"]

    assert len(secret) >= 64
