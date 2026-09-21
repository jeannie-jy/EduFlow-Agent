from __future__ import annotations

import base64
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import Settings, validate_runtime_settings
from db.models import (
    ActiveProviderCredential,
    ProviderCredential,
    UsageBucket,
    UsageLedger,
    User,
    UserQuotaPolicy,
)
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
async def test_provider_credential_list_excludes_revoked_history():
    from api.account import list_provider_credentials

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
        await connection.run_sync(ProviderCredential.__table__.create)
        await connection.run_sync(ActiveProviderCredential.__table__.create)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    user_id = uuid.uuid4()
    active_id = uuid.uuid4()
    revoked_id = uuid.uuid4()
    async with factory() as session:
        user = User(
            id=user_id, email="credentials@example.com", nickname="Credentials",
            password_hash="unused", role="student", is_active=True,
        )
        session.add_all([
            user,
            ProviderCredential(
                id=active_id, user_id=user_id, provider="deepseek", purpose="generation",
                version=2, status="valid", ciphertext="ciphertext", encrypted_data_key="key",
                nonce="nonce", key_fingerprint="fingerprint", key_last_four="2222",
                kms_key_version="test-v1",
            ),
            ActiveProviderCredential(
                user_id=user_id, purpose="generation", credential_id=active_id,
            ),
            ProviderCredential(
                id=revoked_id, user_id=user_id, provider="deepseek", purpose="generation",
                version=1, status="revoked", ciphertext="ciphertext", encrypted_data_key="key",
                nonce="nonce", key_fingerprint="fingerprint", key_last_four="1111",
                kms_key_version="test-v1",
            ),
        ])
        await session.commit()

        result = await list_provider_credentials(session=session, current_user=user)

    assert [item["id"] for item in result["items"]] == [str(active_id)]
    assert result["items"][0]["is_active"] is True
    await engine.dispose()


@pytest.mark.asyncio
async def test_saving_a_provider_preserves_the_active_credential_for_its_purpose():
    from api.account import CredentialRequest, create_provider_credential

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
        await connection.run_sync(ProviderCredential.__table__.create)
        await connection.run_sync(ActiveProviderCredential.__table__.create)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    user_id = uuid.uuid4()
    old_id = uuid.uuid4()
    embedding_id = uuid.uuid4()
    envelope = {
        "ciphertext": "ciphertext",
        "encrypted_data_key": "key",
        "nonce": "nonce",
        "key_fingerprint": "fingerprint",
        "key_last_four": "4444",
        "kms_key_version": "test-v1",
    }
    async with factory() as session:
        user = User(
            id=user_id, email="replace@example.com", nickname="Replace",
            password_hash="unused", role="student", is_active=True,
        )
        session.add_all([
            user,
            ProviderCredential(
                id=old_id, user_id=user_id, provider="deepseek", purpose="generation",
                version=1, status="valid", **envelope,
            ),
            ProviderCredential(
                id=embedding_id, user_id=user_id, provider="dashscope", purpose="embedding",
                version=1, status="valid", **envelope,
            ),
            ActiveProviderCredential(
                user_id=user_id, purpose="generation", credential_id=old_id,
            ),
            ActiveProviderCredential(
                user_id=user_id, purpose="embedding", credential_id=embedding_id,
            ),
        ])
        await session.commit()

        with (
            patch("api.account.encrypt_api_key", new=AsyncMock(return_value=envelope)),
            patch("api.account.record_audit"),
        ):
            result = await create_provider_credential(
                body=CredentialRequest(
                    provider="dashscope", purpose="generation", api_key="sk-new-generation-key",
                ),
                session=session,
                current_user=user,
            )
        await session.commit()

        old = await session.get(ProviderCredential, old_id)
        embedding = await session.get(ProviderCredential, embedding_id)
        replacement = await session.get(ProviderCredential, uuid.UUID(str(result["id"])))

        selection = await session.scalar(select(ActiveProviderCredential).where(
            ActiveProviderCredential.user_id == user_id,
            ActiveProviderCredential.purpose == "generation",
        ))

    assert old is not None and old.status == "valid"
    assert embedding is not None and embedding.status == "valid"
    assert replacement is not None
    assert replacement.provider == "dashscope"
    assert replacement.purpose == "generation"
    assert replacement.status == "unverified"
    assert selection is not None and selection.credential_id == old_id
    assert result["is_active"] is False
    await engine.dispose()


@pytest.mark.asyncio
async def test_activating_a_saved_connection_switches_selection_without_deleting_backup():
    from api.account import activate_provider_credential
    from services.provider_credentials import selected_provider_credential

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
        await connection.run_sync(ProviderCredential.__table__.create)
        await connection.run_sync(ActiveProviderCredential.__table__.create)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    user_id = uuid.uuid4()
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    envelope = {
        "ciphertext": "ciphertext", "encrypted_data_key": "key", "nonce": "nonce",
        "key_fingerprint": "fingerprint", "key_last_four": "5555",
        "kms_key_version": "test-v1",
    }
    async with factory() as session:
        user = User(
            id=user_id, email="switch@example.com", nickname="Switch",
            password_hash="unused", role="student", is_active=True,
        )
        session.add_all([
            user,
            ProviderCredential(
                id=first_id, user_id=user_id, provider="deepseek", purpose="generation",
                version=1, status="valid", **envelope,
            ),
            ProviderCredential(
                id=second_id, user_id=user_id, provider="dashscope", purpose="generation",
                version=1, status="unverified", **envelope,
            ),
            ActiveProviderCredential(
                user_id=user_id, purpose="generation", credential_id=first_id,
            ),
        ])
        await session.commit()

        with patch("api.account.record_audit"):
            result = await activate_provider_credential(
                credential_id=str(second_id), session=session, current_user=user,
            )
        await session.commit()
        selected = await selected_provider_credential(session, user_id, "generation")
        first = await session.get(ProviderCredential, first_id)

    assert result["is_active"] is True
    assert selected is not None and selected.id == second_id
    assert first is not None and first.status == "valid"
    await engine.dispose()


