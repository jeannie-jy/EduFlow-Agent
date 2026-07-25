# EduFlow-Agent MVP 邮箱密码认证设计

## 1. 背景与目标

EduFlow-Agent 当前前端包含登录和注册页面，但认证流程仍由 `simulateAuth()` 模拟，认证状态写入 `localStorage`；后端没有用户、登录、注册、令牌和资源所有权校验。

本设计为当前 FastAPI、SQLAlchemy、PostgreSQL 和 React 架构补充一套 MVP 邮箱密码认证系统，目标如下：

- 支持邮箱密码注册、登录、刷新、登出、全部登出和查询当前用户。
- 使用短期 Access JWT 与可撤销、可轮换的 Refresh Token。
- 防止密码、Refresh Token 和其他敏感认证信息以明文形式持久化。
- 将项目、素材、帧、参数、版本、反馈、生成和导出资源隔离到当前用户。
- 保持现有统一错误响应、异步数据库 Session 和模块化路由风格。
- 为未来接入学校 OAuth2/OIDC 身份认证保留扩展空间，但不在 MVP 中实现 SSO。

## 2. 范围

### 2.1 包含

- 邮箱密码注册和登录。
- Argon2id 密码哈希。
- 15 分钟 Access JWT。
- 30 天 Refresh Token。
- Refresh Token 哈希存储、原子轮换和重放检测。
- 当前设备登出和全部设备登出。
- 当前用户查询。
- 用户与项目、素材的所有权关系。
- 所有业务 API 和 SSE 的身份与资源所有权校验。
- Redis 认证限流。
- 前端认证状态、自动刷新、路由保护和 SSE 鉴权的联调契约。
- SQLite 单元测试与 PostgreSQL 并发集成测试。

### 2.2 不包含

- 邮箱验证。
- 忘记密码和邮件重置密码。
- 修改邮箱、修改密码和用户资料页面。
- 管理员、教师、学生角色和 RBAC。
- 学校统一身份认证、OAuth2/OIDC 和外部身份绑定。
- 企业组织和租户体系。
- 面向第三方客户端的标准 OAuth2 授权服务器。

## 3. 总体架构

采用短期 Access JWT 与服务端 Refresh Session 的混合模型：

1. 注册或登录成功后，服务端返回 Access Token，并将 Refresh Token 写入 HttpOnly Cookie。
2. 前端仅在内存中保存 Access Token，不写入 `localStorage`。
3. 普通业务请求通过 `Authorization: Bearer <access_token>` 认证。
4. 页面重新加载或 Access Token 过期后，前端调用 `/api/auth/refresh`。
5. 服务端验证 Refresh Session，撤销旧 Token，创建新 Token，并返回新的 Access Token。
6. 登出时撤销当前 Refresh Session；全部登出时撤销用户所有 Refresh Session。
7. Access Token 默认不逐请求检查 Session 撤销状态，因此登出后旧 Access Token 最多继续有效 15 分钟。

这种方案兼顾了普通 API 请求性能、浏览器令牌安全、主动会话撤销和未来认证扩展能力。

## 4. 安全依赖与配置

### 4.1 Python 依赖

在 `agent/requirements.txt` 增加：

```text
PyJWT>=2.10,<3
pwdlib[argon2]>=0.3,<1
email-validator>=2.2,<3
```

使用 `pwdlib.PasswordHash.recommended()` 生成和验证 Argon2id 密码哈希。使用 PyJWT 生成和验证 Access Token。

### 4.2 配置项

在 `agent/config.py` 增加：

