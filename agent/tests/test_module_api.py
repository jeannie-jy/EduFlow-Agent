"""模块生成 API 端点集成测试。

测试新增的 /generate/modules GET/POST/stream 端点。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from generators.registry import clear_registry, register_generator


# ============================================================================
# Mock Generator（用于注册表）
# ============================================================================


class _MockCardGenerator:
    module_id = "cards"
    display_name = "知识卡片"
    description = "生成知识卡片"
    icon = "cards"
    category = "visual"
    priority = 2
    version = "1.0.0"

    async def generate(self, **kwargs):
        return {"cards": []}

    def validate(self, output):
        return []

    def get_output_schema(self):
        return {"type": "object"}

    def get_system_prompt(self):
        return "You are a card generator."


class _MockMindmapGenerator:
    module_id = "mindmap"
    display_name = "思维导图"
    description = "生成思维导图"
    icon = "mindmap"
    category = "visual"
    priority = 1
    version = "1.0.0"

    async def generate(self, **kwargs):
        return {"root": {"name": "test"}}

    def validate(self, output):
        return []

    def get_output_schema(self):
        return {"type": "object"}

    def get_system_prompt(self):
        return "You are a mindmap generator."


# ============================================================================
# Helpers
# ============================================================================


def _make_session(with_project: bool = False) -> AsyncMock:
    """创建 mock DB 会话（复用 test_api_integration 模式）。"""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=[])
    exec_result = MagicMock()
    exec_result.scalar = MagicMock(return_value=0)
    exec_result.scalar_one_or_none = MagicMock(return_value=None)
    exec_result.scalars = MagicMock(return_value=scalars_mock)
    exec_result.fetchall = MagicMock(return_value=[])
    session.execute = AsyncMock(return_value=exec_result)

    if with_project:
        mock_project = MagicMock()
        mock_project.id = "00000000-0000-0000-0000-000000000001"
        mock_project.title = "Test Project"
        mock_project.status = "planning"
        mock_project.dsl_snapshot = {
            "teaching_plan": {"objectives": ["test"]},
            "input_content": "Test topic",
            "constraints": {},
        }
        mock_project.audience = "undergraduate_cs"
        mock_project.difficulty = "intermediate"
        mock_project.created_at = None
        mock_project.updated_at = None
        session.get = AsyncMock(return_value=mock_project)
    else:
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
        session.get = AsyncMock(return_value=mock_frame)

    return session


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _clean_registry():
    """每个测试前后清空注册表 + 注册 mock 生成器。"""
    clear_registry()
    register_generator(_MockCardGenerator())
    register_generator(_MockMindmapGenerator())
    yield
    clear_registry()


@pytest_asyncio.fixture
async def client():
    """创建异步 HTTP 测试客户端（无真实 DB）。"""
    from main import app
    from db.database import get_session, get_readonly_session

    app.dependency_overrides[get_session] = lambda: _make_session(with_project=True)
    app.dependency_overrides[get_readonly_session] = lambda: _make_session(with_project=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ============================================================================
# Tests: GET /modules
# ============================================================================


class TestListModules:
    """测试 GET /api/projects/{id}/generate/modules。"""

    async def test_list_modules_returns_all_registered(self, client):
        res = await client.get("/api/projects/00000000-0000-0000-0000-000000000001/generate/modules")
        assert res.status_code == 200
        body = res.json()
        assert "modules" in body
        assert len(body["modules"]) == 2
        ids = {m["module_id"] for m in body["modules"]}
        assert ids == {"cards", "mindmap"}

    async def test_list_modules_sorted_by_priority(self, client):
        res = await client.get("/api/projects/00000000-0000-0000-0000-000000000001/generate/modules")
        body = res.json()
        # mindmap priority=1, cards priority=2
        assert body["modules"][0]["module_id"] == "mindmap"
        assert body["modules"][1]["module_id"] == "cards"

    async def test_list_modules_has_required_fields(self, client):
        res = await client.get("/api/projects/00000000-0000-0000-0000-000000000001/generate/modules")
        body = res.json()
        for mod in body["modules"]:
            for field in ("module_id", "display_name", "description", "icon", "category", "priority"):
                assert field in mod, f"Missing field {field} in {mod['module_id']}"

    async def test_list_modules_empty_registry(self, client):
        clear_registry()
        res = await client.get("/api/projects/00000000-0000-0000-0000-000000000001/generate/modules")
        assert res.status_code == 200
        body = res.json()
        assert body["modules"] == []

    async def test_list_modules_works_without_project(self, client):
        """模块列表不依赖项目存在性，即使项目不存在也返回200。"""
        from db.database import get_session
        from main import app

        no_session = _make_session(with_project=False)
        no_session.get = AsyncMock(return_value=None)
        app.dependency_overrides[get_session] = lambda: no_session
        res = await client.get("/api/projects/00000000-0000-0000-0000-000000000099/generate/modules")
        assert res.status_code == 200  # 不再要求项目存在
        app.dependency_overrides.clear()
        app.dependency_overrides[get_session] = lambda: _make_session(with_project=True)


# ============================================================================
# Tests: POST /modules
# ============================================================================


class TestStartModuleGeneration:
    """测试 POST /api/projects/{id}/generate/modules。"""

    async def test_start_module_generation_returns_stream_url(self, client):
        res = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000001/generate/modules",
            json={"modules": ["cards", "mindmap"]},
        )
        assert res.status_code == 202
        body = res.json()
        assert "stream_url" in body
        assert "modules" in body
        assert body["modules"] == ["cards", "mindmap"]

    async def test_start_requires_at_least_one_module(self, client):
        res = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000001/generate/modules",
            json={"modules": []},
        )
        assert res.status_code == 422  # Pydantic validation: min_length=1

    async def test_start_unknown_module_returns_400(self, client):
        res = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000001/generate/modules",
            json={"modules": ["unknown_module_xyz"]},
        )
        assert res.status_code == 400
        body = res.json()
        assert "Unknown module" in body["error"]["message"]

    async def test_start_mixed_valid_and_invalid(self, client):
        res = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000001/generate/modules",
            json={"modules": ["cards", "bogus"]},
        )
        assert res.status_code == 400

    async def test_start_missing_modules_field(self, client):
        res = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000001/generate/modules",
            json={},
        )
        assert res.status_code == 422

    async def test_start_project_404(self, client):
        from db.database import get_session
        from main import app

        no_session = _make_session(with_project=False)
        no_session.get = AsyncMock(return_value=None)
        app.dependency_overrides[get_session] = lambda: no_session
        res = await client.post(
            "/api/projects/00000000-0000-0000-0000-000000000099/generate/modules",
            json={"modules": ["cards"]},
        )
        assert res.status_code == 404
        app.dependency_overrides.clear()
        app.dependency_overrides[get_session] = lambda: _make_session(with_project=True)


# ============================================================================
# Tests: GET /modules/stream
# ============================================================================


class TestModuleGenerationStream:
    """测试 GET /api/projects/{id}/generate/modules/stream（SSE 流）。"""

    async def test_stream_endpoint_returns_200(self, client):
        # SSE 流本身会挂起等待生成，这里验证端点可访问且 content-type 正确
        # 由于 dispatch_modules 依赖真实 agent service，这里做基本连通性测试
        from db.database import get_session
        from main import app

        # 使用带 _pending_modules 的 project
        session = _make_session(with_project=True)
        session.get = AsyncMock(return_value=MagicMock(
            id="00000000-0000-0000-0000-000000000001",
            title="Test",
            status="generating",
            dsl_snapshot={
                "teaching_plan": {"objectives": ["test"]},
                "knowledge_graph": {"concepts": [{"id": "c1"}]},
                "input_content": "Test",
                "constraints": {},
                "_pending_modules": ["cards"],
            },
            audience="undergraduate_cs",
            difficulty="intermediate",
            created_at=None,
            updated_at=None,
        ))

        app.dependency_overrides[get_session] = lambda: session
        res = await client.get("/api/projects/00000000-0000-0000-0000-000000000001/generate/modules/stream")
        assert res.status_code == 200
        assert "text/event-stream" in res.headers.get("content-type", "")
        app.dependency_overrides.clear()
        app.dependency_overrides[get_session] = lambda: _make_session(with_project=True)

    async def test_stream_project_404(self, client):
        from db.database import get_session
        from main import app

        no_session = _make_session(with_project=False)
        no_session.get = AsyncMock(return_value=None)
        app.dependency_overrides[get_session] = lambda: no_session
        res = await client.get("/api/projects/00000000-0000-0000-0000-000000000099/generate/modules/stream")
        assert res.status_code == 404
        app.dependency_overrides.clear()
        app.dependency_overrides[get_session] = lambda: _make_session(with_project=True)
