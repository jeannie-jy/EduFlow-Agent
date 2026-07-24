# Backend MVP Email Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add secure email/password authentication, refresh-session rotation, and per-user resource isolation to the EduFlow-Agent FastAPI backend.

**Architecture:** Keep HTTP concerns in `api/auth.py`, database transactions in `services/auth_service.py`, and cryptographic primitives in `security/`. Use 15-minute HS256 Access JWTs plus opaque 30-day Refresh Tokens stored as SHA-256 hashes in PostgreSQL. Authenticate every business route and enforce ownership with `id + owner_id` queries that return 404 for foreign resources.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2 async, PostgreSQL 16, Alembic async migrations, PyJWT, pwdlib Argon2, Redis, pytest, pytest-asyncio, httpx.

## Global Constraints

- `PyJWT>=2.10,<3`
- `pwdlib[argon2]>=0.3,<1`
- `email-validator>=2.2,<3`
- Access Token lifetime is exactly 900 seconds by default.
- Refresh Token lifetime is exactly 30 days by default.
- Refresh Tokens are generated with `secrets.token_urlsafe(48)` and only their SHA-256 hashes are stored.
- Access JWTs require `sub`, `sid`, `type`, `jti`, `iss`, `aud`, `iat`, `nbf`, and `exp`.
- JWT decode algorithms are fixed by server configuration and never read from the token header.
- Passwords contain 8 to 128 characters, at least one letter and one number, and no more than 256 UTF-8 bytes.
- Access Tokens and raw Refresh Tokens must never be written to logs or database columns.
- Foreign and missing resources both return 404.
- Existing anonymous records remain hidden until explicitly assigned; never assign them to the first registrant.
- Preserve unrelated working-tree changes in `.gitignore`, `docs/ui-audit/`, and `web/src/lib/auth*`.

---

## File Structure

### New files

- `agent/security/__init__.py`: security package marker.
- `agent/security/passwords.py`: password normalization, policy, hashing, and verification.
- `agent/security/tokens.py`: Access JWT and opaque Refresh Token primitives.
- `agent/schema/auth.py`: authentication request and response models.
- `agent/services/auth_service.py`: registration, login, session rotation, and revocation transactions.
- `agent/api/auth.py`: authentication HTTP endpoints and cookie helpers.
- `agent/api/auth_errors.py`: typed authentication HTTP error constructors.
- `agent/api/ownership.py`: reusable project and material ownership queries.
- `agent/services/auth_rate_limit.py`: Redis-backed authentication rate limiting.
- `agent/tests/test_auth_security.py`: password and token unit tests.
- `agent/tests/test_auth_service.py`: authentication service tests.
- `agent/tests/test_auth_api.py`: API, Cookie, and error-contract tests.
- `agent/tests/test_resource_isolation.py`: two-user ownership tests.
- `agent/tests/test_auth_postgres.py`: PostgreSQL-only concurrency tests.
- `agent/alembic/versions/20260724_0001_existing_schema_baseline.py`: generated baseline for current ORM schema.
- `agent/alembic/versions/20260724_0002_mvp_authentication.py`: generated authentication and ownership migration.

### Modified files

- `agent/requirements.txt`: authentication libraries.
- `agent/config.py`: JWT, Cookie, CORS, and rate-limit settings.
- `.env.example`: non-secret authentication configuration and required secret placeholder.
- `docker-compose.yml`: pass authentication configuration into the API container.
- `agent/alembic/env.py`: async Alembic execution.
- `agent/db/models.py`: `User`, `AuthSession`, and ownership columns.
- `agent/api/deps.py`: `CurrentUser` dependency.
- `agent/api/router.py`: authentication router registration.
- `agent/main.py`: configurable CORS origins.
- `agent/api/projects.py`: project ownership.
- `agent/api/generate.py`: generation and SSE ownership.
- `agent/api/frames.py`: frame ownership.
- `agent/api/parameters.py`: parameter ownership.
- `agent/api/materials.py`: material persistence and ownership.
- `agent/api/feedback.py`: feedback ownership.
- `agent/api/versions.py`: version ownership.
- `agent/api/export.py`: export job and download ownership.
- `agent/api/knowledge.py`: authenticated access.
- `agent/services/generate_service.py`: internal-only project access contract.
- `agent/tests/conftest.py`: user, session, and authenticated-client fixtures.
- `agent/tests/test_db_integration.py`: ORM relationship and constraint coverage.
- `agent/tests/test_api_integration.py`: adapt existing API tests to authentication.
- `.github/workflows/backend-ci.yml`: PostgreSQL service and strict warning/test stages.

---

### Task 1: Establish an Async Alembic Baseline

**Files:**
- Modify: `agent/alembic/env.py`
- Create: `agent/alembic/versions/20260724_0001_existing_schema_baseline.py`
- Test: `agent/tests/test_alembic_migrations.py`

**Interfaces:**
- Consumes: `config.get_settings().database_url`, `db.models.Base.metadata`
- Produces: `run_async_migrations() -> None` and an Alembic baseline that upgrades an empty PostgreSQL database to the pre-authentication schema

- [ ] **Step 1: Write the failing migration-environment test**

```python
# agent/tests/test_alembic_migrations.py
from pathlib import Path


def test_alembic_env_uses_async_engine() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "alembic" / "env.py"
    ).read_text(encoding="utf-8")
    assert "async_engine_from_config" in source
    assert "asyncio.run(run_async_migrations())" in source
    assert "from sqlalchemy import engine_from_config" not in source
```

- [ ] **Step 2: Run the test and verify the current sync environment fails**

Run from `agent/`:

```powershell
python -m pytest tests/test_alembic_migrations.py -v
```

