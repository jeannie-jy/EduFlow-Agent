"""EduFlow-Agent 配置模块。

所有环境变量统一从这里加载，使用 pydantic-settings 做校验。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_AUTH_JWT_SECRET_PLACEHOLDERS = frozenset(
    {
        "replace-with-at-least-64-random-characters",
        "your-jwt-secret",
        "your-secret-key",
        "change-me",
    }
)


class Settings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(
        # 使用绝对路径：无论从哪个目录启动，都能找到项目根目录的 .env
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 项目 ──────────────────────────────────────────────
    project_root: Path = Path(__file__).resolve().parent.parent
    log_level: str = "INFO"
    log_format: str = "text"  # text | json

    # ── 数据库 ────────────────────────────────────────────
    db_user: str = "agent"
    db_password: str = "changeme"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "eduflow"

    # 允许通过 DATABASE_URL 环境变量直接覆盖（CI 切 SQLite 用）
    database_url_override: str | None = Field(
        default=None,
        alias="DATABASE_URL",
        description="完整数据库 URL。设置后将忽略拆分字段。",
    )

    # ── Authentication ───────────────────────────────────
    auth_jwt_secret: SecretStr = Field(alias="AUTH_JWT_SECRET")
    auth_jwt_algorithm: Literal["HS256"] = "HS256"
    auth_jwt_issuer: str = "eduflow-agent"
    auth_jwt_audience: str = "eduflow-web"
    auth_access_token_seconds: int = Field(default=900, gt=0)
    auth_refresh_token_days: int = Field(default=30, gt=0)
    auth_refresh_cookie_name: str = "eduflow_refresh"
    auth_cookie_secure: bool = True
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    auth_trusted_proxy_ips: list[str] = []
    cors_allowed_origins: list[str] = ["http://localhost:5173"]

    @field_validator("auth_jwt_secret")
    @classmethod
    def validate_auth_jwt_secret(cls, value: SecretStr) -> SecretStr:
        """Reject weak or documentation-only JWT secrets."""
        secret = value.get_secret_value()
        if not secret.strip():
            raise ValueError("AUTH_JWT_SECRET must not be blank")
        if secret.casefold() in _AUTH_JWT_SECRET_PLACEHOLDERS:
            raise ValueError("AUTH_JWT_SECRET must not use a placeholder value")
        if len(secret) < 64:
            raise ValueError("AUTH_JWT_SECRET must be at least 64 characters")
        return value

    @model_validator(mode="after")
    def validate_auth_cookie_security(self) -> Settings:
        """Keep the SameSite=None cookie setting safe for modern browsers."""
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            raise ValueError(
                "AUTH_COOKIE_SAMESITE='none' requires AUTH_COOKIE_SECURE=true"
            )
        if "*" in self.cors_allowed_origins:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must not contain '*' when credentials are enabled"
            )
        return self

    @property
    def database_url(self) -> str:
        """数据库连接 URL。环境变量 DATABASE_URL 优先，否则从拆分字段拼接。

        自动将 postgresql:// 转换为 postgresql+asyncpg://（SQLAlchemy async 引擎要求）。
        """
        url = self.database_url_override
        if url:
            # 自动修正 scheme：确保 async 引擎可用
            if url.startswith("postgresql://") and "+" not in url.split("://")[0]:
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ── Redis ─────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── LLM ───────────────────────────────────────────────
    llm_endpoint: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_api_key: str = "your-deepseek-api-key"

    # ── Embedding ─────────────────────────────────────────
    embedding_endpoint: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str = "your-openai-api-key"
    embedding_dimension: int = 1536

    # ── 知识库 ────────────────────────────────────────────
    knowledge_search_top_k: int = 5
    knowledge_similarity_threshold: float = 0.7

    # ── Agent ─────────────────────────────────────────────
    agent_log_level: str = "INFO"
    agent_max_retries: int = 3
    agent_timeout_ms: int = 120_000
    quality_score_threshold: float = 0.6  # 低于此分数触发 Reflection
    max_reflection_cycles: int = 3

    # ── 文件存储 ──────────────────────────────────────────
    upload_dir: Path = Path("data/uploads")
    upload_max_size_bytes: int = 52_428_800  # 50 MB
    allowed_upload_types: list[str] = [
        "application/pdf",
        "text/plain",
        "text/markdown",
        "text/x-python",
        "text/x-csrc",
        "text/x-java-source",
        "text/x-c++src",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ]

    # ── 导出 ──────────────────────────────────────────────
    export_dir: Path = Path("data/exports")
    manim_timeout_seconds: int = 600


@lru_cache
def get_settings() -> Settings:
    """获取配置单例。"""
    return Settings()
