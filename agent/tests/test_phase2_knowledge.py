"""Phase 2 Knowledge Agent 测试。"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch


class TestKnowledgeAgentPrompt:
    """Knowledge Agent 提示词完整性。"""

    def test_prompt_exists(self):
        from agents.prompts import KNOWLEDGE_SYSTEM_PROMPT
        assert len(KNOWLEDGE_SYSTEM_PROMPT) > 100
        assert "知识概念图" in KNOWLEDGE_SYSTEM_PROMPT
        assert "concepts" in KNOWLEDGE_SYSTEM_PROMPT
        assert "edges" in KNOWLEDGE_SYSTEM_PROMPT

    def test_prompt_includes_constraints(self):
        from agents.prompts import KNOWLEDGE_SYSTEM_PROMPT
        assert "depends_on" in KNOWLEDGE_SYSTEM_PROMPT
        assert "leads_to" in KNOWLEDGE_SYSTEM_PROMPT
        assert "contrasts_with" in KNOWLEDGE_SYSTEM_PROMPT


class TestKnowledgeNodeOutputSchema:
    """Knowledge Agent 输出 schema 验证。"""

    def test_schema_has_required_fields(self):
        """schema 定义了 concepts/edges/key_terms 必填。"""
        from agents.nodes import knowledge_node
        # 检查节点里的 output_schema
        import inspect
        source = inspect.getsource(knowledge_node)
        assert "concepts" in source
        assert "edges" in source
        assert "key_terms" in source
        assert "required" in source

    def test_concept_schema_includes_id_name_type(self):
        """concept 必须包含 id, name, type。"""
        import inspect
        from agents.nodes import knowledge_node
        source = inspect.getsource(knowledge_node)
        assert '"id"' in source
        assert '"name"' in source
        assert '"type"' in source

    def test_edge_schema_includes_source_target_relation(self):
        """edge 必须包含 source, target, relation。"""
        import inspect
        from agents.nodes import knowledge_node
        source = inspect.getsource(knowledge_node)
        assert '"source"' in source
        assert '"target"' in source
        assert '"relation"' in source


class TestKnowledgeNodeFallback:
    """Knowledge Agent 异常回退测试。"""

    @pytest.mark.asyncio
    async def test_fallback_on_llm_failure(self):
        """LLM 失败时应返回最小知识图谱回退值。"""
        from agents.nodes import knowledge_node
        from agents.state import AgentState

        state: AgentState = {
            "user_input": "测试二叉树",
            "teaching_plan": {
                "objectives": ["理解二叉树旋转"],
                "outline": [{"step": 1, "title": "概述", "key_points": [], "estimated_frames": 3}],
            },
        }

        # Mock call_llm_structured 抛出异常
        with patch("agents.nodes.call_llm_structured", side_effect=RuntimeError("LLM unavailable")):
            result = await knowledge_node(state)

        assert "knowledge_graph" in result
        assert "key_terms" in result
        kg = result["knowledge_graph"]
        # 回退值至少有一个概念
        assert len(kg.get("concepts", [])) >= 1
        assert kg["concepts"][0]["id"] == "c1"

    @pytest.mark.asyncio
    async def test_fallback_preserves_key_terms_list(self):
        """回退时 key_terms 应是 list 而非 None。"""
        from agents.nodes import knowledge_node
        from agents.state import AgentState

        state: AgentState = {
            "user_input": "测试",
            "teaching_plan": {"objectives": ["test"], "outline": []},
        }

        with patch("agents.nodes.call_llm_structured", side_effect=RuntimeError("fail")):
            result = await knowledge_node(state)

        assert isinstance(result.get("key_terms"), list)


class TestGraphKnowledgeTopology:
    """验证 LangGraph 图中 Knowledge 节点的拓扑位置。"""

    @pytest.mark.skipif(True, reason="langgraph 未安装，跳过图拓扑测试")
    def test_knowledge_node_exists(self):
        """图中应包含 'knowledge' 节点。"""
        from agents.graph import build_graph
        graph = build_graph()
        nodes = graph.get_graph().nodes
        assert "knowledge" in nodes, f"knowledge node missing from graph nodes: {list(nodes.keys())}"

    @pytest.mark.skipif(True, reason="langgraph 未安装")
    def test_planner_to_knowledge_edge(self):
        """Planner → Knowledge 边应存在。"""
        from agents.graph import build_graph
        graph = build_graph()
        # 检查编译后的图结构
        edges = graph.get_graph().edges
        # edges 是一个 dict，key 是源节点，value 是目标节点集合
        assert "planner" in edges, "planner should have outgoing edges"
        targets = list(edges["planner"])
        assert "knowledge" in targets or any(
            "knowledge" in str(t) for t in targets
        ), f"planner should connect to knowledge, got: {targets}"

    @pytest.mark.skipif(True, reason="langgraph 未安装")
    def test_knowledge_to_coder_edge(self):
        """Knowledge → Coder 边应存在。"""
        from agents.graph import build_graph
        graph = build_graph()
        edges = graph.get_graph().edges
        assert "knowledge" in edges, "knowledge should have outgoing edges"
        targets = list(edges["knowledge"])
        assert "coder" in targets or any(
            "coder" in str(t) for t in targets
        ), f"knowledge should connect to coder, got: {targets}"


class TestQualityAgentUpgrade:
    """Quality Agent Phase 2 升级测试。"""

    def test_quality_node_includes_llm_scoring(self):
        """quality_node 应包含 LLM 六维度评分逻辑。"""
        import inspect
        from agents.nodes import quality_node
        source = inspect.getsource(quality_node)
        # Phase 2 应有 LLM 评分调用的证据
        assert "call_llm_structured" in source
        assert "correctness" in source
        assert "clarity" in source
        assert "coherence" in source
        assert "interactivity" in source

    def test_quality_node_layer3_condition(self):
        """Layer 3 (LLM 评分) 仅在 frames 非空时执行。"""
        import inspect
        from agents.nodes import quality_node
        source = inspect.getsource(quality_node)
        assert "if frames:" in source, "LLM scoring should be conditional on frames"


class TestExportEndpoints:
    """导出 API 端点验证。"""

    def test_export_routes_registered(self):
        """导出端点应已在 API 中注册。"""
        from main import app
        schema = app.openapi()
        paths = schema.get("paths", {})
        export_paths = [p for p in paths if "export" in p]
        assert len(export_paths) >= 3, f"Expected 3+ export paths, got {len(export_paths)}: {export_paths}"

    def test_create_export_route(self):
        """POST projects/{id}/export/manim 应存在。"""
        from main import app
        schema = app.openapi()
        paths = schema["paths"]
        assert any("export/manim" in p for p in paths), "Missing export/manim route"
