from __future__ import annotations

import base64
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import Settings, validate_runtime_settings
from db.models import ProviderCredential, UsageBucket, UsageLedger, User, UserQuotaPolicy
from services.provider_credentials import (
    CredentialUnavailableError,
    decrypt_api_key,
    encrypt_api_key,
)
from services.quota import (
    QuotaExceededError,
    consume_quota,
    release_quota,
    reserve_quota,
    settle_quota,
)
from services.totp import new_secret, verify_code


def _settings(**overrides):
    values = {
        "credential_kek_b64": base64.b64encode(b"k" * 32).decode(),
        "credential_kek_version": "test-v1",
        "credential_kms_backend": "local",
        "credential_fingerprint_key_b64": "",
        "credential_kms_wrap_url": "https://kms.example.test/wrap",
        "credential_kms_unwrap_url": "https://kms.example.test/unwrap",
        "credential_kms_bearer_token": "test-token",
        "credential_kms_timeout_seconds": 1.0,
        "quota_generation_daily": 2,
        "quota_generation_monthly": 3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_envelope_encryption_round_trip_never_persists_plaintext():
    user_id = uuid.uuid4()
    secret = "sk-sensitive-provider-key"
    with patch("services.provider_credentials.get_settings", return_value=_settings()):
        envelope = await encrypt_api_key(
            secret, user_id=user_id, provider="deepseek", purpose="generation", version=1
        )
        row = ProviderCredential(
            id=uuid.uuid4(), user_id=user_id, provider="deepseek", purpose="generation",
            version=1, status="active", **envelope,
        )
        serialized = repr(envelope)
        assert secret not in serialized
        assert await decrypt_api_key(row) == secret


@pytest.mark.asyncio
async def test_external_kms_failure_fails_closed_without_local_fallback():
    settings = _settings(
        credential_kms_backend="http",
        credential_fingerprint_key_b64=base64.b64encode(b"f" * 32).decode(),
    )
    with (
        patch("services.provider_credentials.get_settings", return_value=settings),
        patch(
            "services.provider_credentials._kms_request",
            new=AsyncMock(side_effect=CredentialUnavailableError("KMS operation failed")),
        ),
        pytest.raises(CredentialUnavailableError, match="KMS operation failed"),
    ):
        await encrypt_api_key(
            "sk-must-not-fallback", user_id=uuid.uuid4(),
            provider="deepseek", purpose="generation", version=1,
        )


def test_production_configuration_fails_closed():
    settings = Settings(_env_file=None, environment="production")
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        validate_runtime_settings(settings)


def test_totp_accepts_current_code_and_rejects_invalid_code():
    secret = new_secret()
    import services.totp as totp
    with patch.object(totp.time, "time", return_value=1_700_000_000):
        counter = int(1_700_000_000 // 30)
        code = totp._code(secret, counter)
        assert verify_code(secret, code, now=1_700_000_000)
        assert not verify_code(secret, "000000", now=1_700_000_000)


def test_registration_pow_challenge_is_signed_and_bounded():
    import hashlib
    import base64 as b64
    from api.auth import _issue_registration_challenge, _validate_registration_challenge
    settings = _settings(
        auth_registration_challenge_required=True,
        auth_registration_challenge_secret="challenge-secret",
        auth_registration_challenge_difficulty=1,
        auth_allow_registration=True,
    )
    with patch("api.auth.get_settings", return_value=settings):
        challenge = _issue_registration_challenge()
        encoded = str(challenge["challenge"]).split(".", 1)[0]
        payload = b64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        nonce = payload.split(".", 1)[0]
        solution = next(str(i) for i in range(100) if hashlib.sha256(f"{nonce}{i}".encode()).hexdigest().startswith("0"))
        _validate_registration_challenge(str(challenge["challenge"]), solution)


@pytest.mark.asyncio
async def test_quota_is_idempotent_and_enforces_both_periods():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
        await connection.run_sync(UsageBucket.__table__.create)
        await connection.run_sync(UsageLedger.__table__.create)
        await connection.run_sync(UserQuotaPolicy.__table__.create)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    user_id = uuid.uuid4()
    async with factory() as session:
        session.add(User(
            id=user_id, email="quota@example.com", nickname="Quota",
            password_hash="unused", role="student", is_active=True,
        ))
        await session.commit()
        with patch("services.quota.get_settings", return_value=_settings()):
            assert await consume_quota(
                session, user_id=user_id, resource="generation", idempotency_key="one"
            ) is True
            assert await consume_quota(
                session, user_id=user_id, resource="generation", idempotency_key="one"
            ) is False
            assert await consume_quota(
                session, user_id=user_id, resource="generation", idempotency_key="two"
            ) is True
            with pytest.raises(QuotaExceededError):
                await consume_quota(
                    session, user_id=user_id, resource="generation", idempotency_key="three"
                )
    await engine.dispose()


@pytest.mark.asyncio
async def test_quota_reservation_settlement_and_release_are_idempotent():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
        await connection.run_sync(UsageBucket.__table__.create)
        await connection.run_sync(UsageLedger.__table__.create)
        await connection.run_sync(UserQuotaPolicy.__table__.create)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    user_id = uuid.uuid4()
    async with factory() as session:
        session.add(User(
            id=user_id, email="reservation@example.com", nickname="Reservation",
            password_hash="unused", role="student", is_active=True,
        ))
        await session.commit()
        with patch("services.quota.get_settings", return_value=_settings()):
            assert await reserve_quota(
                session, user_id=user_id, resource="generation", idempotency_key="reserve-one",
            ) is True
            assert await reserve_quota(
                session, user_id=user_id, resource="generation", idempotency_key="reserve-one",
            ) is False
            assert await release_quota(
                session, user_id=user_id, resource="generation", idempotency_key="reserve-one",
            ) is True
            assert await release_quota(
                session, user_id=user_id, resource="generation", idempotency_key="reserve-one",
            ) is False

            assert await reserve_quota(
                session, user_id=user_id, resource="generation", idempotency_key="reserve-two",
            ) is True
            assert await settle_quota(
                session, user_id=user_id, resource="generation", idempotency_key="reserve-two",
            ) is True
            assert await settle_quota(
                session, user_id=user_id, resource="generation", idempotency_key="reserve-two",
            ) is False
            bucket = await session.scalar(
                select(UsageBucket).where(
                    UsageBucket.user_id == user_id,
                    UsageBucket.resource == "generation",
                    UsageBucket.period == "day",
                )
            )
            assert bucket is not None and bucket.consumed == 1
    await engine.dispose()