Expected: FAIL because `env.py` imports `engine_from_config`.

- [ ] **Step 3: Replace online migration execution with the async pattern**

Use this structure in `agent/alembic/env.py`:

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from config import get_settings
from db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url",
    get_settings().database_url.replace("%", "%%"),
)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
```

- [ ] **Step 4: Generate and inspect the pre-authentication baseline**

Start a disposable empty PostgreSQL database and point `DATABASE_URL` at it. From `agent/` run:

```powershell
$env:DATABASE_URL='postgresql+asyncpg://agent:changeme@localhost:5433/eduflow_auth_plan'
python -m alembic revision --autogenerate --rev-id 20260724_0001 -m "existing schema baseline"
```

Expected: one revision under `agent/alembic/versions/` containing `op.create_table` for every model currently declared in `db/models.py`.

Inspect the revision and verify it creates:

```text
projects
frames
parameters
quality_reports
export_jobs
feedback
source_materials
project_versions
```

Do not add `users` or `auth_sessions` in this baseline.

- [ ] **Step 5: Verify empty-database upgrade and downgrade**

Run:

```powershell
python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head
```

Expected: all three commands exit 0.

- [ ] **Step 6: Run the migration test**

Run:

```powershell
python -m pytest tests/test_alembic_migrations.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add agent/alembic/env.py agent/alembic/versions agent/tests/test_alembic_migrations.py
git commit -m "build: establish async alembic baseline"
```

---

### Task 2: Add Authentication Dependencies and Configuration

**Files:**
- Modify: `agent/requirements.txt`
- Modify: `agent/config.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `agent/tests/conftest.py`
- Test: `agent/tests/test_auth_security.py`

**Interfaces:**
- Consumes: `pydantic_settings.BaseSettings`
- Produces: `Settings.auth_jwt_secret`, `auth_jwt_algorithm`, `auth_jwt_issuer`, `auth_jwt_audience`, `auth_access_token_seconds`, `auth_refresh_token_days`, `auth_refresh_cookie_name`, `auth_cookie_secure`, `auth_cookie_samesite`, and `cors_allowed_origins`

- [ ] **Step 1: Write failing settings tests**

```python
from pydantic import SecretStr

from config import Settings


def test_auth_settings_defaults() -> None:
    settings = Settings(
        AUTH_JWT_SECRET="x" * 64,
        _env_file=None,
    )
    assert isinstance(settings.auth_jwt_secret, SecretStr)
    assert settings.auth_access_token_seconds == 900
    assert settings.auth_refresh_token_days == 30
    assert settings.auth_refresh_cookie_name == "eduflow_refresh"
    assert settings.auth_cookie_samesite == "lax"


def test_auth_secret_is_required() -> None:
    try:
        Settings(_env_file=None)
    except ValueError as exc:
        assert "AUTH_JWT_SECRET" in str(exc)
    else:
        raise AssertionError("AUTH_JWT_SECRET must be required")
```

- [ ] **Step 2: Run the settings tests and verify failure**

Run:

```powershell
python -m pytest tests/test_auth_security.py -v
```

Expected: FAIL because the authentication fields do not exist.

- [ ] **Step 3: Add dependencies**

Append to `agent/requirements.txt`:

```text
# ── Authentication ────────────────────────────────────────
PyJWT>=2.10,<3
pwdlib[argon2]>=0.3,<1
email-validator>=2.2,<3
```

- [ ] **Step 4: Add exact Settings fields**

```python
from pydantic import Field, SecretStr

auth_jwt_secret: SecretStr = Field(alias="AUTH_JWT_SECRET")
auth_jwt_algorithm: str = "HS256"
auth_jwt_issuer: str = "eduflow-agent"
auth_jwt_audience: str = "eduflow-web"
auth_access_token_seconds: int = 900
auth_refresh_token_days: int = 30
auth_refresh_cookie_name: str = "eduflow_refresh"
auth_cookie_secure: bool = True
auth_cookie_samesite: str = "lax"
cors_allowed_origins: list[str] = ["http://localhost:5173"]
```

- [ ] **Step 5: Add environment examples and container forwarding**

Add to `.env.example`:

```text
AUTH_JWT_SECRET=replace-with-at-least-64-random-characters
AUTH_ACCESS_TOKEN_SECONDS=900
AUTH_REFRESH_TOKEN_DAYS=30
AUTH_COOKIE_SECURE=false
CORS_ALLOWED_ORIGINS=["http://localhost:5173"]
```

Add to the `agent-api` environment section of `docker-compose.yml`:

```yaml
- AUTH_JWT_SECRET=${AUTH_JWT_SECRET}
- AUTH_ACCESS_TOKEN_SECONDS=${AUTH_ACCESS_TOKEN_SECONDS:-900}
- AUTH_REFRESH_TOKEN_DAYS=${AUTH_REFRESH_TOKEN_DAYS:-30}
- AUTH_COOKIE_SECURE=${AUTH_COOKIE_SECURE:-false}
- 'CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS:-["http://localhost:5173"]}'
```

- [ ] **Step 6: Provide a test-only JWT secret before application imports**

At the top of `agent/tests/conftest.py`, before importing application modules:

```python
import os

os.environ.setdefault(
    "AUTH_JWT_SECRET",
    "pytest-only-secret-with-at-least-sixty-four-characters-000000000000",
)
```

This keeps production configuration required while allowing the existing test suite to import `db.database`.

- [ ] **Step 7: Install dependencies and run tests**

