"""Ephemeral provider credentials for explicitly opted-in online evaluations.

The application is BYOK-only and deliberately rejects process-wide provider
keys. Online benchmark jobs are an isolated, explicit exception: GitHub
Actions injects evaluation secrets into the benchmark container, and this
module scopes them to the current evaluation call without persisting or
exposing them through the user credential store.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlsplit

from config import get_settings
from services.provider_credentials import (
    CredentialContext,
    CredentialPurpose,
    CredentialUnavailableError,
    ProviderName,
    credential_scope,
)


def _provider_for_endpoint(endpoint: str) -> ProviderName:
    """Return metadata for a benchmark endpoint without applying app allowlists."""
    host = (urlsplit(endpoint).hostname or "").casefold()
    if host.endswith("deepseek.com"):
        return "deepseek"
    if host.endswith("aliyuncs.com"):
        return "dashscope"
    if host in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}:
        return "ollama"
    return "openai"


def _required_key(eval_name: str, legacy_name: str) -> str:
    """Read an explicit eval secret, retaining local CLI compatibility."""
    value = os.getenv(eval_name, "").strip() or os.getenv(legacy_name, "").strip()
    if not value:
        raise CredentialUnavailableError(
            f"missing required online evaluation credential: {eval_name}"
        )
    return value


def _build_context(
    *,
    settings: object,
    purpose: CredentialPurpose,
    endpoint_name: str,
    model_name: str,
    eval_key_name: str,
    legacy_key_name: str,
) -> CredentialContext:
    endpoint = str(getattr(settings, endpoint_name, "") or "").strip().rstrip("/")
    model = str(getattr(settings, model_name, "") or "").strip()
    if not endpoint or not model:
        raise CredentialUnavailableError(
            f"missing required online evaluation setting: {endpoint_name}/{model_name}"
        )
    return CredentialContext(
        credential_id=uuid.uuid4(),
        version=1,
        provider=_provider_for_endpoint(endpoint),
        purpose=purpose,
        endpoint=endpoint,
        model=model,
        api_key=_required_key(eval_key_name, legacy_key_name),
    )


@contextmanager
def online_eval_credential_scope() -> Iterator[None]:
    """Scope explicit evaluation secrets, or remain a no-op outside eval jobs.

    Keeping the non-evaluation path a no-op lets unit tests and normal local
    callers retain the same BYOK enforcement as the production application.
    Once the opt-in flag is set, both candidate and embedding credentials are
    mandatory so a benchmark cannot silently downgrade to fallback behavior.
    """
    if os.getenv("EDUFLOW_ALLOW_ONLINE_EVAL") != "1":
        yield
        return

    settings = get_settings()
    generation = _build_context(
        settings=settings,
        purpose="generation",
        endpoint_name="llm_endpoint",
        model_name="llm_model",
        eval_key_name="EDUFLOW_EVAL_LLM_API_KEY",
        legacy_key_name="LLM_API_KEY",
    )
    embedding = _build_context(
        settings=settings,
        purpose="embedding",
        endpoint_name="embedding_endpoint",
        model_name="embedding_model",
        eval_key_name="EDUFLOW_EVAL_EMBEDDING_API_KEY",
        legacy_key_name="EMBEDDING_API_KEY",
    )
    with credential_scope(generation, embedding):
        yield
