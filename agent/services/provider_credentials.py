"""User-owned provider credentials with envelope encryption and request scoping.

Only ciphertext is persistent. Plaintext exists for the duration of a provider call
and is deliberately excluded from task payloads, traces, logs, and API responses.
"""

from __future__ import annotations

import base64
import contextvars
import hmac
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import ActiveProviderCredential, ProviderCredential

ProviderName = Literal["deepseek", "dashscope", "openai", "ollama"]
CredentialPurpose = Literal["generation", "embedding"]


class CredentialConfigurationError(RuntimeError):
    pass


class CredentialUnavailableError(RuntimeError):
    pass


class CredentialReferenceUnavailableError(CredentialUnavailableError):
    """A persisted credential id/version is revoked or no longer available."""


@dataclass(frozen=True, slots=True)
class CredentialContext:
    credential_id: uuid.UUID
    version: int
    provider: ProviderName
    purpose: CredentialPurpose
    endpoint: str
    model: str
    api_key: str


_generation_context: contextvars.ContextVar[CredentialContext | None] = contextvars.ContextVar(
    "generation_provider_credential", default=None
)
_embedding_context: contextvars.ContextVar[CredentialContext | None] = contextvars.ContextVar(
    "embedding_provider_credential", default=None
)


def current_generation_credential() -> CredentialContext | None:
    return _generation_context.get()


def current_embedding_credential() -> CredentialContext | None:
    return _embedding_context.get()


def _kek() -> bytes:
    encoded = get_settings().credential_kek_b64.strip()
    if not encoded:
        raise CredentialConfigurationError("Credential encryption is not configured")
    try:
        key = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise CredentialConfigurationError("CREDENTIAL_KEK_B64 is not valid base64") from exc
    if len(key) != 32:
        raise CredentialConfigurationError("CREDENTIAL_KEK_B64 must decode to exactly 32 bytes")
    return key


def _fingerprint_key() -> bytes:
    encoded = get_settings().credential_fingerprint_key_b64.strip()
    if not encoded and get_settings().credential_kms_backend == "local":
        return _kek()
    try:
        key = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise CredentialConfigurationError("CREDENTIAL_FINGERPRINT_KEY_B64 is not valid base64") from exc
    if len(key) < 32:
        raise CredentialConfigurationError("CREDENTIAL_FINGERPRINT_KEY_B64 must decode to at least 32 bytes")
    return key