```python
auth_jwt_secret: SecretStr
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

约束：

- `AUTH_JWT_SECRET` 必须由部署环境提供，不设置生产可用默认值。
- JWT 解码算法从服务端配置固定，不能根据令牌头部动态选择。
- 本地开发可将 `AUTH_COOKIE_SECURE=false`，生产环境必须为 `true`。
- 开启 Credential Cookie 时，CORS 来源必须明确列举，不能使用通配符。

## 5. 数据模型

### 5.1 User

新增 `users` 表：

| 字段 | 类型 | 约束 |
|---|---|---|
| `id` | UUID | 主键 |
| `email` | VARCHAR(320) | 非空，保留展示形式 |
| `email_normalized` | VARCHAR(320) | 非空，唯一 |
| `nickname` | VARCHAR(100) | 非空 |
| `password_hash` | VARCHAR(255) | 非空 |
| `is_active` | BOOLEAN | 非空，默认 true |
| `last_login_at` | TIMESTAMPTZ | 可空 |
| `password_changed_at` | TIMESTAMPTZ | 可空 |
| `created_at` | TIMESTAMPTZ | 非空 |
| `updated_at` | TIMESTAMPTZ | 非空 |

邮箱规范化统一使用 `email.strip().casefold()`。注册、登录和未来修改邮箱必须复用同一个函数。

密码哈希使用 Argon2id 的完整编码结果，不单独保存盐。

### 5.2 AuthSession

新增 `auth_sessions` 表：

| 字段 | 类型 | 约束 |
|---|---|---|
| `id` | UUID | 主键，同时作为 Access Token 的 `sid` |
| `user_id` | UUID | 外键 `users.id`，级联删除 |
| `family_id` | UUID | 非空，用于重放检测 |
| `refresh_token_hash` | VARCHAR(64) | 非空，唯一 |
| `expires_at` | TIMESTAMPTZ | 非空 |
| `last_used_at` | TIMESTAMPTZ | 可空 |
| `revoked_at` | TIMESTAMPTZ | 可空 |
| `replaced_by_id` | UUID | 可空，自引用外键 |
| `user_agent` | VARCHAR(500) | 可空 |
| `created_at` | TIMESTAMPTZ | 非空 |

索引：

- `(user_id, revoked_at)`
- `family_id`
- `refresh_token_hash` 唯一索引

Refresh Token 使用 `secrets.token_urlsafe(48)` 生成，数据库仅保存 SHA-256 哈希。

### 5.3 资源所有权

`projects.owner_id` 从普通字符串迁移为可空 UUID 外键 `users.id`。第一阶段保持可空以兼容旧数据，新项目必须写入所有者。

`source_materials` 增加 `owner_id`。素材上传发生在项目创建前，因此素材必须独立归属于用户。第一阶段迁移同样保持该字段可空以兼容旧数据，但所有新的上传记录必须写入所有者。

对旧的无所有者项目和素材：

- 默认不向普通用户展示。
- 不自动分配给第一个注册用户。
- 由明确的一次性维护操作分配或清理。
- 全部迁移后再将所有者字段调整为 `NOT NULL`。

## 6. Alembic 迁移策略

当前 Alembic 没有版本脚本，且同步迁移环境读取 `postgresql+asyncpg://` 异步 URL。认证开发前先完成：

1. 将 Alembic 环境改为 `async_engine_from_config`。
2. 建立与当前数据库结构一致的基线迁移。
3. 已部署数据库执行 `alembic stamp <baseline_revision>`。
4. 创建独立认证迁移，增加用户、会话和所有权字段。
5. 新环境统一执行 `alembic upgrade head`。
6. `db/init.sql` 最终仅负责 PostgreSQL 扩展初始化，避免与 ORM 和 Alembic 重复维护表结构。

## 7. API 契约

### 7.1 注册

`POST /api/auth/register`

请求：

```json
{
  "email": "student@example.com",
  "nickname": "小明",
  "password": "learning2026"
}
```

成功返回 `201`、AuthResponse，并设置 Refresh Cookie。

邮箱冲突返回 `409 EMAIL_ALREADY_REGISTERED`。数据库唯一约束是并发注册的最终防线。

### 7.2 登录

`POST /api/auth/login`

请求：

```json
{
  "email": "student@example.com",
  "password": "learning2026"
}
```

成功返回 `200`、AuthResponse，并设置 Refresh Cookie。

