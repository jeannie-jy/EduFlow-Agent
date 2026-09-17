"""Tests for the isolated online-evaluation credential scope."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from evals.evaluation_credentials import online_eval_credential_scope
from services.provider_credentials import (
    CredentialUnavailableError,
    current_embedding_credential,
    current_generation_credential,
)


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        llm_endpoint="https://api.deepseek.com/v1",
        llm_model="deepseek-chat",
        embedding_endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1",
        embedding_model="text-embedding-v4",
    )


def test_online_eval_scope_is_noop_without_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("EDUFLOW_ALLOW_ONLINE_EVAL", raising=False)
    with online_eval_credential_scope():
        assert current_generation_credential() is None
        assert current_embedding_credential() is None


def test_online_eval_scope_requires_both_credentials(monkeypatch):
    monkeypatch.setenv("EDUFLOW_ALLOW_ONLINE_EVAL", "1")
    monkeypatch.setenv("EDUFLOW_EVAL_LLM_API_KEY", "candidate-key")
    monkeypatch.delenv("EDUFLOW_EVAL_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    with patch("evals.evaluation_credentials.get_settings", return_value=_settings()):
        with pytest.raises(CredentialUnavailableError, match="EMBEDDING"):
            with online_eval_credential_scope():
                pass


def test_online_eval_scope_scopes_secrets_and_clears_them(monkeypatch):
    monkeypatch.setenv("EDUFLOW_ALLOW_ONLINE_EVAL", "1")
    monkeypatch.setenv("EDUFLOW_EVAL_LLM_API_KEY", "candidate-key")
    monkeypatch.setenv("EDUFLOW_EVAL_EMBEDDING_API_KEY", "embedding-key")
    with patch("evals.evaluation_credentials.get_settings", return_value=_settings()):
        with online_eval_credential_scope():
            generation = current_generation_credential()
            embedding = current_embedding_credential()
            assert generation is not None
            assert generation.api_key == "candidate-key"
            assert generation.endpoint == "https://api.deepseek.com/v1"
            assert embedding is not None
            assert embedding.api_key == "embedding-key"
            assert embedding.provider == "dashscope"
        assert current_generation_credential() is None
        assert current_embedding_credential() is None