Run:

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/test_auth_security.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add agent/requirements.txt agent/config.py .env.example docker-compose.yml agent/tests/conftest.py agent/tests/test_auth_security.py
git commit -m "feat: configure authentication dependencies"
```

---

### Task 3: Implement Password and Token Primitives

**Files:**
- Create: `agent/security/__init__.py`
- Create: `agent/security/passwords.py`
- Create: `agent/security/tokens.py`
- Test: `agent/tests/test_auth_security.py`

**Interfaces:**
- Produces: `normalize_email(value: str) -> str`
- Produces: `validate_password_policy(password: str) -> str`
- Produces: `hash_password(password: str) -> str`
- Produces: `verify_password(password: str, encoded_hash: str) -> tuple[bool, str | None]`
- Produces: `create_access_token(user_id: UUID, session_id: UUID) -> IssuedAccessToken`
- Produces: `decode_access_token(token: str) -> AccessTokenClaims`
- Produces: `generate_refresh_token() -> str`
- Produces: `hash_refresh_token(token: str) -> str`

- [ ] **Step 1: Add failing password and token tests**

```python
from uuid import uuid4

import pytest

from security.passwords import (
    hash_password,
    normalize_email,
    validate_password_policy,
    verify_password,
)
from security.tokens import (
    AccessTokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)


def test_normalize_email() -> None:
    assert normalize_email(" Student@Example.COM ") == "student@example.com"


@pytest.mark.parametrize("password", ["short1", "abcdefgh", "12345678"])
def test_password_policy_rejects_invalid_values(password: str) -> None:
    with pytest.raises(ValueError):
        validate_password_policy(password)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("learning2026")
    valid, replacement = verify_password("learning2026", encoded)
    assert valid is True
    assert replacement is None
    assert verify_password("wrong2026", encoded)[0] is False


def test_access_token_round_trip(monkeypatch) -> None:
    user_id = uuid4()
    session_id = uuid4()
    issued = create_access_token(user_id, session_id)
    claims = decode_access_token(issued.token)
    assert claims.user_id == user_id
    assert claims.session_id == session_id
    assert issued.expires_in == 900


def test_refresh_token_is_opaque_and_hash_is_stable() -> None:
    token = generate_refresh_token()
    assert len(token) >= 64
    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert token not in hash_refresh_token(token)
```

- [ ] **Step 2: Run tests and verify import failures**

Run:

```powershell
python -m pytest tests/test_auth_security.py -v
```

Expected: FAIL because `security.passwords` and `security.tokens` do not exist.

- [ ] **Step 3: Implement password primitives**

```python
# agent/security/passwords.py
from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = _password_hash.hash("not-a-real-user-password-2026")


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def validate_password_policy(password: str) -> str:
    if not 8 <= len(password) <= 128:
        raise ValueError("密码长度必须为 8 至 128 个字符")
    if len(password.encode("utf-8")) > 256:
        raise ValueError("密码编码后不能超过 256 字节")
    if not any(character.isalpha() for character in password):
        raise ValueError("密码必须包含字母")
    if not any(character.isdigit() for character in password):
        raise ValueError("密码必须包含数字")
    return password


def hash_password(password: str) -> str:
    return _password_hash.hash(validate_password_policy(password))


def verify_password(
    password: str,
    encoded_hash: str,
) -> tuple[bool, str | None]:
    return _password_hash.verify_and_update(password, encoded_hash)
```

- [ ] **Step 4: Implement token primitives**

Implement the dataclasses and functions exactly as specified in the design:

```python
# agent/security/tokens.py
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid

import jwt

from config import get_settings