邮箱不存在、密码错误和账号不可用统一返回 `401 INVALID_CREDENTIALS`，防止通过错误信息枚举账号。不存在邮箱时仍验证固定虚拟密码哈希，降低时序差异。

### 7.3 刷新

`POST /api/auth/refresh`

- 请求体为空。
- 从 HttpOnly Cookie 读取 Refresh Token。
- 对匹配的 AuthSession 执行 `SELECT ... FOR UPDATE`。
- 成功后撤销旧 Session，创建同一 `family_id` 下的新 Session。
- 返回新的 AuthResponse 和 Refresh Cookie。
- 无效、过期、已撤销或重放统一返回 `401 REFRESH_TOKEN_INVALID` 并清除 Cookie。

### 7.4 登出

`POST /api/auth/logout`

- 撤销当前 Refresh Session。
- 清除 Cookie。
- 返回 `204`。
- 缺少 Cookie 或 Session 已撤销时仍返回 `204`。

### 7.5 全部登出

`POST /api/auth/logout-all`

- 要求有效 Access Token。
- 撤销当前用户全部未撤销 Session。
- 清除当前 Cookie。
- 返回 `204`。

### 7.6 当前用户

`GET /api/auth/me`

- 要求有效 Access Token。
- 返回 UserResponse。

### 7.7 AuthResponse

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "student@example.com",
    "nickname": "小明",
    "is_active": true,
    "created_at": "2026-07-24T10:00:00Z"
  }
}
```

## 8. 密码与令牌规则

### 8.1 密码

- 8 至 128 个字符。
- 至少一个字母和一个数字，与现有前端规则一致。
- UTF-8 编码后不超过 256 字节。
- 服务端独立执行验证，不能信任前端校验。
- 登录使用 `verify_and_update()`，在 Argon2 参数变化时透明升级密码哈希。

### 8.2 Access JWT

Claims：

```json
{
  "sub": "<user_uuid>",
  "sid": "<auth_session_uuid>",
  "type": "access",
  "jti": "<token_uuid>",
  "iss": "eduflow-agent",
  "aud": "eduflow-web",
  "iat": 0,
  "nbf": 0,
  "exp": 0
}
```

解码必须校验签名、固定算法、issuer、audience、过期时间和必需 Claims，并显式验证 `type == "access"`。

### 8.3 Refresh Cookie

```python
response.set_cookie(
    key=settings.auth_refresh_cookie_name,
    value=refresh_token,
    max_age=settings.auth_refresh_token_days * 86400,
    httponly=True,
    secure=settings.auth_cookie_secure,
    samesite=settings.auth_cookie_samesite,
    path="/api/auth",
)
```

依赖 Cookie 的刷新和登出端点还需要校验 Origin 是否在允许列表中。

## 9. 模块职责

### 9.1 `security/passwords.py`

- 密码策略校验。
- Argon2id 哈希。
- 密码验证与哈希升级。
- 固定虚拟密码哈希。

### 9.2 `security/tokens.py`

- 创建 Access JWT。
- 解码并验证 Access JWT。
- 生成 Refresh Token。
- 计算 Refresh Token 哈希。
- 将 PyJWT 异常转换为内部 `AccessTokenError`。
- 不访问数据库。

### 9.3 `services/auth_service.py`

- 注册用户。
- 验证登录。
- 创建 Refresh Session。
- 原子轮换 Refresh Token。
- 检测旧 Refresh Token 重放并撤销整个 Session Family。
- 撤销当前会话和全部会话。
- 返回领域结果，不直接设置 Cookie 或构造 HTTP 响应。

### 9.4 `api/auth.py`

- 接收请求体、Cookie、Origin 和 User-Agent。
- 调用认证服务。
- 设置或清除 Cookie。
- 将认证领域异常转换成统一 HTTP 错误。

### 9.5 `api/deps.py`

- 使用 `HTTPBearer(auto_error=False)` 提取 Access Token。
- 解码 Token 并加载当前用户。
- 拒绝无效 Token、缺失用户和停用用户。
- 导出 `CurrentUser` 类型别名。

由于登录端点使用 JSON 而非 OAuth2 表单，不使用会让 OpenAPI 误报登录请求格式的 `OAuth2PasswordBearer`。

## 10. 错误语义

继续使用现有统一响应：

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "邮箱或密码错误"
  }
}
```

