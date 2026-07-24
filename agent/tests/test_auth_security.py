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
    assert settings.auth_cookie_samesite == "lax"


def test_auth_secret_is_required(monkeypatch) -> None:
    monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)

    try:
        Settings(_env_file=None)
    except ValueError as exc:
        assert "AUTH_JWT_SECRET" in str(exc)
    else:
        raise AssertionError("AUTH_JWT_SECRET must be required")
