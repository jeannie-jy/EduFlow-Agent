"""One-time account tokens and SMTP delivery without persisting plaintext tokens."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import AuthOneTimeToken, User


def hash_one_time_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_one_time_token(
    session: AsyncSession, user: User, purpose: str,
) -> str:
    now = datetime.now(timezone.utc)
    await session.execute(update(AuthOneTimeToken).where(
        AuthOneTimeToken.user_id == user.id,
        AuthOneTimeToken.purpose == purpose,
        AuthOneTimeToken.consumed_at.is_(None),
    ).values(consumed_at=now))
    token = secrets.token_urlsafe(32)
    session.add(AuthOneTimeToken(
        id=uuid.uuid4(), user_id=user.id, purpose=purpose,
        token_hash=hash_one_time_token(token),
        expires_at=now + timedelta(minutes=get_settings().auth_token_minutes),
    ))
    await session.flush()
    return token


def _send_smtp(recipient: str, subject: str, body: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
        if settings.smtp_starttls:
            client.starttls()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)


async def send_account_email(user: User, token: str, purpose: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        if settings.auth_require_email_verification:
            raise RuntimeError("SMTP is not configured")
        return
    if purpose == "verify_email":
        subject = "验证你的 EduFlow 邮箱"
        action = "verify-email"
    else:
        subject = "重置你的 EduFlow 密码"
        action = "reset-password"
    url = f"{settings.public_origin.rstrip('/')}/{action}#token={token}"
    body = f"请在 {settings.auth_token_minutes} 分钟内打开以下链接：\n\n{url}\n\n如果不是你发起的操作，请忽略此邮件。"
    await asyncio.to_thread(_send_smtp, user.email, subject, body)