错误集合：

| HTTP | code | 场景 |
|---:|---|---|
| 400 | `PASSWORD_POLICY_VIOLATION` | 密码不符合规则 |
| 401 | `INVALID_CREDENTIALS` | 登录失败 |
| 401 | `ACCESS_TOKEN_INVALID` | Access Token 无效或过期 |
| 401 | `REFRESH_TOKEN_INVALID` | Refresh Token 无效、过期或重放 |
| 403 | `ACCOUNT_DISABLED` | 已认证用户被停用 |
| 409 | `EMAIL_ALREADY_REGISTERED` | 注册邮箱冲突 |
| 429 | `AUTH_RATE_LIMITED` | 认证请求超出限制 |

401 响应设置 `WWW-Authenticate: Bearer`。

## 11. Refresh Token 轮换与重放处理

轮换在单一事务中完成：

1. 对 Token 哈希匹配的 Session 加行锁。
2. 不存在、过期或用户停用时拒绝。
3. 如果旧 Session 已撤销且存在 `replaced_by_id`，判定为重放。
4. 重放时撤销同一 `family_id` 下所有 Session。
5. 创建新 Session，继承 `family_id`。
6. 撤销旧 Session，并设置 `replaced_by_id`。
7. 返回新 Access Token 和新的原始 Refresh Token。

该事务必须用 PostgreSQL 集成测试验证；SQLite 不提供等价的行锁语义。

重放检测存在一个额外的事务要求：撤销 Session Family 后不能直接抛出异常并交给当前 `get_session` 依赖处理，因为该依赖会在异常路径回滚事务，导致安全撤销失效。实现应在认证服务中完成 Family 撤销并显式提交该安全事务，再向路由返回失败结果或抛出 `InvalidRefreshToken`。除这个必须持久化的安全失败分支外，普通认证流程继续由现有 Session 依赖统一提交或回滚。

## 12. 资源所有权

除健康检查、Ping 和认证入口外，所有业务 API 均要求登录。

项目访问使用单条所有权过滤查询：

```python
select(Project).where(
    Project.id == project_id,
    Project.owner_id == current_user.id,
)
```

不存在和不属于当前用户统一返回 404，避免暴露其他用户资源是否存在。

需要接入的模块：

- `projects.py`
- `generate.py`，包括审批、拒绝、重生成和全部 SSE
- `frames.py`
- `parameters.py`
- `materials.py`
- `feedback.py`
- `versions.py`
- `export.py`，包括导出状态和文件下载
- `knowledge.py`

HTTP 路由负责鉴权和所有权验证。后台内部服务可以继续以项目 ID 工作，但只能由已鉴权路由或内部队列触发。

## 13. 素材持久化

当前素材上传仅写文件系统，未创建 SourceMaterial 数据库记录。认证接入时必须同时修正：

1. 上传时创建带 `owner_id` 的 SourceMaterial。
2. 解析和预览时先按 `material_id + owner_id` 查询记录。
3. 文件路径只从数据库记录读取，不能根据未鉴权 UUID 直接拼接。
4. 创建项目时验证全部 `material_ids` 属于当前用户。
5. 创建成功后可将素材关联到新项目。

## 14. 前端联调契约

### 14.1 AuthProvider

前端认证状态只保存在内存：

```typescript
type AuthState = {
  status: "loading" | "authenticated" | "anonymous";
  accessToken: string | null;
  user: AuthUser | null;
};
```

页面初始化调用 `/auth/refresh`。成功后恢复 Access Token 和用户；401 则进入匿名状态。

现有 `simulateAuth()` 和基于 `localStorage` 的认证判断必须移除。`/app` 路由需要认证守卫。

### 14.2 API Client