class AccessTokenError(Exception):
    pass


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
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        seconds=settings.auth_access_token_seconds
    )
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
                    "sub", "sid", "type", "jti",
                    "iss", "aud", "iat", "nbf", "exp",
                ]
            },
        )
        if payload["type"] != "access":
            raise AccessTokenError
        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            session_id=uuid.UUID(payload["sid"]),
            token_id=uuid.UUID(payload["jti"]),
            expires_at=datetime.fromtimestamp(
                payload["exp"],
                tz=timezone.utc,
            ),
        )
    except (
        jwt.InvalidTokenError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise AccessTokenError from exc


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

- [ ] **Step 5: Add malformed, expired, and wrong-algorithm tests**

Add tests that assert `AccessTokenError` for:

```python
@pytest.mark.parametrize(
    "token",
    ["", "not-a-jwt", "a.b.c"],
)
def test_decode_rejects_malformed_tokens(token: str) -> None:
    with pytest.raises(AccessTokenError):
        decode_access_token(token)
```

Also construct signed tokens missing `sid`, using `type="refresh"`, and using a different issuer; each must raise `AccessTokenError`.

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_auth_security.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add agent/security agent/tests/test_auth_security.py
git commit -m "feat: add password and token security primitives"
```

---

### Task 4: Add User, AuthSession, and Ownership ORM Models

**Files:**
- Modify: `agent/db/models.py`
- Create: `agent/alembic/versions/20260724_0002_mvp_authentication.py`
- Modify: `agent/tests/test_db_integration.py`

**Interfaces:**
- Produces: `User`
- Produces: `AuthSession`
- Changes: `Project.owner_id` to nullable UUID foreign key
- Changes: `SourceMaterial.project_id` to nullable UUID foreign key
- Adds: `SourceMaterial.owner_id` nullable UUID foreign key for migration compatibility

- [ ] **Step 1: Write failing ORM tests**

```python
async def test_user_email_normalized_is_unique(db_session):
    first = User(
        email="Student@example.com",
        email_normalized="student@example.com",
        nickname="Student",
        password_hash="encoded",
    )
    db_session.add(first)
    await db_session.flush()

    db_session.add(User(
        email="student@example.com",
        email_normalized="student@example.com",
        nickname="Other",
        password_hash="encoded",
    ))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_auth_session_is_deleted_with_user(db_session):
    user = User(
        email="user@example.com",
        email_normalized="user@example.com",
        nickname="User",
        password_hash="encoded",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(AuthSession(
        user_id=user.id,
        family_id=uuid.uuid4(),
        refresh_token_hash="a" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    await db_session.flush()
    await db_session.delete(user)
    await db_session.flush()
    assert await db_session.scalar(
        select(func.count(AuthSession.id))
    ) == 0
```

- [ ] **Step 2: Run tests and verify missing models**

Run:

```powershell
python -m pytest tests/test_db_integration.py -k "user or auth_session" -v
```

Expected: FAIL because `User` and `AuthSession` are undefined.

- [ ] **Step 3: Implement ORM models and relationships**

Add `User` and `AuthSession` with the exact fields and constraints from the approved design. Use named constraints:

```python
UniqueConstraint(
    "email_normalized",
    name="uq_users_email_normalized",
)
UniqueConstraint(
    "refresh_token_hash",
    name="uq_auth_sessions_refresh_token_hash",
)
Index(
    "idx_auth_sessions_user_active",
    "user_id",
    "revoked_at",
)
Index(
    "idx_auth_sessions_family",
    "family_id",
)
```

Add:

```python
Project.owner_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("users.id", ondelete="RESTRICT"),
    nullable=True,
    index=True,
)

SourceMaterial.owner_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("users.id", ondelete="CASCADE"),
    nullable=True,
    index=True,
)

SourceMaterial.project_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("projects.id", ondelete="CASCADE"),
    nullable=True,
)
```

- [ ] **Step 4: Generate the authentication migration**

Upgrade the disposable PostgreSQL database to the baseline, then run:

```powershell
python -m alembic revision --autogenerate --rev-id 20260724_0002 -m "mvp authentication"
```

Expected migration operations:

```text
create users
create auth_sessions
alter projects.owner_id from VARCHAR to UUID using owner_id::uuid
add source_materials.owner_id
alter source_materials.project_id nullable
create ownership and session indexes
```

For legacy non-UUID `projects.owner_id` values, the migration must first set them to NULL:

```python
op.execute(
    "UPDATE projects SET owner_id = NULL "
    "WHERE owner_id IS NOT NULL "
    "AND owner_id !~* "
    "'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    "[89ab][0-9a-f]{3}-[0-9a-f]{12}$'"
)
```

Use an explicit PostgreSQL cast in the alter operation:

```python
postgresql_using="owner_id::uuid"
```

- [ ] **Step 5: Run ORM and migration tests**

Run:

```powershell
python -m pytest tests/test_db_integration.py -v
python -m alembic downgrade base
python -m alembic upgrade head
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit**

```powershell
git add agent/db/models.py agent/alembic/versions agent/tests/test_db_integration.py
git commit -m "feat: add authentication persistence models"
```

---

### Task 5: Add Authentication Schemas and Error Constructors

**Files:**
- Create: `agent/schema/auth.py`
- Create: `agent/api/auth_errors.py`
- Test: `agent/tests/test_auth_api.py`

**Interfaces:**
- Produces: `RegisterRequest`, `LoginRequest`, `UserResponse`, `AuthResponse`
- Produces: `email_registered()`, `invalid_credentials()`, `access_token_invalid()`, `refresh_token_invalid()`, `account_disabled()`, `auth_rate_limited()`

- [ ] **Step 1: Write failing schema and error tests**

```python
from pydantic import ValidationError

from api.auth_errors import invalid_credentials
from schema.auth import RegisterRequest


def test_register_request_normalizes_nickname() -> None:
    request = RegisterRequest(
        email="student@example.com",
        nickname="  小明  ",
        password="learning2026",
    )
    assert request.nickname == "小明"


def test_register_request_rejects_bad_password() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="student@example.com",
            nickname="小明",
            password="password",
        )


def test_invalid_credentials_error_contract() -> None:
    error = invalid_credentials()
    assert error.status_code == 401
    assert error.detail["error"]["code"] == "INVALID_CREDENTIALS"
    assert error.headers == {"WWW-Authenticate": "Bearer"}
```

- [ ] **Step 2: Run tests and verify imports fail**

Run:

```powershell
python -m pytest tests/test_auth_api.py -v
```

Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement request and response models**

Use `EmailStr`, `ConfigDict(from_attributes=True)`, and field validators. Call `validate_password_policy()` from the registration password validator so backend policy has one source.

```python
class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse
```

- [ ] **Step 4: Implement typed HTTP errors**

```python
def auth_http_error(
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
        headers=headers,
    )


def invalid_credentials() -> HTTPException:
    return auth_http_error(
        401,
        "INVALID_CREDENTIALS",
        "邮箱或密码错误",
        {"WWW-Authenticate": "Bearer"},
    )
```

Implement each named constructor from the Interfaces block with the approved status and error code.

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_auth_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add agent/schema/auth.py agent/api/auth_errors.py agent/tests/test_auth_api.py
git commit -m "feat: define authentication API contracts"
```

---

### Task 6: Implement Registration and Login Service

**Files:**
- Create: `agent/services/auth_service.py`
- Create: `agent/tests/test_auth_service.py`

**Interfaces:**
- Consumes: password and token primitives, `User`, `AuthSession`
- Produces: `AuthResult`
- Produces: `register_user(session, request, user_agent) -> AuthResult`
- Produces: `authenticate_user(session, request, user_agent) -> AuthResult`
- Raises: `EmailAlreadyRegistered`, `InvalidCredentials`

- [ ] **Step 1: Write failing registration and login service tests**

Cover:

```python
async def test_register_creates_user_and_session(db_session):
    result = await register_user(
        db_session,
        RegisterRequest(
            email="Student@Example.com",
            nickname="Student",
            password="learning2026",
        ),
        "pytest",
    )
    assert result.user.email_normalized == "student@example.com"
    assert result.user.password_hash != "learning2026"
    assert result.access_token.expires_in == 900
    assert result.refresh_token


async def test_login_rejects_unknown_email_with_same_error(db_session):
    with pytest.raises(InvalidCredentials):
        await authenticate_user(
            db_session,
            LoginRequest(
                email="missing@example.com",
                password="learning2026",
            ),
            "pytest",
        )
```

Also test duplicate normalized email, wrong password, inactive user, `last_login_at`, and password hash upgrade.

- [ ] **Step 2: Run tests and verify service is missing**

Run:

```powershell
python -m pytest tests/test_auth_service.py -v
```

Expected: FAIL because `auth_service.py` does not exist.

- [ ] **Step 3: Implement service result and domain errors**

```python
@dataclass(frozen=True)
class AuthResult:
    user: User
    access_token: IssuedAccessToken
    refresh_token: str


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class InvalidRefreshToken(Exception):
    pass
```

- [ ] **Step 4: Implement `_create_refresh_session()`**

```python
def _create_refresh_session(
    user_id: uuid.UUID,
    user_agent: str | None,
    family_id: uuid.UUID | None = None,
) -> tuple[str, AuthSession]:
    settings = get_settings()
    raw_token = generate_refresh_token()
    auth_session = AuthSession(
        id=uuid.uuid4(),
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        refresh_token_hash=hash_refresh_token(raw_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.auth_refresh_token_days),
        user_agent=user_agent,
    )
    return raw_token, auth_session
```

- [ ] **Step 5: Implement registration and login**

Follow these transaction rules:

- Query normalized email before insert for a friendly response.
- Still catch the named unique constraint to handle races.
- Use `DUMMY_PASSWORD_HASH` when the email is absent.
- Return the same `InvalidCredentials` for absent, wrong-password, and inactive users.
- Never log request passwords, encoded password hashes, JWTs, or Refresh Tokens.

- [ ] **Step 6: Run service tests**

Run:

```powershell
python -m pytest tests/test_auth_service.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add agent/services/auth_service.py agent/tests/test_auth_service.py
git commit -m "feat: implement registration and login service"
```

---

### Task 7: Implement Refresh Rotation and Session Revocation

**Files:**
- Modify: `agent/services/auth_service.py`
- Modify: `agent/tests/test_auth_service.py`

**Interfaces:**
- Produces: `rotate_refresh_token(session, raw_token, user_agent) -> AuthResult`
- Produces: `revoke_refresh_token(session, raw_token) -> None`
- Produces: `revoke_all_user_sessions(session, user_id) -> None`
- Produces: `revoke_session_family(session, family_id) -> None`

- [ ] **Step 1: Write failing refresh and revocation tests**

Add tests for:

```python
async def test_refresh_rotates_session(db_session, registered_auth):
    old = registered_auth
    result = await rotate_refresh_token(
        db_session,
        old.refresh_token,
        "pytest-refresh",
    )
    assert result.refresh_token != old.refresh_token
    old_record = await db_session.get(
        AuthSession,
        decode_access_token(old.access_token.token).session_id,
    )
    assert old_record.revoked_at is not None
    assert old_record.replaced_by_id is not None


async def test_logout_is_idempotent(db_session, registered_auth):
    await revoke_refresh_token(
        db_session,
        registered_auth.refresh_token,
    )
    await revoke_refresh_token(
        db_session,
        registered_auth.refresh_token,
    )
```

Also cover expiration, inactive users, replay, family revocation, and logout-all user isolation.

- [ ] **Step 2: Run the targeted tests**

Run:

```powershell
python -m pytest tests/test_auth_service.py -k "refresh or revoke or logout" -v
```

Expected: FAIL because the functions are missing.

- [ ] **Step 3: Implement atomic rotation**

Use:

```python
record = await session.scalar(
    select(AuthSession)
    .where(AuthSession.refresh_token_hash == token_hash)
    .with_for_update()
)
```

On normal rotation, create the replacement before assigning `replaced_by_id`, call `await session.flush()`, then revoke the old record.

On replay of a replaced Token:

```python
await revoke_session_family(session, record.family_id)
await session.commit()
raise InvalidRefreshToken
```

The explicit commit is required because the existing request Session dependency rolls back when an exception escapes.

- [ ] **Step 4: Implement idempotent revocation**

`revoke_refresh_token()` returns without error for absent or already revoked Tokens. `revoke_all_user_sessions()` updates only rows belonging to the provided user ID.

- [ ] **Step 5: Run service tests**

Run:

```powershell
python -m pytest tests/test_auth_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add agent/services/auth_service.py agent/tests/test_auth_service.py
git commit -m "feat: rotate and revoke refresh sessions"
```

---

### Task 8: Add CurrentUser and Authentication Routes

**Files:**
- Modify: `agent/api/deps.py`
- Create: `agent/api/auth.py`
- Modify: `agent/api/router.py`
- Modify: `agent/main.py`
- Modify: `agent/tests/conftest.py`
- Modify: `agent/tests/test_auth_api.py`

**Interfaces:**
- Produces: `get_current_user() -> User`
- Produces: `CurrentUser`
- Produces: `/api/auth/register`, `/login`, `/refresh`, `/logout`, `/logout-all`, `/me`

- [ ] **Step 1: Write failing API tests**

Use dependency overrides with the in-memory test database and verify:

```python
async def test_register_sets_refresh_cookie(client):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "student@example.com",
            "nickname": "Student",
            "password": "learning2026",
        },
    )
    assert response.status_code == 201
    cookie = response.headers["set-cookie"]
    assert "eduflow_refresh=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api/auth" in cookie


