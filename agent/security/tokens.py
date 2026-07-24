"""Access JWT and opaque refresh-token primitives."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid

import jwt

from config import get_settings


class AccessTokenError(Exception):
    """Raised when an access token is invalid or cannot be decoded."""


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID
    token_id: uuid.UUID
    expires_at: datetime


@dataclass(frozen=True)
class IssuedAccessToken:
    token: str
    expires_in: int
    expires_at: datetime


def create_access_token(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> IssuedAccessToken:
    """Create a signed access JWT for a user session."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.auth_access_token_seconds)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iss": settings.auth_jwt_issuer,
        "aud": settings.auth_jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": expires_at,
    }
    token = jwt.encode(
        payload,
        settings.auth_jwt_secret.get_secret_value(),
        algorithm=settings.auth_jwt_algorithm,
    )
    return IssuedAccessToken(
        token=token,
        expires_in=settings.auth_access_token_seconds,
        expires_at=expires_at,
    )


def decode_access_token(token: str) -> AccessTokenClaims:
    """Decode and validate a signed access JWT."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.auth_jwt_secret.get_secret_value(),
            algorithms=[settings.auth_jwt_algorithm],
            issuer=settings.auth_jwt_issuer,
            audience=settings.auth_jwt_audience,
            options={
                "require": [
                    "sub",
                    "sid",
                    "type",
                    "jti",
                    "iss",
                    "aud",
                    "iat",
                    "nbf",
                    "exp",
                ]
            },
        )
        if payload["type"] != "access":
            raise AccessTokenError
        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            session_id=uuid.UUID(payload["sid"]),
            token_id=uuid.UUID(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise AccessTokenError from exc


def generate_refresh_token() -> str:
    """Generate a high-entropy opaque refresh token."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Return the stable SHA-256 digest stored for a refresh token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
