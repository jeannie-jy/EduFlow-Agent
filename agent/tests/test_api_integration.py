"""API 集成测试。

使用 FastAPI TestClient 测试所有 API 端点的正确性、边界条件和错误处理。
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ============================================================================
# Fixtures
# ============================================================================


def _make_session(with_project: bool = False) -> AsyncMock:
    """创建 mock 数据库会话。

    Args:
        with_project: True 时 .get() 返回 mock 项目对象（停用 404）
    """
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    # 模拟 execute 返回值 — scalars().all() 返回空列表
    # 注意：scalar/scalar_one_or_none/scalars 是同步方法，不用 AsyncMock
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=[])
    exec_result = MagicMock()
    exec_result.scalar = MagicMock(return_value=0)
    exec_result.scalar_one_or_none = MagicMock(return_value=None)
    exec_result.scalars = MagicMock(return_value=scalars_mock)
    exec_result.fetchall = MagicMock(return_value=[])
    session.execute = AsyncMock(return_value=exec_result)

    # 模拟 get() — 返回 mock 帧（含 is_locked 属性）
    mock_frame = MagicMock()
    mock_frame.id = "mock-frame-id"
    mock_frame.frame_id = "f_001"
    mock_frame.order_index = 1
    mock_frame.title = "mock"
    mock_frame.narration = "mock"
    mock_frame.visual_objects = []
    mock_frame.state_snapshot = {}
    mock_frame.animations = []
    mock_frame.interaction_hooks = []
    mock_frame.quality_status = "ok"
    mock_frame.is_locked = False
    mock_frame.updated_at = None

    mock_project = MagicMock()
    mock_project.id = "mock-project-id"
    mock_project.title = "mock"
    mock_project.status = "draft"
    mock_project.dsl_snapshot = {"frames": [], "parameters": []}
    mock_project.audience = "undergraduate_cs"
    mock_project.difficulty = "intermediate"
    mock_project.created_at = None
    mock_project.updated_at = None

    session.get = AsyncMock(return_value=mock_project if with_project else mock_frame)
    return session


@pytest_asyncio.fixture
async def client():
    """创建异步 HTTP 测试客户端。

    使用 FastAPI 内置的 dependency_overrides 替换 DB 会话，
    避免真实数据库连接。
    """
    from main import app
    from db.database import get_session, get_readonly_session
    from security.tokens import create_access_token

    mock_session = _make_session()

    # mock 项目对象（普通类实例，避免 MagicMock 的 coroutine 序列化问题）
    class _MockRow:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    mock_project = _MockRow(
        id="mock-project-id", title="mock", status="draft", topic=None,
        dsl_snapshot={"frames": [], "parameters": []},
        audience="undergraduate_cs", difficulty="intermediate",
        created_at=None, updated_at=None,
    )
    mock_frame = _MockRow(
        id="mock-frame-id", frame_id="f_001", order_index=1, version=1,
        title="mock", narration="mock",
        visual_objects=[], state_snapshot={}, animations=[],
        interaction_hooks=[], quality_status="ok", is_locked=False,
        updated_at=None,
    )
    user_id = uuid.uuid4()
    mock_user = _MockRow(id=user_id, is_active=True)

    async def _mock_get(model_cls, ident, **kw):
        # 特殊 UUID 用于 404 测试
        if str(ident) == "00000000-0000-0000-0000-000000000000":
            return None
        if model_cls.__name__ == "User":
            return mock_user
        return mock_project if "Project" in str(model_cls) else mock_frame

    mock_session.get = _mock_get

    app.dependency_overrides[get_session] = lambda: mock_session
    app.dependency_overrides[get_readonly_session] = lambda: mock_session

    transport = ASGITransport(app=app)
    access_token = create_access_token(user_id, uuid.uuid4())
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token.token}"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ============================================================================
# System endpoints
# ============================================================================


class TestHealthCheck:
    """健康检查端点测试。"""

    async def test_health_returns_200(self, client: AsyncClient):
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    async def test_ping_returns_200(self, client: AsyncClient):
        response = await client.get("/api/ping")
        assert response.status_code == 200
        assert response.json() == {"ping": "pong"}

    async def test_health_method_not_allowed(self, client: AsyncClient):
        """POST /api/health 应返回 405。"""
        response = await client.post("/api/health")
        assert response.status_code == 405

    async def test_openapi_schema_accessible(self, client: AsyncClient):
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "paths" in schema
        # 验证所有预期端点存在
        paths = schema["paths"]
        assert "/api/health" in paths
        assert "/api/projects" in paths
        assert "/api/projects/{project_id}" in paths
        assert "/api/projects/{project_id}/generate" in paths
        assert "/api/projects/{project_id}/generate/stream" in paths


# ============================================================================
# Knowledge endpoints
# ============================================================================


class TestKnowledgeAPI:
    """知识库 API 测试。"""

    async def test_search_returns_results(self, client: AsyncClient):
        """关键词搜索应返回匹配结果。"""
        response = await client.post(
            "/api/knowledge/search",
            json={"query": "冒泡排序", "top_k": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) >= 1
        # 冒泡排序应排在首位
        top = data["results"][0]
        assert "冒泡" in top["concept"] or top["similarity"] >= 0.7

    async def test_search_dijkstra(self, client: AsyncClient):
        response = await client.post(
            "/api/knowledge/search",
            json={"query": "Dijkstra shortest path", "top_k": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert any("Dijkstra" in r["concept"] for r in data["results"])

    async def test_search_empty_query(self, client: AsyncClient):
        """空查询应正常处理（不崩溃）。"""
        response = await client.post(
            "/api/knowledge/search",
            json={"query": "", "top_k": 5},
        )
        # 当前实现会返回低分结果，但不应崩溃
        assert response.status_code == 200

    async def test_search_top_k_capped(self, client: AsyncClient):
        """top_k 超过 50 应被限制。"""
        response = await client.post(
            "/api/knowledge/search",
            json={"query": "sort", "top_k": 100},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 22  # Phase 2: 22 条种子数据

    async def test_templates_list(self, client: AsyncClient):
        response = await client.get("/api/knowledge/templates")
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert len(data["templates"]) >= 5

    async def test_templates_filter_by_subject(self, client: AsyncClient):
        response = await client.get("/api/knowledge/templates?subject=algorithm")
        assert response.status_code == 200
        data = response.json()
        for t in data["templates"]:
            assert t["subject"] == "algorithm"

    async def test_templates_filter_by_difficulty(self, client: AsyncClient):
        response = await client.get("/api/knowledge/templates?difficulty=3")
        assert response.status_code == 200
        data = response.json()
        for t in data["templates"]:
            assert t["difficulty"] == 3

    async def test_search_missing_query_field(self, client: AsyncClient):
        """缺少 query 字段不应导致 500。"""
        response = await client.post(
            "/api/knowledge/search",
            json={"top_k": 5},
        )
        # FastAPI 不会自动拒绝（body 是 dict），应在 200 内处理
        assert response.status_code in (200, 422)


# ============================================================================
# Project CRUD endpoints
# ============================================================================


class TestProjectCRUD:
    """项目 CRUD API 测试。"""

    async def test_create_project_201(self, client: AsyncClient):
        response = await client.post(
            "/api/projects",
            json={
                "title": "测试项目-Dijkstra",
                "input_type": "natural_language",
                "input_content": "讲解 Dijkstra 算法",
                "audience": "undergraduate_cs",
                "difficulty": "intermediate",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "测试项目-Dijkstra"
        assert data["status"] == "draft"
        assert "id" in data
        assert "created_at" in data

    async def test_create_project_minimal(self, client: AsyncClient):
        """最小字段创建项目。"""
        response = await client.post(
            "/api/projects",
            json={"title": "最小项目"},
        )
        assert response.status_code == 201

    async def test_create_project_empty_title(self, client: AsyncClient):
        """空标题应被拒绝。"""
        response = await client.post(
            "/api/projects",
            json={"title": ""},
        )
        assert response.status_code == 422

    async def test_create_project_missing_title(self, client: AsyncClient):
        """缺少 title 应被拒绝。"""
        response = await client.post(
            "/api/projects",
            json={},
        )
        assert response.status_code == 422

    async def test_create_project_with_constraints(self, client: AsyncClient):
        response = await client.post(
            "/api/projects",
            json={
                "title": "TCP 三次握手讲解",
                "input_type": "natural_language",
                "input_content": "讲解 TCP 三次握手",
                "constraints": {
                    "must_cover": ["SYN", "ACK", "序列号"],
                    "style": "严谨直观",
                },
            },
        )
        assert response.status_code == 201

    async def test_list_projects(self, client: AsyncClient):
        response = await client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    async def test_list_projects_pagination(self, client: AsyncClient):
        response = await client.get("/api/projects?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    async def test_list_projects_invalid_page(self, client: AsyncClient):
        """负数页码应被拒绝。"""
        response = await client.get("/api/projects?page=-1")
        assert response.status_code == 422

    async def test_list_projects_zero_page_size(self, client: AsyncClient):
        """page_size=0 应被拒绝。"""
        response = await client.get("/api/projects?page_size=0")
        assert response.status_code == 422

    async def test_get_project_404(self, client: AsyncClient):
        """不存在的项目应返回 404。"""
        response = await client.get(
            "/api/projects/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    async def test_get_project_invalid_uuid(self, client: AsyncClient):
        """非法 UUID 格式不应导致 500。"""
        response = await client.get("/api/projects/not-a-uuid")
        # FastAPI 路径参数会返回 422
        assert response.status_code in (404, 422)


# ============================================================================
# Frame endpoints
# ============================================================================


class TestFrameAPI:
    """帧 API 测试。"""

    async def test_list_frames_empty(self, client: AsyncClient):
        """不存在的项目的帧列表应正确处理。"""
        response = await client.get(
            "/api/projects/00000000-0000-0000-0000-000000000000/frames"
        )
        assert response.status_code in (200, 404)

    async def test_update_frame_404(self, client: AsyncClient):
        response = await client.put(
            "/api/projects/00000000-0000-0000-0000-000000000000/frames/f_001",
            json={"title": "新的标题"},
        )
        assert response.status_code == 404

    async def test_lock_frame_404(self, client: AsyncClient):
        response = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/frames/f_001/lock",
            json={"is_locked": True},
        )
        assert response.status_code == 404


# ============================================================================
# Parameter endpoints
# ============================================================================


class TestParameterAPI:
    """参数 API 测试。"""

    async def test_list_parameters_empty(self, client: AsyncClient):
        response = await client.get(
            "/api/projects/00000000-0000-0000-0000-000000000000/parameters"
        )
        assert response.status_code in (200, 404)

    async def test_recompute_404(self, client: AsyncClient):
        response = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/recompute",
            json={"changed_params": {"key": "value"}},
        )
        assert response.status_code == 404


# ============================================================================
# Generate endpoints
# ============================================================================


class TestGenerateAPI:
    """生成流程 API 测试。"""

    async def test_start_generation_404(self, client: AsyncClient):
        response = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/generate",
            json={"action": "full"},
        )
        assert response.status_code == 404

    async def test_regenerate_404(self, client: AsyncClient):
        response = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/regenerate",
            json={"scope": {"type": "single_frame", "frame_ids": ["f_001"]}},
        )
        assert response.status_code == 404


# ============================================================================
# Feedback endpoints
# ============================================================================


class TestFeedbackAPI:
    """反馈 API 测试。"""

    async def test_submit_feedback_404(self, client: AsyncClient):
        response = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/feedback",
            json={
                "type": "correction",
                "content": "旋转方向画反了",
            },
        )
        assert response.status_code == 404

    async def test_submit_feedback_missing_content(self, client: AsyncClient):
        """缺少 content 字段应返回 422。"""
        # 由于项目 404 先触发，这个测试验证的是项目存在时的校验逻辑
        # 实际请求中 404 优先级高于 422
        response = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/feedback",
            json={"type": "correction"},
        )
        assert response.status_code in (404, 422)

    async def test_submit_feedback_invalid_rating(self, client: AsyncClient):
        """rating 超出范围应被拒绝。"""
        response = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/feedback",
            json={"type": "rating", "rating": 10},
        )
        assert response.status_code == 422

    async def test_submit_feedback_rating_missing(self, client: AsyncClient):
        """type=rating 时缺少 rating 字段。"""
        response = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/feedback",
            json={"type": "rating"},
        )
        assert response.status_code in (404, 422)


# ============================================================================
# CORS & Security
# ============================================================================


class TestCORSAndSecurity:
    """CORS 与安全测试。"""

    async def test_cors_headers(self, client: AsyncClient):
        response = await client.options(
            "/api/health",
            headers={"Origin": "http://localhost:5173"},
        )
        # OPTIONS 请求应返回恰当的 CORS 头
        assert response.status_code in (200, 405)

    async def test_no_sensitive_info_in_error(self, client: AsyncClient):
        """404 错误响应不应泄露内部信息。"""
        response = await client.get("/api/nonexistent")
        assert response.status_code == 404
        # 不应包含堆栈跟踪或内部路径
        body = response.text
        assert "traceback" not in body.lower()
        assert "sqlalchemy" not in body.lower()

    async def test_path_traversal_protected(self, client: AsyncClient):
        """路径遍历攻击应被阻止。"""
        response = await client.get("/api/projects/../../../etc/passwd")
        assert response.status_code in (404, 422)

    async def test_sql_injection_protected(self, client: AsyncClient):
        """SQL 注入尝试不应导致崩溃。"""
        response = await client.get("/api/projects/1' OR '1'='1")
        # FastAPI 的 UUID 校验会直接返回 422
        assert response.status_code in (404, 422)


# ============================================================================
# Content-Type validation
# ============================================================================


class TestContentTypeValidation:
    """Content-Type 校验测试。"""

    async def test_project_create_wrong_content_type(self, client: AsyncClient):
        """非 JSON Content-Type 应正常处理或返回 422。"""
        response = await client.post(
            "/api/projects",
            content="not-json",
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code in (400, 415, 422)

    async def test_knowledge_search_large_payload(self, client: AsyncClient):
        """大 payload 不应导致崩溃。"""
        large_query = "x" * 10000
        response = await client.post(
            "/api/knowledge/search",
            json={"query": large_query, "top_k": 5},
        )
        assert response.status_code == 200

    async def test_project_create_long_title(self, client: AsyncClient):
        """超长标题应被拒绝。"""
        response = await client.post(
            "/api/projects",
            json={"title": "x" * 1000},
        )
        assert response.status_code == 422