async def test_me_requires_bearer_token(client):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ACCESS_TOKEN_INVALID"
```

Add tests for login, refresh rotation, invalid refresh Cookie clearing, logout idempotence, logout-all, disabled user, and response omission of password and raw Refresh Token.

Add Origin tests for Cookie-authenticated endpoints:

```python
async def test_refresh_rejects_untrusted_origin(client):
    response = await client.post(
        "/api/auth/refresh",
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
```

- [ ] **Step 2: Run API tests**

Run:

```powershell
python -m pytest tests/test_auth_api.py -v
```

Expected: FAIL because the routes are not registered.

- [ ] **Step 3: Implement `CurrentUser`**

Use `HTTPBearer(auto_error=False)`. Decode the Token, load `User` with `get_readonly_session`, reject missing or inactive users, and return `ACCESS_TOKEN_INVALID` or `ACCOUNT_DISABLED`.

- [ ] **Step 4: Implement Cookie helpers**

```python
def set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=token,
        max_age=settings.auth_refresh_token_days * 86400,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/api/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_refresh_cookie_name,
        path="/api/auth",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )
```

- [ ] **Step 5: Implement routes and domain-error mapping**

Each route calls the service layer. Map domain errors to the exact constructors in `api/auth_errors.py`. Refresh and logout read:

```python
request.cookies.get(settings.auth_refresh_cookie_name)
```

`/me` serializes through `UserResponse.model_validate(current_user)`.

For `/refresh` and `/logout`, reject a present `Origin` header unless it exactly matches an entry in `settings.cors_allowed_origins`. Requests without Origin remain supported for non-browser API clients.

- [ ] **Step 6: Register router and configure CORS**

Add `auth_router` to `api/router.py`. Replace hard-coded `allow_origins` in `main.py` with:

```python
allow_origins=settings.cors_allowed_origins
```

- [ ] **Step 7: Run tests**

Run:

```powershell
python -m pytest tests/test_auth_api.py -v
python -m pytest tests/test_api_integration.py -v
```

Expected: authentication tests pass; existing API tests may now fail with 401 and are adapted in Task 10.

- [ ] **Step 8: Commit**

```powershell
git add agent/api/deps.py agent/api/auth.py agent/api/router.py agent/main.py agent/tests/conftest.py agent/tests/test_auth_api.py
git commit -m "feat: expose authentication API"
```

---

### Task 9: Enforce Project Ownership

**Files:**
- Create: `agent/api/ownership.py`
- Modify: `agent/api/projects.py`
- Modify: `agent/tests/test_resource_isolation.py`

**Interfaces:**
- Produces: `get_owned_project(session, project_id, user_id, for_update=False) -> Project`
- Changes: project create/list/detail/delete to current-user scope

- [ ] **Step 1: Write failing two-user project tests**

Create user A, user B, and A's project. Assert:

```python
async def test_user_cannot_read_foreign_project(
    client_for_user_b,
    project_owned_by_user_a,
):
    response = await client_for_user_b.get(
        f"/api/projects/{project_owned_by_user_a.id}"
    )
    assert response.status_code == 404


