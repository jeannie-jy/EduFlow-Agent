"""Authentication hashing, session, and production gate tests."""

from http.cookies import SimpleCookie
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from api.auth import (
    LoginRequest,
    RegisterRequest,
    get_current_user,
    login,
    register,
)
from services.auth_service import hash_password, verify_password


def _request(ip: str = "127.0.0.1") -> Request:
    return Request({"type": "http", "client": (ip, 12345), "headers": []})


@pytest.fixture(autouse=True)
def _disable_external_rate_limiter():
    with patch("api.auth.check_rate_limit", new=AsyncMock(return_value=None)):
        yield


@pytest_asyncio.fixture
async def auth_db():
    from db.models import AuditEvent, AuthSession, User

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
        await connection.run_sync(AuthSession.__table__.create)
        await connection.run_sync(AuditEvent.__table__.create)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def test_scrypt_password_hash_is_salted_and_verifiable():
    first = hash_password("correct-horse-42")
    second = hash_password("correct-horse-42")

    assert first != second
    assert verify_password("correct-horse-42", first)
    assert not verify_password("wrong-password", first)


@pytest.mark.asyncio
async def test_register_issues_httponly_cookie_and_me_resolves_session(auth_db):
    response = Response()
    user_data = await register(
        RegisterRequest(
            email="  Learner@Example.com ",
            nickname="Learner",
            password="secure-pass-42",
        ),
        _request(),
        response,
        auth_db,
    )
    await auth_db.commit()

    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    morsel = cookie["eduflow_session"]
    resolved = await get_current_user(morsel.value, auth_db)

    assert user_data["email"] == "learner@example.com"
    assert user_data["role"] == "teacher"
    assert resolved is not None
    assert str(resolved.id) == user_data["id"]
    assert morsel["httponly"] is True
    assert morsel["samesite"].lower() == "lax"
    from db.models import AuditEvent

    audit = await auth_db.scalar(select(AuditEvent))
    assert audit is not None
    assert audit.action == "auth.register"
    assert audit.resource_id == user_data["id"]


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(auth_db):
    await register(
        RegisterRequest(
            email="owner@example.com",
            nickname="Owner",
            password="secure-pass-42",
        ),
        _request("127.0.0.2"),
        Response(),
        auth_db,
    )
    await auth_db.commit()

    with pytest.raises(HTTPException) as exc:
        await login(
            LoginRequest(email="owner@example.com", password="wrong"),
            _request("127.0.0.3"),
            Response(),
            auth_db,
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_cookie_is_rejected_when_auth_is_required():
    with patch(
        "api.auth.get_settings",
        return_value=MagicMock(auth_required=True),
    ):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(None, MagicMock())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_process_fallback_rate_limiter_blocks_after_limit():
    from services.rate_limit import _fallback, check_rate_limit

    _fallback.clear()
    with patch("api.export._get_redis", new=AsyncMock(return_value=None)):
        assert await check_rate_limit("test", "same-client", limit=2, window_seconds=60) is None
        assert await check_rate_limit("test", "same-client", limit=2, window_seconds=60) is None
        retry_after = await check_rate_limit(
            "test", "same-client", limit=2, window_seconds=60
        )
    assert retry_after is not None
    assert retry_after > 0


@pytest.mark.asyncio
async def test_student_cannot_use_editor_role_dependency():
    from api.auth import require_editor

    with pytest.raises(HTTPException) as caught:
        await require_editor(MagicMock(role="student"))
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_cross_project_owner_boundary():
    from api.auth import require_project_owner

    project_id = "11111111-1111-1111-1111-111111111111"
    request = Request({
        "type": "http",
        "path_params": {"project_id": project_id},
        "headers": [],
    })
    admin = MagicMock(id="admin-id", role="admin")
    session = MagicMock()
    session.get = AsyncMock(return_value=MagicMock(owner_id="different-owner"))

    assert await require_project_owner(request, admin, session) is admin
