from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from pydantic import SecretStr

from config import Settings, get_settings
from security.passwords import (
    hash_password,
    normalize_email,
    validate_password_policy,
    verify_password,
)
from security.tokens import (
    AccessTokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)


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


def test_normalize_email() -> None:
    assert normalize_email(" Student@Example.COM ") == "student@example.com"


@pytest.mark.parametrize("password", ["short1", "abcdefgh", "12345678"])
def test_password_policy_rejects_invalid_values(password: str) -> None:
    with pytest.raises(ValueError):
        validate_password_policy(password)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("learning2026")

    valid, replacement = verify_password("learning2026", encoded)

    assert valid is True
    assert replacement is None
    assert verify_password("wrong2026", encoded)[0] is False


def test_access_token_round_trip() -> None:
    user_id = uuid4()
    session_id = uuid4()

    issued = create_access_token(user_id, session_id)
    claims = decode_access_token(issued.token)

    assert claims.user_id == user_id
    assert claims.session_id == session_id
    assert issued.expires_in == 900


def test_refresh_token_is_opaque_and_hash_is_stable() -> None:
    token = generate_refresh_token()

    assert len(token) >= 64
    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert token not in hash_refresh_token(token)


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c"])
def test_decode_rejects_malformed_tokens(token: str) -> None:
    with pytest.raises(AccessTokenError):
        decode_access_token(token)


@pytest.mark.parametrize(
    "payload_overrides",
    [
        {"sid": None},
        {"type": "refresh"},
        {"iss": "unexpected-issuer"},
        {"exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
    ],
    ids=["missing-session", "refresh-token", "wrong-issuer", "expired"],
)
def test_decode_rejects_invalid_signed_tokens(
    payload_overrides: dict[str, object],
) -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "sub": str(uuid4()),
        "sid": str(uuid4()),
        "type": "access",
        "jti": str(uuid4()),
        "iss": settings.auth_jwt_issuer,
        "aud": settings.auth_jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=15),
    }
    payload.update(payload_overrides)
    payload = {key: value for key, value in payload.items() if value is not None}
    token = jwt.encode(
        payload,
        settings.auth_jwt_secret.get_secret_value(),
        algorithm=settings.auth_jwt_algorithm,
    )

    with pytest.raises(AccessTokenError):
        decode_access_token(token)


def test_decode_rejects_wrong_algorithm() -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "sid": str(uuid4()),
            "type": "access",
            "jti": str(uuid4()),
            "iss": settings.auth_jwt_issuer,
            "aud": settings.auth_jwt_audience,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=15),
        },
        settings.auth_jwt_secret.get_secret_value(),
        algorithm="HS384",
    )

    with pytest.raises(AccessTokenError):
        decode_access_token(token)