async def test_project_list_only_returns_current_user_projects(
    client_for_user_b,
    project_owned_by_user_a,
    project_owned_by_user_b,
):
    response = await client_for_user_b.get("/api/projects")
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {str(project_owned_by_user_b.id)}
```

- [ ] **Step 2: Run tests and verify data leakage**

Run:

```powershell
python -m pytest tests/test_resource_isolation.py -k project -v
```

Expected: FAIL because current routes do not filter owners.

- [ ] **Step 3: Implement ownership helper**

Use one filtered query and return 404 for missing or foreign projects. Apply `with_for_update()` only when requested.

- [ ] **Step 4: Modify project CRUD**

- Inject `CurrentUser`.
- Set `owner_id=current_user.id` on create.
- Add owner filter to both list count and item queries.
- Use `get_owned_project()` for detail and delete.

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_resource_isolation.py -k project -v
python -m pytest tests/test_api_integration.py -k project -v
```

Expected: PASS after existing fixtures send valid Bearer Tokens.

- [ ] **Step 6: Commit**

```powershell
git add agent/api/ownership.py agent/api/projects.py agent/tests/test_resource_isolation.py agent/tests/test_api_integration.py
git commit -m "feat: isolate projects by owner"
```

---

### Task 10: Persist and Isolate Uploaded Materials

**Files:**
- Modify: `agent/api/materials.py`
- Modify: `agent/tests/test_phase2_materials.py`
- Modify: `agent/tests/test_resource_isolation.py`

**Interfaces:**
- Consumes: `CurrentUser`, `SourceMaterial.owner_id`
- Produces: database-backed material upload, parse, and preview

- [ ] **Step 1: Write failing material persistence tests**

Verify upload creates a `SourceMaterial` with `project_id is None`, `owner_id == current_user.id`, and a storage path. Verify user B receives 404 when parsing or previewing user A's material.

- [ ] **Step 2: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_phase2_materials.py tests/test_resource_isolation.py -k material -v
```

Expected: FAIL because upload currently writes only to the filesystem.

- [ ] **Step 3: Persist upload metadata**

After writing the file, add:

```python
material = SourceMaterial(
    id=material_id,
    owner_id=current_user.id,
    project_id=None,
    type=suffix.lstrip("."),
    filename=original_name,
    size_bytes=len(contents),
    storage_path=str(file_path),
)
session.add(material)
await session.flush()
```

If database flush fails, remove the newly written file and directory before re-raising so the database and filesystem remain consistent.

- [ ] **Step 4: Replace UUID path lookup with owned database lookup**

Parse the material UUID, query `SourceMaterial.id + owner_id`, and read only `material.storage_path`. Store `content_text` and `parsed_result` after parsing.

- [ ] **Step 5: Validate project material binding**

In project creation, verify every submitted `material_id` belongs to the current user. Reject mixed or missing IDs with `400 BAD_REQUEST`. Set each accepted material's `project_id` to the new project.

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_phase2_materials.py tests/test_resource_isolation.py -k material -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add agent/api/materials.py agent/api/projects.py agent/tests/test_phase2_materials.py agent/tests/test_resource_isolation.py
git commit -m "feat: persist and isolate source materials"
```

