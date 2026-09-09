"""EduFlow-Agent 配置模块。

所有环境变量统一从这里加载，使用 pydantic-settings 做校验。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(
        # 使用绝对路径：无论从哪个目录启动，都能找到项目根目录的 .env
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # ── 项目 ──────────────────────────────────────────────
    project_root: Path = Path(__file__).resolve().parent.parent
    app_version: str = "0.9.0"  # 版本号唯一来源（/api/health 与 FastAPI version 同源）
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
    llm_model: str = "deepseek-v4-flash"
    llm_api_key: str = "your-deepseek-api-key"
    llm_backup_endpoint: str = ""
    llm_backup_model: str = ""
    llm_backup_api_key: str = ""
    llm_planner_model: str = ""
    llm_knowledge_model: str = ""
    llm_coder_model: str = ""
    llm_quality_model: str = ""
    llm_reflection_model: str = ""
    llm_module_model: str = ""
    llm_manim_model: str = ""
    llm_timeout_seconds: float = Field(default=120.0, ge=1, le=600)
    llm_gateway_max_retries: int = Field(default=2, ge=0, le=8)
    llm_gateway_retry_base_seconds: float = Field(default=0.5, ge=0, le=30)
    llm_gateway_max_concurrency: int = Field(default=8, ge=1, le=128)
    llm_circuit_failure_threshold: int = Field(default=5, ge=1, le=100)
    llm_circuit_reset_seconds: float = Field(default=30.0, ge=1, le=3600)
    llm_input_cost_per_million: float = Field(default=0.0, ge=0)
    llm_output_cost_per_million: float = Field(default=0.0, ge=0)
    llm_request_max_tokens: int = Field(default=200_000, ge=1, le=10_000_000)
    llm_request_max_cost_usd: float = Field(default=10.0, ge=0.01, le=10_000)

    # ── Embedding ─────────────────────────────────────────
    embedding_endpoint: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str = "your-openai-api-key"
    embedding_dimension: int = 1536

    # ── 知识库 ────────────────────────────────────────────
    knowledge_search_top_k: int = 5
    knowledge_similarity_threshold: float = 0.7
    retrieval_query_count: int = Field(default=3, ge=1, le=5)
    retrieval_context_max_chars: int = Field(default=6000, ge=500, le=30000)

    # ── Agent ─────────────────────────────────────────────
    agent_log_level: str = "INFO"
    agent_max_retries: int = 3
    agent_timeout_ms: int = 120_000
    quality_score_threshold: float = 0.6  # 低于此分数触发 Reflection
    max_reflection_cycles: int = 3
    max_replan_cycles: int = Field(default=3, ge=1, le=10)
    module_generation_concurrency: int = Field(default=3, ge=1, le=16)
    tool_calling_enabled: bool = True
    tool_max_rounds: int = Field(default=3, ge=1, le=8)
    tool_max_calls: int = Field(default=8, ge=1, le=32)
    tool_max_concurrency: int = Field(default=3, ge=1, le=16)
    tool_timeout_seconds: float = Field(default=10.0, ge=0.1, le=120)
    tool_result_max_chars: int = Field(default=12000, ge=500, le=100000)
    sse_stream_lease_seconds: int = Field(default=90, ge=15, le=600)
    sse_stream_poll_seconds: float = Field(default=0.5, ge=0.1, le=10)
    sse_event_retention_hours: int = Field(default=24, ge=1, le=168)

    # ── 文件存储 ──────────────────────────────────────────
    upload_dir: Path = Path("data/uploads")
    upload_max_size_bytes: int = 52_428_800  # 50 MB
    material_retention_days: int = Field(default=30, ge=1, le=3650)
    material_cleanup_interval_seconds: int = Field(default=21600, ge=60, le=604800)
    material_parse_execution_mode: Literal["inline", "sandbox"] = "inline"
    material_sandbox_dir: Path = Path("data/material-sandbox")
    material_parse_timeout_seconds: int = Field(default=120, ge=5, le=1800)
    material_parse_result_max_bytes: int = Field(
        default=2 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024
    )
    allowed_upload_types: list[str] = [
        "application/pdf",
        "text/plain",
        "text/markdown",
        "text/x-python",
        "text/x-csrc",
        "text/x-java-source",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ]
    artifact_store_backend: Literal["local", "minio"] = "local"
    artifact_store_dir: Path = Path("data/artifacts")
    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str = "localhost:9000"
    # Compose historically names these MINIO_USER / MINIO_PASSWORD while the
    # application-facing names are MINIO_ACCESS_KEY / MINIO_SECRET_KEY. Accept
    # both so a host-run API and container workers share one .env file.
    minio_access_key: str = Field(
        default="",
        validation_alias=AliasChoices("MINIO_ACCESS_KEY", "MINIO_USER"),
    )
    minio_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("MINIO_SECRET_KEY", "MINIO_PASSWORD"),
    )
    minio_bucket: str = "eduflow-artifacts"
    minio_secure: bool = False

    # ── 导出 ──────────────────────────────────────────────
    # 默认放到用户目录下，避免放在项目内触发 uvicorn --reload 重启
    export_dir: Path = Path.home() / ".eduflow" / "exports"
    manim_timeout_seconds: int = 600
    # Host/API remains disabled by default; video startup explicitly selects queue.
    manim_execution_mode: Literal["disabled", "queue", "worker"] = "disabled"
    # Deterministic compilation is the reliable/fast default. The optional LLM
    # director always falls back to the same compiler before a job can fail.
    manim_script_mode: Literal["deterministic", "llm"] = "deterministic"
    export_worker_poll_seconds: float = Field(default=2.0, ge=0.2, le=60)
    export_worker_heartbeat_seconds: float = Field(default=30.0, ge=1, le=300)
    export_worker_max_attempts: int = Field(default=3, ge=1, le=10)
    export_retry_base_seconds: float = Field(default=5.0, ge=0.1, le=3600)
    export_retry_max_seconds: float = Field(default=300.0, ge=0.1, le=86400)
    export_max_artifact_bytes: int = Field(default=500 * 1024 * 1024, ge=1)
    export_max_workspace_bytes: int = Field(default=1024 * 1024 * 1024, ge=1)
    export_max_workspace_files: int = Field(default=5000, ge=1, le=100000)
    ffmpeg_path: str = ""  # FFmpeg 目录路径，留空则自动从 PATH 查找

    # ── 通用后台任务 ──────────────────────────────────────
    task_worker_poll_seconds: float = Field(default=2.0, ge=0.2, le=60)
    task_worker_heartbeat_seconds: float = Field(default=30.0, ge=1, le=300)
    task_worker_lease_seconds: int = Field(default=300, ge=30, le=3600)
    task_worker_max_attempts: int = Field(default=3, ge=1, le=10)
    task_retry_base_seconds: float = Field(default=5.0, ge=0.1, le=3600)
    task_retry_max_seconds: float = Field(default=300.0, ge=0.1, le=86400)

    # ── 认证 ──────────────────────────────────────────────
    # 本地/既有测试默认兼容匿名模式；Compose 生产入口显式开启。
    auth_required: bool = False
    auth_cookie_secure: bool = False
    auth_session_days: int = Field(default=14, ge=1, le=90)
    auth_login_attempts: int = Field(default=10, ge=1, le=1000)
    auth_login_window_seconds: int = Field(default=300, ge=1, le=86400)
    auth_register_attempts: int = Field(default=5, ge=1, le=1000)
    auth_register_window_seconds: int = Field(default=3600, ge=1, le=86400)
    api_write_rate_limit: int = Field(default=120, ge=1, le=10000)
    api_write_rate_window_seconds: int = Field(default=60, ge=1, le=86400)
    api_generation_rate_limit: int = Field(default=20, ge=1, le=1000)
    api_generation_rate_window_seconds: int = Field(default=300, ge=1, le=86400)
    audit_retention_days: int = Field(default=90, ge=7, le=3650)
    audit_archive_max_events: int = Field(default=10000, ge=1, le=100000)
    audit_archive_hmac_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """获取配置单例。"""
    return Settings()