async def _kms_request(url: str, payload: dict[str, str]) -> dict[str, str]:
    settings = get_settings()
    if not url.startswith("https://"):
        raise CredentialConfigurationError("KMS bridge URL must use HTTPS")
    if not settings.credential_kms_bearer_token:
        raise CredentialConfigurationError("KMS bridge identity is not configured")
    headers = {"Authorization": f"Bearer {settings.credential_kms_bearer_token}"}
    try:
        async with httpx.AsyncClient(timeout=settings.credential_kms_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        raise CredentialUnavailableError("KMS operation failed") from exc
    if not isinstance(data, dict):
        raise CredentialUnavailableError("KMS response is invalid")
    return {str(key): str(value) for key, value in data.items()}


async def _wrap_data_key(data_key: bytes, aad: bytes) -> tuple[str, str]:
    settings = get_settings()
    if settings.credential_kms_backend == "local":
        key_nonce = os.urandom(12)
        wrapped_key = AESGCM(_kek()).encrypt(key_nonce, data_key, aad)
        return "local:" + base64.b64encode(key_nonce + wrapped_key).decode(), settings.credential_kek_version
    result = await _kms_request(settings.credential_kms_wrap_url, {
        "plaintext_b64": base64.b64encode(data_key).decode(),
        "aad_b64": base64.b64encode(aad).decode(),
        "key_version": settings.credential_kek_version,
    })
    ciphertext = result.get("ciphertext_b64", "")
    version = result.get("key_version", "")
    if not ciphertext or not version:
        raise CredentialUnavailableError("KMS wrap response is incomplete")
    return "http:" + ciphertext, version


async def _unwrap_data_key(encrypted: str, aad: bytes, key_version: str) -> bytes:
    settings = get_settings()
    if encrypted.startswith("http:"):
        if settings.credential_kms_backend != "http":
            raise CredentialConfigurationError("HTTP KMS backend is not configured")
        result = await _kms_request(settings.credential_kms_unwrap_url, {
            "ciphertext_b64": encrypted.removeprefix("http:"),
            "aad_b64": base64.b64encode(aad).decode(),
            "key_version": key_version,
        })
        try:
            data_key = base64.b64decode(result.get("plaintext_b64", ""), validate=True)
        except Exception as exc:
            raise CredentialUnavailableError("KMS unwrap response is invalid") from exc
        if len(data_key) != 32:
            raise CredentialUnavailableError("KMS returned an invalid data key")
        return data_key
    if settings.credential_kms_backend != "local":
        raise CredentialConfigurationError("Legacy local credential requires the local KMS backend")
    try:
        wrapped = base64.b64decode(encrypted.removeprefix("local:"), validate=True)
        if len(wrapped) < 29:
            raise ValueError("wrapped key is too short")
        return AESGCM(_kek()).decrypt(wrapped[:12], wrapped[12:], aad)
    except CredentialConfigurationError:
        raise
    except Exception as exc:
        # Treat corrupt/tampered envelopes like an unavailable credential. Do
        # not expose cryptography/parser details at the API boundary.
        raise CredentialUnavailableError("Provider credential envelope is invalid") from exc


async def encrypt_user_secret(secret: str, *, user_id: uuid.UUID, purpose: str) -> dict[str, str]:
    value = secret.strip()
    if not value:
        raise ValueError("Secret must not be empty")
    aad = _aad(user_id, "eduflow", purpose, 1)
    data_key = os.urandom(32)
    payload_nonce = os.urandom(12)
    wrapped_key, key_version = await _wrap_data_key(data_key, aad)
    return {
        "secret_ciphertext": base64.b64encode(AESGCM(data_key).encrypt(payload_nonce, value.encode(), aad)).decode(),
        "secret_encrypted_data_key": wrapped_key,
        "secret_nonce": base64.b64encode(payload_nonce).decode(),
        "kms_key_version": key_version,
    }


async def decrypt_user_secret(
    *, user_id: uuid.UUID, purpose: str, ciphertext: str,
    encrypted_data_key: str, nonce: str, key_version: str,
) -> str:
    aad = _aad(user_id, "eduflow", purpose, 1)
    data_key = await _unwrap_data_key(encrypted_data_key, aad, key_version)
    return AESGCM(data_key).decrypt(
        base64.b64decode(nonce), base64.b64decode(ciphertext), aad
    ).decode()


def _aad(user_id: uuid.UUID, provider: str, purpose: str, version: int) -> bytes:
    return f"eduflow:v1:{user_id}:{provider}:{purpose}:{version}".encode()


async def encrypt_api_key(
    api_key: str, *, user_id: uuid.UUID, provider: ProviderName,
    purpose: CredentialPurpose, version: int,
) -> dict[str, str]:
    secret = api_key.strip()
    if len(secret) < 8 or len(secret) > 1000:
        raise ValueError("Provider API key must contain 8 to 1000 characters")
    aad = _aad(user_id, provider, purpose, version)
    data_key = os.urandom(32)
    payload_nonce = os.urandom(12)
    ciphertext = AESGCM(data_key).encrypt(payload_nonce, secret.encode(), aad)
    wrapped_key, key_version = await _wrap_data_key(data_key, aad)
    # This is a keyed lookup fingerprint, not password hashing. HMAC-SHA256
    # keeps duplicate-key detection deterministic without exposing the key.
    fingerprint = hmac.digest(_fingerprint_key(), secret.encode(), "sha256").hex()
    return {
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "encrypted_data_key": wrapped_key,
        "nonce": base64.b64encode(payload_nonce).decode(),
        "key_fingerprint": fingerprint,
        "key_last_four": secret[-4:],
        "kms_key_version": key_version,
    }


async def decrypt_api_key(row: ProviderCredential) -> str:
    if row.status == "revoked":
        raise CredentialReferenceUnavailableError("Provider credential has been revoked")
    aad = _aad(row.user_id, row.provider, row.purpose, row.version)
    try:
        data_key = await _unwrap_data_key(row.encrypted_data_key, aad, row.kms_key_version)
        plaintext = AESGCM(data_key).decrypt(
            base64.b64decode(row.nonce, validate=True),
            base64.b64decode(row.ciphertext, validate=True),
            aad,
        )
        return plaintext.decode()
    except (CredentialConfigurationError, CredentialUnavailableError, CredentialReferenceUnavailableError):
        raise
    except Exception as exc:
        raise CredentialUnavailableError("Provider credential envelope is invalid") from exc


def provider_defaults(provider: str, purpose: str) -> tuple[str, str]:
    settings = get_settings()
    if provider == "deepseek" and purpose == "generation":
        return settings.deepseek_endpoint, settings.deepseek_model
    elif provider == "dashscope" and purpose == "generation":
        return settings.dashscope_endpoint, settings.dashscope_model
    elif provider == "dashscope" and purpose == "embedding":
        return settings.dashscope_endpoint, settings.dashscope_embedding_model
    elif provider == "openai" and purpose == "generation":
        return "https://api.openai.com/v1", "gpt-4.1-mini"
    elif provider == "openai" and purpose == "embedding":
        return "https://api.openai.com/v1", "text-embedding-3-small"
    elif provider == "ollama" and purpose == "generation":
        return "http://localhost:11434/v1", "llama3.2"
    elif provider == "ollama" and purpose == "embedding":
        return "http://localhost:11434/v1", "nomic-embed-text"
    raise CredentialUnavailableError("Provider does not support the requested purpose")


def _endpoint_model(
    provider: str, purpose: str, base_url: str | None = None, model: str | None = None,
) -> tuple[str, str]:
    default_endpoint, default_model = provider_defaults(provider, purpose)
    endpoint = (base_url or default_endpoint).strip().rstrip("/")
    selected_model = (model or default_model).strip()
    if not selected_model or len(selected_model) > 200:
        raise CredentialConfigurationError("Provider model must contain 1 to 200 characters")

    allowed_hosts: set[str]
    if provider == "deepseek":
        allowed_hosts = {"api.deepseek.com"}
        allowed_schemes = {"https"}
        allowed_ports = {None, 443}
    elif provider == "dashscope":
        allowed_hosts = {"dashscope.aliyuncs.com"}
        allowed_schemes = {"https"}
        allowed_ports = {None, 443}
    elif provider == "openai":
        allowed_hosts = {"api.openai.com"}
        allowed_schemes = {"https"}
        allowed_ports = {None, 443}
    elif provider == "ollama":
        # Ollama is intentionally limited to the developer machine. Arbitrary
        # private/public URLs would turn credential validation into an SSRF
        # primitive from the API server's network position.
        allowed_hosts = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
        allowed_schemes = {"http"}
        allowed_ports = {11434}
    else:
        raise CredentialUnavailableError("Unsupported provider")

    parsed = urlsplit(endpoint)
    try:
        port = parsed.port
    except ValueError as exc:
        raise CredentialConfigurationError("Provider endpoint has an invalid port") from exc
    if (
        parsed.scheme not in allowed_schemes
        or (parsed.hostname or "").lower() not in allowed_hosts
        or port not in allowed_ports
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise CredentialConfigurationError("Provider endpoint is not in the production allowlist")
    return endpoint, selected_model


async def selected_provider_credential(
    session: AsyncSession, user_id: uuid.UUID, purpose: CredentialPurpose,
) -> ProviderCredential | None:
    return await session.scalar(
        select(ProviderCredential)
        .join(
            ActiveProviderCredential,
            ActiveProviderCredential.credential_id == ProviderCredential.id,
        )
        .where(
            ActiveProviderCredential.user_id == user_id,
            ActiveProviderCredential.purpose == purpose,
            ProviderCredential.user_id == user_id,
            ProviderCredential.purpose == purpose,
            ProviderCredential.status.in_(("unverified", "valid")),
        )
    )


async def resolve_user_credentials(
    session: AsyncSession, user_id: uuid.UUID,
) -> tuple[CredentialContext | None, CredentialContext | None]:
    generation_row = await selected_provider_credential(session, user_id, "generation")
    embedding_row = await selected_provider_credential(session, user_id, "embedding")

    async def build(row: ProviderCredential | None) -> CredentialContext | None:
        if row is None:
            return None
        endpoint, model = _endpoint_model(row.provider, row.purpose, row.base_url, row.model)
        row.last_used_at = datetime.now(UTC)
        return CredentialContext(
            credential_id=row.id,
            version=row.version,
            provider=row.provider,
            purpose=row.purpose,
            endpoint=endpoint,
            model=model,
            api_key=await decrypt_api_key(row),
        )

    generation = await build(generation_row)
    embedding = await build(embedding_row)
    if generation is None:
        raise CredentialReferenceUnavailableError("A generation provider credential is required")
    return generation, embedding


async def resolve_credential_reference(
    session: AsyncSession, user_id: uuid.UUID, reference: dict | None,
) -> tuple[CredentialContext | None, CredentialContext | None]:
    """Resolve a persisted id/version pair without ever persisting plaintext."""
    if not reference:
        return await resolve_user_credentials(session, user_id)
    try:
        credential_id = uuid.UUID(str(reference["id"]))
        version = int(reference["version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CredentialReferenceUnavailableError("Credential reference is invalid") from exc
    generation_row = await session.scalar(select(ProviderCredential).where(
        ProviderCredential.id == credential_id,
        ProviderCredential.user_id == user_id,
        ProviderCredential.version == version,
        ProviderCredential.purpose == "generation",
        ProviderCredential.status.in_(("unverified", "valid")),
    ))
    if generation_row is None:
        raise CredentialReferenceUnavailableError("Referenced provider credential is unavailable")
    endpoint, model = _endpoint_model(
        generation_row.provider, generation_row.purpose,
        generation_row.base_url, generation_row.model,
    )
    generation = CredentialContext(
        credential_id=generation_row.id, version=generation_row.version,
        provider=generation_row.provider, purpose=generation_row.purpose,
        endpoint=endpoint, model=model, api_key=await decrypt_api_key(generation_row),
    )
    _, embedding = await resolve_user_credentials(session, user_id)
    return generation, embedding


@contextmanager
def credential_scope(
    generation: CredentialContext | None,
    embedding: CredentialContext | None,
) -> Iterator[None]:
    generation_token = _generation_context.set(generation)
    embedding_token = _embedding_context.set(embedding)
    try:
        yield
    finally:
        _embedding_context.reset(embedding_token)
        _generation_context.reset(generation_token)


def public_credential(row: ProviderCredential, *, is_active: bool = False) -> dict[str, object]:
    return {
        "id": str(row.id),
        "name": row.name,
        "provider": row.provider,
        "purpose": row.purpose,
        "model": row.model,
        "base_url": row.base_url,
        "version": row.version,
        "status": row.status,
        "is_active": is_active,
        "key_last_four": row.key_last_four,
        "validated_at": row.validated_at,
        "last_used_at": row.last_used_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
