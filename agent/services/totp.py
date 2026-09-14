"""Small RFC 6238 TOTP implementation with no external runtime dependency."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code(secret: str, counter: int) -> str:
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded)
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def verify_code(secret: str, code: str, *, now: float | None = None) -> bool:
    normalized = "".join(str(code).split())
    if len(normalized) != 6 or not normalized.isdigit():
        return False
    counter = int((time.time() if now is None else now) // 30)
    return any(hmac.compare_digest(_code(secret, counter + drift), normalized) for drift in (-1, 0, 1))


def provisioning_uri(secret: str, *, email: str) -> str:
    from urllib.parse import quote

    label = quote(f"EduFlow:{email}")
    issuer = quote("EduFlow")
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