@pytest.mark.asyncio
async def test_successful_validation_does_not_change_the_active_credential():
    from api.account import validate_provider_credential

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
        await connection.run_sync(ProviderCredential.__table__.create)
        await connection.run_sync(ActiveProviderCredential.__table__.create)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    user_id = uuid.uuid4()
    active_id = uuid.uuid4()
    recovering_id = uuid.uuid4()
    envelope = {
        "ciphertext": "ciphertext",
        "encrypted_data_key": "key",
        "nonce": "nonce",
        "key_fingerprint": "fingerprint",
        "key_last_four": "5555",
        "kms_key_version": "test-v1",
    }
    async with factory() as session:
        user = User(
            id=user_id, email="validate@example.com", nickname="Validate",
            password_hash="unused", role="student", is_active=True,
        )
        session.add_all([
            user,
            ProviderCredential(
                id=active_id, user_id=user_id, provider="deepseek", purpose="generation",
                version=1, status="valid", **envelope,
            ),
            ActiveProviderCredential(
                user_id=user_id, purpose="generation", credential_id=active_id,
            ),
            ProviderCredential(
                id=recovering_id, user_id=user_id, provider="dashscope", purpose="generation",
                version=1, status="invalid", **envelope,
            ),
        ])
        await session.commit()

        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock()
        with (
            patch("api.account.decrypt_api_key", new=AsyncMock(return_value="sk-valid-key")),
            patch("api.account.AsyncOpenAI", return_value=mock_client),
            patch("api.account.record_audit"),
        ):
            await validate_provider_credential(
                credential_id=str(recovering_id), session=session, current_user=user,
            )
        await session.commit()

        active = await session.get(ProviderCredential, active_id)
        recovering = await session.get(ProviderCredential, recovering_id)
        selection = await session.scalar(select(ActiveProviderCredential).where(
            ActiveProviderCredential.user_id == user_id,
            ActiveProviderCredential.purpose == "generation",
        ))

    assert active is not None and active.status == "valid"
    assert recovering is not None and recovering.status == "valid"
    assert selection is not None and selection.credential_id == active_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_envelope_encryption_round_trip_never_persists_plaintext():
    user_id = uuid.uuid4()
    secret = "sk-sensitive-provider-key"
    with patch("services.provider_credentials.get_settings", return_value=_settings()):
        envelope = await encrypt_api_key(
            secret, user_id=user_id, provider="deepseek", purpose="generation", version=1
        )
        same_secret = await encrypt_api_key(
            secret, user_id=user_id, provider="deepseek", purpose="generation", version=2
        )
        different_secret = await encrypt_api_key(
            "sk-different-provider-key",
            user_id=user_id,
            provider="deepseek",
            purpose="generation",
            version=3,
        )
        row = ProviderCredential(
            id=uuid.uuid4(), user_id=user_id, provider="deepseek", purpose="generation",
            version=1, status="valid", **envelope,
        )
        serialized = repr(envelope)
        assert secret not in serialized
        assert len(envelope["key_fingerprint"]) == 64
        assert envelope["key_fingerprint"] == same_secret["key_fingerprint"]
        assert envelope["key_fingerprint"] != different_secret["key_fingerprint"]
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
    from services import totp
    with patch.object(totp.time, "time", return_value=1_700_000_000):
        counter = 1_700_000_000 // 30
        code = totp._code(secret, counter)
        assert verify_code(secret, code, now=1_700_000_000)
        assert not verify_code(secret, "000000", now=1_700_000_000)


def test_registration_pow_challenge_is_signed_and_bounded():
    import base64 as b64
    import hashlib

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


@pytest.mark.asyncio
async def test_byok_reservation_is_audited_without_consuming_generation_quota():
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
            id=user_id, email="byok-quota@example.com", nickname="BYOK",
            password_hash="unused", role="student", is_active=True,
        ))
        await session.commit()
        with patch("services.quota.get_settings", return_value=_settings()):
            for index in range(4):
                assert await reserve_quota(
                    session,
                    user_id=user_id,
                    resource="generation",
                    idempotency_key=f"byok-{index}",
                    count_toward_limit=False,
                ) is True

            bucket = await session.scalar(select(UsageBucket).where(
                UsageBucket.user_id == user_id,
                UsageBucket.resource == "generation",
            ))
            rows = list((await session.scalars(select(UsageLedger).where(
                UsageLedger.user_id == user_id,
                UsageLedger.resource == "generation",
            ))).all())

            assert bucket is None
            assert len(rows) == 4
            assert all(row.amount == 0 for row in rows)
            assert all(row.details.get("_quota_metered") is False for row in rows)
    await engine.dispose()
