from pathlib import Path

import pytest
from pydantic import SecretStr

from config import Settings


def test_auth_settings_defaults() -> None:
    settings = Settings(
        AUTH_JWT_SECRET="x" * 64,
        _env_file=None,
    )

    assert isinstance(settings.auth_jwt_secret, SecretStr)
    assert settings.auth_access_token_seconds == 900
    assert settings.auth_refresh_token_days == 30
    assert settings.auth_refresh_cookie_name == "eduflow_refresh"
    assert settings.auth_jwt_algorithm == "HS256"
    assert settings.auth_cookie_secure is True
    assert settings.auth_cookie_samesite == "lax"


def test_auth_secret_is_required(monkeypatch) -> None:
    monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)

    try:
        Settings(_env_file=None)
    except ValueError as exc:
        assert "AUTH_JWT_SECRET" in str(exc)
    else:
        raise AssertionError("AUTH_JWT_SECRET must be required")


@pytest.mark.parametrize(
    "secret",
    ["", " " * 64, "x" * 63, "replace-with-at-least-64-random-characters"],
)
def test_auth_secret_rejects_blank_short_and_documented_placeholder(secret: str) -> None:
    with pytest.raises(ValueError, match="AUTH_JWT_SECRET"):
        Settings(AUTH_JWT_SECRET=secret, _env_file=None)


def test_auth_secret_accepts_sixty_four_characters() -> None:
    settings = Settings(AUTH_JWT_SECRET="x" * 64, _env_file=None)

    assert settings.auth_jwt_secret.get_secret_value() == "x" * 64


@pytest.mark.parametrize(
    ("environment_name", "value"),
    [
        ("AUTH_ACCESS_TOKEN_SECONDS", "0"),
        ("AUTH_ACCESS_TOKEN_SECONDS", "-1"),
        ("AUTH_REFRESH_TOKEN_DAYS", "0"),
        ("AUTH_REFRESH_TOKEN_DAYS", "-1"),
        ("AUTH_JWT_ALGORITHM", "HS384"),
        ("AUTH_COOKIE_SAMESITE", "invalid"),
    ],
)
def test_invalid_auth_security_settings_are_rejected(
    monkeypatch, environment_name: str, value: str
) -> None:
    monkeypatch.setenv("AUTH_JWT_SECRET", "x" * 64)
    monkeypatch.setenv(environment_name, value)

    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_samesite_none_requires_secure_cookie(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_JWT_SECRET", "x" * 64)
    monkeypatch.setenv("AUTH_COOKIE_SAMESITE", "none")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")

    with pytest.raises(ValueError, match="AUTH_COOKIE_SAMESITE"):
        Settings(_env_file=None)


def test_auth_deployment_defaults_require_a_secret_and_secure_cookies() -> None:
    project_root = Path(__file__).resolve().parents[2]
    env_example = (project_root / ".env.example").read_text(encoding="utf-8")
    compose = (project_root / "docker-compose.yml").read_text(encoding="utf-8")

    assert "AUTH_COOKIE_SECURE=true" in env_example
    assert "AUTH_JWT_SECRET=${AUTH_JWT_SECRET:?AUTH_JWT_SECRET is required}" in compose
    assert "AUTH_COOKIE_SECURE=${AUTH_COOKIE_SECURE:-true}" in compose