---

### Task 11: Enforce Ownership Across Remaining Business APIs

**Files:**
- Modify: `agent/api/generate.py`
- Modify: `agent/api/frames.py`
- Modify: `agent/api/parameters.py`
- Modify: `agent/api/feedback.py`
- Modify: `agent/api/versions.py`
- Modify: `agent/api/export.py`
- Modify: `agent/api/knowledge.py`
- Modify: `agent/tests/test_resource_isolation.py`
- Modify: `agent/tests/test_api_integration.py`

**Interfaces:**
- Consumes: `CurrentUser`, `get_owned_project()`
- Produces: authenticated and owner-scoped business routes

- [ ] **Step 1: Add failing route-family isolation tests**

For user B and user A's project, assert 404 for:

```text
GET frames
PUT frame
POST frame lock
GET parameters
POST recompute
GET feedback
POST feedback
POST version
GET versions
GET version detail
POST version restore
POST generate
GET generation stream
POST approve
POST reject
POST regenerate
GET regenerate stream
POST export
GET export status
GET export download
```

Assert unauthenticated requests to `/api/knowledge/search` and `/api/knowledge/templates` return 401.

- [ ] **Step 2: Run tests and verify unauthorized access**

Run:

```powershell
python -m pytest tests/test_resource_isolation.py -v
```

Expected: FAIL for unprotected route families.

- [ ] **Step 3: Inject authentication and ownership checks**

At the beginning of every project-scoped route:

```python
project = await get_owned_project(
    session,
    project_id,
    current_user.id,
)
```

Use `for_update=True` for mutating operations.

For export status and download, join:

```python
select(ExportJobModel)
.join(Project, Project.id == ExportJobModel.project_id)
.where(
    ExportJobModel.id == job_id,
    Project.owner_id == current_user.id,
)
```

- [ ] **Step 4: Protect all SSE endpoints**

Authenticate and authorize before returning `EventSourceResponse`. Do not rely on the earlier POST request having been authenticated.

- [ ] **Step 5: Protect knowledge endpoints**

Inject `CurrentUser` even though knowledge records are shared. This prevents anonymous Embedding API usage.

- [ ] **Step 6: Run isolation and existing tests**

Run:

```powershell
python -m pytest tests/test_resource_isolation.py -v
python -m pytest tests/test_api_integration.py -v
python -m pytest tests/test_generate_service.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add agent/api agent/tests/test_resource_isolation.py agent/tests/test_api_integration.py
git commit -m "feat: enforce authentication across business APIs"
```

---

### Task 12: Add Redis Authentication Rate Limits

**Files:**
- Create: `agent/db/redis.py`
- Create: `agent/services/auth_rate_limit.py`
- Modify: `agent/api/auth.py`
- Modify: `agent/config.py`
- Modify: `agent/main.py`
- Modify: `agent/tests/test_auth_api.py`

**Interfaces:**
- Produces: `get_redis() -> redis.asyncio.Redis`
- Produces: `close_redis() -> None`
- Produces: `check_login_limit(redis, client_ip, normalized_email) -> None`
- Produces: `record_login_failure(redis, client_ip, normalized_email) -> None`
- Produces: `clear_login_failures(redis, client_ip, normalized_email) -> None`
- Produces: `check_registration_limit(redis, client_ip) -> None`
- Produces: `check_refresh_limit(redis, session_key) -> None`

- [ ] **Step 1: Write failing fixed-window tests**

Use a fake Redis fixture. Assert the sixth failed login within 15 minutes raises `AuthRateLimited`, a successful login clears the counter, the sixth registration in one hour is blocked, and the 31st refresh in one minute is blocked.

- [ ] **Step 2: Run tests**

Run:

```powershell
python -m pytest tests/test_auth_api.py -k rate_limit -v
```

Expected: FAIL because the limiter does not exist.

- [ ] **Step 3: Implement hashed keys**

Create the shared Redis lifecycle:

```python
# agent/db/redis.py
from redis.asyncio import Redis

from config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            get_settings().redis_url,
            decode_responses=True,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
```

Call `await close_redis()` from the FastAPI lifespan shutdown path.

Then implement opaque Redis keys:

```python
def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def login_key(client_ip: str, email: str) -> str:
    return f"auth:login:{_digest(client_ip)}:{_digest(email)}"
```

Use a Redis transaction or Lua script so `INCR` and first-use `EXPIRE` are atomic.

- [ ] **Step 4: Integrate with auth routes**

- Check before expensive Argon2 work.
- Increment only failed logins.
- Clear on successful login.
- Apply registration and refresh limits before service calls.
- Convert `AuthRateLimited` to `429 AUTH_RATE_LIMITED`.

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_auth_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add agent/db/redis.py agent/services/auth_rate_limit.py agent/api/auth.py agent/config.py agent/main.py agent/tests/test_auth_api.py
git commit -m "feat: rate limit authentication endpoints"
```

---

### Task 13: Add PostgreSQL Concurrency Coverage and CI Gates

**Files:**
- Create: `agent/tests/test_auth_postgres.py`
- Modify: `agent/pytest.ini`
- Modify: `agent/tests/test_generate_service.py`
- Modify: `agent/tests/test_phase3.py`
- Modify: `.github/workflows/backend-ci.yml`

**Interfaces:**
- Consumes: real PostgreSQL row locking through SQLAlchemy `Select.with_for_update()`, authentication service
- Produces: CI evidence that concurrent refresh and unique-email behavior are correct

- [ ] **Step 1: Register the integration marker**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
markers =
    postgres: requires the PostgreSQL CI service
```

