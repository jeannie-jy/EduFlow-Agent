"""Pytest 全局配置与共享 fixtures。

提供：
- Mock LLM 客户端（可控返回）
- Mock Embedding 客户端
- 测试数据工厂（DSL、AgentState）
- SQLite 内存数据库
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


os.environ.setdefault(
    "AUTH_JWT_SECRET",
    "pytest-only-secret-with-at-least-sixty-four-characters-000000000000",
)


# ============================================================================
# Mock LLM 客户端
# ============================================================================


class MockLLMResponse:
    """可配置的 Mock LLM 响应构建器。"""

    def __init__(self, tool_content: dict[str, Any] | None = None, *, text_content: str | None = None):
        self._tool_content = tool_content
        self._text_content = text_content

    def build(self) -> MagicMock:
        """构建一个完整的 mock chat.completions.create 返回值。"""
        import json

        response = MagicMock()
        choice = MagicMock()
        message = MagicMock()

        if self._tool_content is not None:
            tool_call = MagicMock()
            tool_call.id = "call_mock_001"
            tool_call.function.name = "output_structured_result"
            tool_call.function.arguments = json.dumps(self._tool_content, ensure_ascii=False)
            message.tool_calls = [tool_call]
            message.content = None
        elif self._text_content is not None:
            message.tool_calls = []
            message.content = self._text_content
        else:
            message.tool_calls = []
            message.content = "{}"

        choice.message = message
        response.choices = [choice]
        response.usage = MagicMock()
        response.usage.prompt_tokens = 500
        response.usage.completion_tokens = 200
        response.usage.total_tokens = 700
        return response


def create_mock_llm_response(tool_content: dict[str, Any] | None = None) -> MagicMock:
    """快捷创建带 tool_calls 的 mock LLM 响应。"""
    return MockLLMResponse(tool_content=tool_content).build()


def create_mock_embedding_response(dim: int = 1536) -> MagicMock:
    """创建 mock embedding 响应。"""
    import random
    response = MagicMock()
    embedding_data = MagicMock()
    embedding_data.embedding = [random.uniform(-1, 1) for _ in range(dim)]
    response.data = [embedding_data]
    return response


# ============================================================================
# Test Data Factories
# ============================================================================


class AgentStateFactory:
    """AgentState 测试数据工厂。"""

    @staticmethod
    def minimal(project_id: str | None = None) -> dict[str, Any]:
        return {
            "user_input": "讲解冒泡排序",
            "project_id": project_id or str(uuid.uuid4()),
            "materials": [],
            "constraints": {},
            "status": "draft",
            "reflection_count": 0,
            "revision_history": [],
        }

    @staticmethod
    def with_plan() -> dict[str, Any]:
        state = AgentStateFactory.minimal()
        state["teaching_plan"] = {
            "target_audience_level": "undergraduate_cs",
            "prerequisites": ["数组", "循环"],
            "objectives": ["理解冒泡排序原理", "掌握时间复杂度分析"],
            "outline": [
                {
                    "step": 1,
                    "title": "算法介绍",
                    "key_points": ["什么是冒泡排序", "名称由来"],
                    "estimated_frames": 3,
                },
                {
                    "step": 2,
                    "title": "逐步演示",
                    "key_points": ["第一轮遍历", "交换过程", "冒泡到末尾"],
                    "estimated_frames": 5,
                },
            ],
            "teaching_approach": "直觉先行 → 逐步演示 → 伪代码",
            "difficulty_curve": "beginner_friendly",
            "estimated_total_frames": 8,
            "risk_notes": [],
            "suggested_parameters": [],
        }
        state["status"] = "planning"
        return state

    @staticmethod
    def with_knowledge() -> dict[str, Any]:
        state = AgentStateFactory.with_plan()
        state["knowledge_graph"] = {
            "concepts": [
                {"id": "c1", "name": "冒泡排序", "type": "definition"},
                {"id": "c2", "name": "比较交换", "type": "core_mechanism"},
            ],
            "edges": [
                {"source": "c1", "target": "c2", "relation": "leads_to"},
            ],
        }
        state["key_terms"] = ["冒泡排序", "比较交换", "时间复杂度"]
        return state

    @staticmethod
    def with_dsl() -> dict[str, Any]:
        state = AgentStateFactory.with_knowledge()
        state["dsl"] = DSLFactory.bubble_sort_minimal()
        state["status"] = "generating"
        return state

    @staticmethod
    def with_quality_report() -> dict[str, Any]:
        state = AgentStateFactory.with_dsl()
        state["quality_report"] = {
            "scores": {
                "correctness": 0.9,
                "clarity": 0.85,
                "coherence": 0.8,
                "interactivity": 0.7,
                "renderability": 0.95,
                "completeness": 0.85,
            },
            "overall_score": 0.84,
            "issues": [],
            "suggestions": [],
            "is_blocking": False,
        }
        state["status"] = "reviewing"
        return state


class DSLFactory:
    """DSL 测试数据工厂。"""

    @staticmethod
    def bubble_sort_minimal() -> dict[str, Any]:
        return {
            "project_id": "test_001",
            "topic": "冒泡排序",
            "audience": "undergraduate_cs",
            "difficulty": "intermediate",
            "teaching_strategy": {
                "objectives": ["理解冒泡排序"],
                "prerequisites": ["数组"],
                "approach": "直觉先行",
            },
            "knowledge_graph": {
                "concepts": [
                    {"id": "c1", "name": "冒泡排序", "type": "definition"},
                ],
                "edges": [],
            },
            "parameters": [],
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "数组初始化",
                    "learning_goal": "了解初始数组",
                    "narration": "这是一个未排序的数组 [5, 3, 8, 1]。",
                    "visual_objects": [
                        {
                            "id": "arr_display",
                            "type": "array",
                            "label": "数组",
                            "position": {"x": 100, "y": 200},
                            "cells": [
                                {"value": 5}, {"value": 3}, {"value": 8}, {"value": 1},
                            ],
                        },
                    ],
                    "state_snapshot": {"array": [5, 3, 8, 1]},
                    "animations": [
                        {"type": "appear", "target": "arr_display", "duration_ms": 500},
                    ],
                    "interaction_hooks": [],
                    "checks": [],
                },
                {
                    "frame_id": "f_002",
                    "title": "第一轮比较",
                    "learning_goal": "理解相邻元素比较",
                    "narration": "比较 5 和 3，5 > 3，交换。",
                    "visual_objects": [
                        {
                            "id": "arr_display",
                            "type": "array",
                            "label": "数组",
                            "position": {"x": 100, "y": 200},
                            "cells": [
                                {"value": 3}, {"value": 5}, {"value": 8}, {"value": 1},
                            ],
                        },
                    ],
                    "state_snapshot": {"array": [3, 5, 8, 1]},
                    "animations": [
                        {"type": "highlight", "target": "arr_display", "duration_ms": 500},
                        {"type": "swap", "target": "cell_0", "target_2": "cell_1", "duration_ms": 800},
                    ],
                    "interaction_hooks": [],
                    "checks": [],
                },
            ],
            "assets": [],
            "export_targets": ["web", "manim_video"],
        }

    @staticmethod
    def with_quality_issues() -> dict[str, Any]:
        """包含质量问题（帧缺少 frame_id、状态不一致）的 DSL。"""
        dsl = DSLFactory.bubble_sort_minimal()
        # 添加一个缺少 frame_id 的帧
        dsl["frames"].append({
            "title": "问题帧",
            "narration": "缺少 frame_id",
            "visual_objects": [],
            "state_snapshot": {},
            "animations": [],
            "interaction_hooks": [],
            "checks": [],
        })
        return dsl

    @staticmethod
    def empty() -> dict[str, Any]:
        return {
            "project_id": "test_empty",
            "topic": "空测试",
            "audience": "undergraduate_cs",
            "difficulty": "intermediate",
            "teaching_strategy": {
                "objectives": [],
                "prerequisites": [],
                "approach": "",
            },
            "knowledge_graph": {"concepts": [], "edges": []},
            "parameters": [],
            "frames": [],
            "assets": [],
            "export_targets": ["web"],
        }


# ============================================================================
# Async helpers
# ============================================================================


def async_return(value: Any) -> AsyncMock:
    """创建返回指定值的 AsyncMock。"""
    mock = AsyncMock()
    mock.return_value = value
    return mock


# ============================================================================
# SQLite test database
# ============================================================================


@pytest_asyncio.fixture
async def test_db():
    """创建 SQLite 内存数据库用于集成测试。

    使用 aiosqlite 避免 PostgreSQL 依赖，CI 友好。
    """
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from db.models import Base

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@dataclass
class AuthApiClient:
    """HTTP client and isolated database used by authentication API tests."""

    client: Any
    session_factory: Any


def _make_sqlite_compatible() -> None:
    """Adapt PostgreSQL-only model types for isolated HTTP API tests."""
    from sqlalchemy import schema, types
    from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID

    from db.models import Base

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, (JSONB, ARRAY)):
                column.type = types.JSON()
            elif isinstance(column.type, PG_UUID):
                column.type = types.Uuid(as_uuid=True)
                column.server_default = None
                if column.default is None and column.primary_key:
                    column.default = schema.ColumnDefault(uuid.uuid4)


@pytest_asyncio.fixture
async def auth_api_client() -> AuthApiClient:
    """Run authentication requests against an isolated transactional database."""
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from db.models import Base
    from db.database import get_readonly_session, get_session
    from main import app

    _make_sqlite_compatible()
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def get_test_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def get_test_readonly_session():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.rollback()

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_readonly_session] = get_test_readonly_session
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield AuthApiClient(client=client, session_factory=session_factory)

    app.dependency_overrides.clear()
    await engine.dispose()


# ============================================================================
# Mock LLM fixture
# ============================================================================


@pytest.fixture
def mock_llm_client():
    """Mock LLM 客户端 — 所有 chat.completions.create 调用被拦截。"""
    with patch("agents.llm_client._get_llm_client") as mock_get:
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_get.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_embedding_client():
    """Mock Embedding 客户端。"""
    with patch("agents.llm_client._get_embedding_client") as mock_get:
        mock_client = MagicMock()
        mock_client.embeddings = MagicMock()
        mock_client.embeddings.create = AsyncMock()
        mock_get.return_value = mock_client
        yield mock_client
