"""EduFlow-Agent 配置模块。

所有环境变量统一从这里加载，使用 pydantic-settings 做校验。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 项目 ──────────────────────────────────────────────
    project_root: Path = Path(__file__).resolve().parent.parent
    log_level: str = "INFO"

    # ── 数据库 ────────────────────────────────────────────
    db_user: str = "agent"
    db_password: str = "changeme"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "eduflow"

    @property
    def database_url(self) -> str:
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
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ]

    # ── 导出 ──────────────────────────────────────────────
    export_dir: Path = Path("data/exports")
    manim_timeout_seconds: int = 600


@lru_cache
def get_settings() -> Settings:
    """获取配置单例。"""
    return Settings()