- 普通请求加入 `Authorization: Bearer <access_token>`。
- 请求使用 `credentials: "include"`，使跨端口开发环境可以接收和发送 Refresh Cookie。
- 401 时使用共享 Refresh Promise，避免并发请求同时刷新。
- 刷新成功后原请求只重试一次。
- 登录、注册和刷新请求自身不能触发递归刷新。

### 14.3 SSE

SSE 使用 fetch 流，加入 Bearer Token。每次自动重连时重新获取当前 Access Token，不能永久捕获连接创建时的旧值。

后端 SSE 端点必须独立完成身份和项目所有权验证。

## 15. 限流

使用现有 Redis 实施固定窗口限流：

| 操作 | 限制 |
|---|---:|
| 登录失败 | 同一 IP 与邮箱每 15 分钟 5 次 |
| 注册 | 同一 IP 每小时 5 次 |
| Refresh | 同一 Session 每分钟 30 次 |

Redis Key 不保存明文邮箱，使用规范化邮箱的 SHA-256 截断值。只有在明确配置可信代理后才读取 `X-Forwarded-For`。

## 16. 测试策略

### 16.1 单元测试

- 密码规则边界。
- Argon2 盐值和验证。
- 哈希参数透明升级。
- JWT 正确、过期、错误签名、错误 issuer/audience、错误算法和缺失 Claims。
- Refresh Token 不能作为 Access Token。

### 16.2 服务测试

- 注册成功和大小写邮箱冲突。
- 并发重复注册。
- 不存在邮箱、错误密码和停用用户的统一错误。
- 登录时间和密码哈希升级。
- Refresh 正常轮换。
- 并发 Refresh 只有一个成功。
- 旧 Token 重放撤销 Session Family。
- 过期和已撤销 Session。
- Logout 幂等和 Logout All 隔离。

### 16.3 API 测试

- 注册、登录、刷新、登出和 `/me`。
- 统一错误格式。
- Refresh Cookie 的 HttpOnly、SameSite、Path 和生产 Secure 属性。
- Refresh 失败清除 Cookie。
- 响应不包含密码哈希或 Refresh Token。
- Origin 和限流行为。

### 16.4 双用户资源隔离

用户 B 不能读取、修改、删除、生成、订阅、解析或下载用户 A 的任何项目、素材、帧、参数、版本、反馈和导出资源。所有场景统一返回 404。

### 16.5 PostgreSQL 集成测试

使用临时 PostgreSQL 服务验证：

- `SELECT ... FOR UPDATE` 的并发刷新行为。
- 唯一邮箱约束。
- UUID 外键和级联规则。
- Session Family 重放撤销事务。

## 17. 实施顺序

1. 修复 Alembic 异步环境并创建基线。
2. 增加用户、会话和所有权迁移。
3. 编写密码、令牌和认证服务的失败测试。
4. 实现 `security/passwords.py` 和 `security/tokens.py`。
5. 实现认证服务和 API。
6. 实现 `get_current_user`。
7. 给现有业务路由加入认证和所有权校验。
8. 修复素材数据库持久化。
9. 改造前端 AuthProvider、API Client、路由守卫和 SSE。
10. 增加双用户隔离与 PostgreSQL 并发测试。
11. 接入 Redis 限流。
12. 验证生产 Cookie、CORS 和 Secret 配置。

## 18. 验收标准

- 新用户可以注册、登录、刷新会话和登出。
- 密码和原始 Refresh Token不会写入数据库或日志。
- Access Token 不写入浏览器持久存储。
- Refresh Token 每次使用后失效，重放会撤销整个 Session Family。
- 所有业务 API 和 SSE 均要求认证。
- 任意用户无法读取或修改其他用户资源。
- 认证错误保持当前统一错误格式。
- SQLite 单元测试和 PostgreSQL 并发集成测试均通过。
- 前端刷新页面后可以通过 Refresh Cookie 恢复登录态。
- 生产环境使用 HTTPS Secure Cookie、明确 CORS 来源和高熵 JWT Secret。