- [ ] **Step 2: Write the concurrent-refresh test**

Create one user and one Refresh Token, open two independent AsyncSessions, and run:

```python
results = await asyncio.gather(
    rotate_refresh_token(
        first_session,
        raw_refresh_token,
        "postgres-test-a",
    ),
    rotate_refresh_token(
        second_session,
        raw_refresh_token,
        "postgres-test-b",
    ),
    return_exceptions=True,
)
assert sum(isinstance(item, AuthResult) for item in results) == 1
assert sum(
    isinstance(item, InvalidRefreshToken)
    for item in results
) == 1
```

- [ ] **Step 3: Write the concurrent-registration test**

Start two independent registrations for normalized-equivalent emails. Assert one succeeds and one raises `EmailAlreadyRegistered`. Query the database and assert exactly one User row exists.

- [ ] **Step 4: Run PostgreSQL tests locally**

Run:

```powershell
$env:DATABASE_URL='postgresql+asyncpg://agent:changeme@localhost:5433/eduflow_auth_test'
python -m pytest tests/test_auth_postgres.py -m postgres -v
```

Expected: PASS.

- [ ] **Step 5: Add a PostgreSQL CI service**

Add:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    env:
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: changeme
      POSTGRES_DB: eduflow_test
    ports:
      - 5432:5432
    options: >-
      --health-cmd "pg_isready -U agent -d eduflow_test"
      --health-interval 5s
      --health-timeout 5s
      --health-retries 10
```

Set job environment:

```yaml
env:
  DATABASE_URL: postgresql+asyncpg://agent:changeme@localhost:5432/eduflow_test
  AUTH_JWT_SECRET: ci-only-secret-with-at-least-sixty-four-characters-000000000000
  AUTH_COOKIE_SECURE: "false"
```

- [ ] **Step 6: Make warnings visible and run all backend tests**

CI commands:

```yaml
- name: Upgrade database
  run: python -m alembic upgrade head

- name: Run unit and API tests
  run: python -m pytest tests/ -v --tb=short -m "not postgres"

- name: Run PostgreSQL authentication tests
  run: python -m pytest tests/test_auth_postgres.py -v -m postgres
```

Before enabling warnings as errors, correct the two pre-existing AsyncMock warnings:

```python
# tests/test_generate_service.py
mock_db_session = AsyncMock()
mock_db_session.add = MagicMock()

# tests/test_phase3.py
mock_session = AsyncMock()
mock_session.add = MagicMock()
```

Then enable:

```yaml
PYTHONWARNINGS: error
```

- [ ] **Step 7: Run the complete verification suite**

Run from `agent/`:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest tests -p no:cacheprovider -v
python -m alembic downgrade base
python -m alembic upgrade head
```

Expected: all tests pass, no unexpected warnings, and both migration commands exit 0.

- [ ] **Step 8: Commit**

```powershell
git add agent/tests/test_auth_postgres.py agent/pytest.ini agent/tests/test_generate_service.py agent/tests/test_phase3.py .github/workflows/backend-ci.yml
git commit -m "test: verify authentication on PostgreSQL"
```

---

### Task 14: Final Backend Security Verification

**Files:**
- Modify only if a verification failure identifies a defect

**Interfaces:**
- Consumes: all previous tasks
- Produces: a backend release candidate satisfying the approved authentication specification

- [ ] **Step 1: Verify no sensitive values are logged**

Run:

```powershell
rg -n "password|refresh_token|access_token|password_hash" agent -g "*.py"
```

Review every logger call in the results. No logger arguments may contain raw credentials or encoded hashes.

- [ ] **Step 2: Verify every business route is authenticated**

Run:

```powershell
python -m pytest tests/test_resource_isolation.py -v
```

Expected: all public/private and two-user isolation cases pass.

- [ ] **Step 3: Verify error contract**

Run:

```powershell
python -m pytest tests/test_auth_api.py -k "error or invalid or disabled or conflict" -v
```

Expected: all responses contain an `error` object with `code` and `message`; `details` remains optional for compatibility with existing explicit error bodies.

- [ ] **Step 4: Run the complete backend suite**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest tests -p no:cacheprovider -v
```

Expected: zero failed tests.

- [ ] **Step 5: Inspect the final diff**

Run:

```powershell
git status --short
git diff --check
git diff --stat
```

Expected: no whitespace errors and no unrelated user files staged.

- [ ] **Step 6: Commit final verification-only fixes if needed**

If verification required changes:

```powershell
git add agent .github/workflows/backend-ci.yml .env.example docker-compose.yml
git commit -m "fix: close backend authentication verification gaps"
```

If verification required no changes, do not create an empty commit.

---

## Deferred Frontend Plan

The backend plan intentionally stops at the API contract. Create a separate implementation plan for:

- replacing `simulateAuth()`;
- adding an in-memory `AuthProvider`;
- bootstrapping with `/api/auth/refresh`;
- adding Bearer headers and single-flight refresh to `api-client.ts`;
- adding Bearer headers to every SSE reconnect;
- protecting `/app` routes;
- removing persisted `isAuthenticated` state;
- adding login, registration, refresh, logout, and route-guard tests.

This separation allows the backend authentication and ownership boundary to be reviewed and deployed independently before the frontend starts relying on it.
