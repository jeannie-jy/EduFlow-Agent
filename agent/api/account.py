"""Self-service BYOK credentials and usage metadata."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_readonly_session, get_session
from db.models import ProviderCredential, User
from services.audit import record_audit
from services.provider_credentials import (
    CredentialConfigurationError,
    CredentialUnavailableError,
    decrypt_api_key,
    encrypt_api_key,
    public_credential,
)
from services.quota import usage_snapshot

from .auth import get_current_user

router = APIRouter(prefix="/me", tags=["account"])


class CredentialRequest(BaseModel):
    provider: Literal["deepseek", "dashscope"]
    purpose: Literal["generation", "embedding"]
    api_key: str = Field(min_length=8, max_length=1000)


class UsageLimitRequest(BaseModel):
    task_max_tokens: int | None = Field(default=None, ge=1, le=10_000_000)
    monthly_reference_cost_usd: float | None = Field(default=None, ge=0.01, le=10_000)

    @model_validator(mode="after")
    def require_change(self) -> UsageLimitRequest:
        if self.task_max_tokens is None and self.monthly_reference_cost_usd is None:
            raise ValueError("At least one usage limit is required")
        return self


class TotpCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=12)


class ConsentRequest(BaseModel):
    policy: Literal["model_processing"]
    policy_version: str = Field(min_length=1, max_length=50)
    accepted: bool = True


def _user(user: User | None) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _validate_pair(provider: str, purpose: str) -> None:
    if provider == "deepseek" and purpose != "generation":
        raise HTTPException(status_code=422, detail="DeepSeek is supported for generation only")


@router.get("/provider-credentials")
async def list_provider_credentials(
    session: AsyncSession = Depends(get_readonly_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, object]:
    user = _user(current_user)
    rows = list((await session.scalars(
        select(ProviderCredential)
        .where(ProviderCredential.user_id == user.id)
        .order_by(ProviderCredential.created_at.desc())
    )).all())
    return {"items": [public_credential(row) for row in rows]}


@router.post("/provider-credentials", status_code=201)
async def create_provider_credential(
    body: CredentialRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, object]:
    user = _user(current_user)
    _validate_pair(body.provider, body.purpose)
    # Serialize rotations for one owner so concurrent requests cannot select the
    # same credential version or revoke the just-created replacement.
    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    max_version = await session.scalar(select(func.max(ProviderCredential.version)).where(
        ProviderCredential.user_id == user.id,
        ProviderCredential.provider == body.provider,
        ProviderCredential.purpose == body.purpose,
    ))
    version = int(max_version or 0) + 1
    try:
        envelope = await encrypt_api_key(
            body.api_key, user_id=user.id, provider=body.provider,
            purpose=body.purpose, version=version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Provider API key must contain 8 to 1000 non-whitespace characters") from exc
    except (CredentialConfigurationError, CredentialUnavailableError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await session.execute(update(ProviderCredential).where(
        ProviderCredential.user_id == user.id,
        ProviderCredential.provider == body.provider,
        ProviderCredential.purpose == body.purpose,
        ProviderCredential.status == "active",
    ).values(status="revoked"))
    row = ProviderCredential(
        id=uuid.uuid4(), user_id=user.id, provider=body.provider,
        purpose=body.purpose, version=version, status="active", **envelope,
    )
    session.add(row)
    await session.flush()
    record_audit(
        session, action="credential.rotate", resource_type="provider_credential",
        resource_id=str(row.id), actor_id=user.id,
        details={"provider": row.provider, "purpose": row.purpose, "version": row.version},
    )
    return public_credential(row)


async def _owned_credential(
    credential_id: str, user: User, session: AsyncSession,
) -> ProviderCredential:
    try:
        parsed = uuid.UUID(credential_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Credential not found") from exc
    row = await session.scalar(select(ProviderCredential).where(
        ProviderCredential.id == parsed, ProviderCredential.user_id == user.id,
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return row


@router.post("/provider-credentials/{credential_id}/validate")
async def validate_provider_credential(
    credential_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, object]:
    user = _user(current_user)
    row = await _owned_credential(credential_id, user, session)
    if row.status == "revoked":
        raise HTTPException(status_code=409, detail="Credential is revoked")
    from services.provider_credentials import _endpoint_model
    endpoint, model = _endpoint_model(row.provider, row.purpose)
    client = None
    try:
        client = AsyncOpenAI(
            base_url=endpoint, api_key=await decrypt_api_key(row), max_retries=0, timeout=15.0
        )
        if row.purpose == "embedding":
            # A tiny synthetic input checks the embedding permission without
            # sending any user material to the provider.
            await client.embeddings.create(model=model, input="eduflow-credential-check")
        else:
            await client.models.list()
    except (CredentialConfigurationError, CredentialUnavailableError) as exc:
        raise HTTPException(status_code=503, detail="Credential service is unavailable") from exc
    except Exception as exc:
        # A provider-auth rejection makes this version unusable; transport,
        # timeout and 5xx failures are transient and must not revoke a valid
        # user key or force a needless rotation.
        provider_status = getattr(exc, "status_code", None)
        if provider_status in {401, 403}:
            row.status = "invalid"
            record_audit(
                session, action="credential.validate_failed", resource_type="provider_credential",
                resource_id=str(row.id), actor_id=user.id,
                details={"provider": row.provider, "purpose": row.purpose, "status_code": provider_status},
            )
            await session.commit()
            raise HTTPException(status_code=422, detail="Provider rejected the credential") from exc
        raise HTTPException(status_code=503, detail="Provider validation is temporarily unavailable") from exc
    finally:
        if client is not None:
            await client.close()
    row.status = "active"
    row.validated_at = datetime.now(UTC)
    record_audit(
        session, action="credential.validate", resource_type="provider_credential",
        resource_id=str(row.id), actor_id=user.id,
        details={"provider": row.provider, "purpose": row.purpose},
    )
    return public_credential(row)


@router.delete("/provider-credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_provider_credential(
    credential_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
) -> None:
    user = _user(current_user)
    row = await _owned_credential(credential_id, user, session)
    row.status = "revoked"
    record_audit(
        session, action="credential.revoke", resource_type="provider_credential",
        resource_id=str(row.id), actor_id=user.id,
        details={"provider": row.provider, "purpose": row.purpose, "version": row.version},
    )


@router.get("/usage")
async def get_usage(
    session: AsyncSession = Depends(get_readonly_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, object]:
    return await usage_snapshot(session, _user(current_user).id)


@router.put("/usage-limits")
async def update_usage_limits(
    body: UsageLimitRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, object]:
    from db.models import UserQuotaPolicy
    user = _user(current_user)
    policy = await session.get(UserQuotaPolicy, user.id)
    previous = dict(policy.limits or {}) if policy else {}
    limits = dict(previous)
    if body.task_max_tokens is not None:
        limits["task_max_tokens"] = body.task_max_tokens
    if body.monthly_reference_cost_usd is not None:
        limits["monthly_reference_cost_usd"] = body.monthly_reference_cost_usd
    if policy is None:
        session.add(UserQuotaPolicy(user_id=user.id, limits=limits, is_suspended=False))
    else:
        policy.limits = limits
    record_audit(
        session, action="account.usage_limits.update", resource_type="user",
        resource_id=str(user.id), actor_id=user.id,
        details={"before": previous, "after": limits},
    )
    await session.flush()
    return {"limits": limits}


@router.post("/consents", status_code=201)
async def record_consent(
    body: ConsentRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, object]:
    """Record explicit model/material processing consent per policy version."""
    from db.models import UserConsent

    user = _user(current_user)
    if not body.accepted:
        return {"policy": body.policy, "policy_version": body.policy_version, "accepted": False}
    existing = await session.scalar(select(UserConsent).where(
        UserConsent.user_id == user.id,
        UserConsent.policy == body.policy,
        UserConsent.policy_version == body.policy_version,
    ))
    if existing is None:
        existing = UserConsent(
            id=uuid.uuid4(), user_id=user.id, policy=body.policy,
            policy_version=body.policy_version,
        )
        session.add(existing)
        record_audit(
            session, action="consent.record", resource_type="user_consent",
            resource_id=str(existing.id), actor_id=user.id,
            details={"policy": body.policy, "policy_version": body.policy_version},
        )
        await session.flush()
    return {
        "policy": body.policy,
        "policy_version": body.policy_version,
        "accepted": True,
        "accepted_at": existing.accepted_at,
    }


@router.get("/consents")
async def list_consents(
    session: AsyncSession = Depends(get_readonly_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, object]:
    from db.models import UserConsent

    user = _user(current_user)
    rows = list((await session.scalars(select(UserConsent).where(
        UserConsent.user_id == user.id
    ).order_by(UserConsent.accepted_at.desc()))).all())
    return {"items": [
        {"policy": row.policy, "policy_version": row.policy_version, "accepted_at": row.accepted_at}
        for row in rows
    ]}


@router.get("/mfa/totp")
async def get_totp_status(
    session: AsyncSession = Depends(get_readonly_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, object]:
    from db.models import UserMFA
    user = _user(current_user)
    row = await session.get(UserMFA, user.id)
    return {"enabled": bool(row.enabled) if row else False, "confirmed_at": row.confirmed_at if row else None}


@router.post("/mfa/totp/setup")
async def setup_totp(
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, str]:
    from db.models import UserMFA
    from services.provider_credentials import encrypt_user_secret
    from services.totp import new_secret, provisioning_uri
    user = _user(current_user)
    existing = await session.get(UserMFA, user.id)
    if existing is not None and existing.enabled:
        raise HTTPException(status_code=409, detail="TOTP is already enabled")
    secret = new_secret()
    envelope = await encrypt_user_secret(secret, user_id=user.id, purpose="totp")
    if existing is None:
        existing = UserMFA(user_id=user.id, enabled=False, **envelope)
        session.add(existing)
    else:
        for key, value in envelope.items():
            setattr(existing, key, value)
        existing.enabled = False
        existing.confirmed_at = None
    await session.flush()
    record_audit(
        session, action="mfa.totp.setup", resource_type="user",
        resource_id=str(user.id), actor_id=user.id,
    )
    return {"secret": secret, "otpauth_uri": provisioning_uri(secret, email=user.email)}


@router.post("/mfa/totp/confirm")
async def confirm_totp(
    body: TotpCodeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, object]:
    from db.models import UserMFA
    from services.provider_credentials import decrypt_user_secret
    from services.totp import verify_code
    user = _user(current_user)
    row = await session.get(UserMFA, user.id)
    if row is None:
        raise HTTPException(status_code=409, detail="TOTP setup has not been started")
    try:
        secret = await decrypt_user_secret(
            user_id=user.id, purpose="totp", ciphertext=row.secret_ciphertext,
            encrypted_data_key=row.secret_encrypted_data_key, nonce=row.secret_nonce,
            key_version=row.kms_key_version,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="MFA service unavailable") from exc
    if not verify_code(secret, body.code):
        raise HTTPException(status_code=422, detail="Invalid TOTP code")
    row.enabled = True
    row.confirmed_at = datetime.now(UTC)
    record_audit(session, action="mfa.totp.enabled", resource_type="user", resource_id=str(user.id), actor_id=user.id)
    return {"enabled": True, "confirmed_at": row.confirmed_at}


@router.delete("/mfa/totp", status_code=204)
async def disable_totp(
    body: TotpCodeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
) -> None:
    from db.models import UserMFA
    from services.provider_credentials import decrypt_user_secret
    from services.totp import verify_code
    user = _user(current_user)
    row = await session.get(UserMFA, user.id)
    if row is None or not row.enabled:
        return
    try:
        secret = await decrypt_user_secret(
            user_id=user.id, purpose="totp", ciphertext=row.secret_ciphertext,
            encrypted_data_key=row.secret_encrypted_data_key, nonce=row.secret_nonce,
            key_version=row.kms_key_version,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="MFA service unavailable") from exc
    if not verify_code(secret, body.code):
        raise HTTPException(status_code=422, detail="Invalid TOTP code")
    await session.delete(row)
    record_audit(session, action="mfa.totp.disabled", resource_type="user", resource_id=str(user.id), actor_id=user.id)


@router.get("/export")
async def export_account_data(
    session: AsyncSession = Depends(get_readonly_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, object]:
    """Portable metadata export; secrets, password hashes and session tokens are excluded."""
    from db.models import (
        AuditEvent,
        Feedback,
        Material,
        Project,
        ProjectVersion,
        UsageLedger,
        UserConsent,
        WorkflowRun,
    )
    user = _user(current_user)
    projects = list((await session.scalars(
        select(Project).where(Project.owner_id == str(user.id)).order_by(Project.created_at)
    )).all())
    materials = list((await session.scalars(
        select(Material).where(Material.owner_id == user.id).order_by(Material.created_at)
    )).all())
    consents = list((await session.scalars(
        select(UserConsent).where(UserConsent.user_id == user.id)
    )).all())
    ledger = list((await session.scalars(
        select(UsageLedger).where(UsageLedger.user_id == user.id).order_by(UsageLedger.created_at)
    )).all())
    credentials = list((await session.scalars(
        select(ProviderCredential).where(ProviderCredential.user_id == user.id)
    )).all())
    project_ids = [project.id for project in projects]
    feedback = list((await session.scalars(
        select(Feedback).where(Feedback.project_id.in_(project_ids))
    )).all()) if project_ids else []
    versions = list((await session.scalars(
        select(ProjectVersion).where(ProjectVersion.project_id.in_(project_ids)).order_by(ProjectVersion.created_at)
    )).all()) if project_ids else []
    traces = list((await session.scalars(
        select(WorkflowRun).where(WorkflowRun.project_id.in_(project_ids)).order_by(WorkflowRun.started_at)
    )).all()) if project_ids else []
    audit_events = list((await session.scalars(
        select(AuditEvent).where(AuditEvent.actor_id == user.id).order_by(AuditEvent.created_at)
    )).all())
    return {
        "exported_at": datetime.now(UTC),
        "profile": {"id": str(user.id), "email": user.email, "nickname": user.nickname, "role": user.role, "created_at": user.created_at},
        "projects": [{"id": str(row.id), "title": row.title, "status": row.status, "dsl": row.dsl_snapshot, "created_at": row.created_at, "updated_at": row.updated_at} for row in projects],
        "materials": [{"id": str(row.id), "filename": row.original_filename, "media_type": row.media_type, "size_bytes": row.size_bytes, "status": row.status, "created_at": row.created_at} for row in materials],
        "feedback": [{"id": str(row.id), "project_id": str(row.project_id), "frame_id": str(row.frame_id) if row.frame_id else None, "type": row.type, "content": row.content, "rating": row.rating, "resolved": row.resolved, "created_at": row.created_at} for row in feedback],
        "project_versions": [{"id": str(row.id), "project_id": str(row.project_id), "version": row.version, "change_summary": row.change_summary, "dsl": row.dsl_snapshot, "created_at": row.created_at} for row in versions],
        "workflow_traces": [{"id": str(row.id), "project_id": str(row.project_id), "thread_id": row.thread_id, "entrypoint": row.entrypoint, "status": row.status, "input_tokens": row.input_tokens, "output_tokens": row.output_tokens, "estimated_cost_usd": row.estimated_cost_usd, "started_at": row.started_at, "completed_at": row.completed_at} for row in traces],
        "provider_credentials": [public_credential(row) for row in credentials],
        "consents": [{"policy": row.policy, "policy_version": row.policy_version, "accepted_at": row.accepted_at} for row in consents],
        "usage_ledger": [{"resource": row.resource, "amount": row.amount, "details": row.details, "created_at": row.created_at} for row in ledger],
        "audit_events": [{"id": row.id, "action": row.action, "resource_type": row.resource_type, "resource_id": row.resource_id, "request_id": row.request_id, "details": row.details, "created_at": row.created_at} for row in audit_events],
    }


@router.post("/deletion-request", status_code=202)
async def request_account_deletion(
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, object]:
    from db.models import AccountDeletionRequest, AuthSession
    user = _user(current_user)
    # Serialize duplicate clicks from multiple devices so the cooling-off
    # deadline and audit record remain single-valued.
    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    existing = await session.scalar(select(AccountDeletionRequest).where(
        AccountDeletionRequest.user_id == user.id
    ))
    if existing is None:
        existing = AccountDeletionRequest(
            id=uuid.uuid4(), user_id=user.id,
            execute_after=datetime.now(UTC) + timedelta(days=7),
        )
        session.add(existing)
    await session.execute(update(AuthSession).where(AuthSession.user_id == user.id).values(
        expires_at=datetime.now(UTC)
    ))
    record_audit(
        session, action="account.deletion_requested", resource_type="user",
        resource_id=str(user.id), actor_id=user.id,
        details={"execute_after": existing.execute_after.isoformat()},
    )
    return {"status": "scheduled", "execute_after": existing.execute_after}


@router.delete("/deletion-request", status_code=204)
async def cancel_account_deletion(
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
) -> None:
    from sqlalchemy import delete

    from db.models import AccountDeletionRequest
    user = _user(current_user)
    await session.execute(delete(AccountDeletionRequest).where(
        AccountDeletionRequest.user_id == user.id
    ))
    record_audit(
        session, action="account.deletion_cancelled", resource_type="user",
        resource_id=str(user.id), actor_id=user.id,
    )
