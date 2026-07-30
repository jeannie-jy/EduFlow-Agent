"""Phase D 生成器边界与极端情况深度测试。

补充 test_generators_phase_d.py 未覆盖的边界/LLM恢复/多语言/大数据量。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


def _ensure_registered():
    from generators.registry import register_generator, has_generator
    for mod_id, cls_name in [
        ("misconception", "MisconceptionGenerator"), ("pathway", "PathwayGenerator"), ("sandbox", "SandboxGenerator"),
    ]:
        if not has_generator(mod_id):
            mod = __import__(f"generators.{mod_id}_generator", fromlist=[cls_name])
            register_generator(getattr(mod, cls_name)())


@pytest.fixture(autouse=True)
def _setup():
    _ensure_registered()
    yield


@pytest.fixture
def mock_llm():
    with patch("agents.llm_client.call_llm_structured") as m:
        yield m


@pytest.fixture
def plan():
    return {"objectives": ["T"], "outline": [{"step": 1, "title": "I", "key_points": ["p"], "estimated_frames": 1}],
            "teaching_approach": "A", "estimated_total_frames": 1}


@pytest.fixture
def kg():
    return {"concepts": [{"id": "c1", "name": "Sort", "type": "definition", "common_pitfalls": ["P1"]}], "edges": []}


# ============================================================================
# Misconception Edge Cases
# ============================================================================

class TestMisconceptionEdges:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("misconception")

    async def test_llm_returns_no_items(self, gen, mock_llm, plan, kg):
        mock_llm.return_value = {}
        result = await gen.generate(teaching_plan=plan, knowledge_graph=kg, user_input="T", constraints={}, project_id="t")
        issues = gen.validate(result)
        assert any("empty_items" in i.get("type", "") for i in issues)

    async def test_llm_raises_exception(self, gen, mock_llm, plan, kg):
        mock_llm.side_effect = RuntimeError("API down")
        with pytest.raises(RuntimeError):
            await gen.generate(teaching_plan=plan, knowledge_graph=kg, user_input="T", constraints={}, project_id="t")

    def test_validate_items_with_none_element(self, gen):
        output = {"items": [
            {"id": "m1", "concept": "C", "misconception": "W", "correction": "R" * 20},
            None,  # non-dict
        ]}
        issues = gen.validate(output)
        assert isinstance(issues, list)

    def test_validate_many_items(self, gen):
        """大量误区不超时。"""
        import time
        output = {"items": [
            {"id": f"m{i}", "concept": "C", "misconception": "W" * 50, "correction": "R" * 100,
             "counter_example": "E" * 100, "why_it_matters": "I" * 50, "difficulty": (i % 3) + 1}
            for i in range(50)
        ]}
        start = time.monotonic()
        issues = gen.validate(output)
        assert time.monotonic() - start < 5.0
        assert isinstance(issues, list)

    def test_validate_missing_optional_fields_ok(self, gen):
        """counter_example 和 why_it_matters 是可选的。"""
        output = {"items": [{"id": "m1", "concept": "C", "misconception": "W", "correction": "R" * 20}]}
        errors = [i for i in gen.validate(output) if i["severity"] == "error"]
        assert len(errors) == 0

    def test_build_context_includes_pitfalls(self, gen, plan, kg):
        ctx = gen._build_context(plan, kg, "T", {})
        assert ctx["concepts"][0]["pitfalls_hint"] == ["P1"]

    def test_build_context_empty_kg(self, gen, plan):
        ctx = gen._build_context(plan, {"concepts": [], "edges": []}, "T", {})
        assert ctx["concepts"] == []


# ============================================================================
# Pathway Edge Cases
# ============================================================================

class TestPathwayEdges:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("pathway")

    async def test_llm_returns_partial(self, gen, mock_llm, plan, kg):
        mock_llm.return_value = {"current_topic": "T"}
        result = await gen.generate(teaching_plan=plan, knowledge_graph=kg, user_input="T", constraints={}, project_id="t")
        issues = gen.validate(result)
        assert any(i["severity"] == "high" for i in issues)

    def test_validate_all_node_types(self, gen):
        output = {
            "current_topic": "T", "nodes": [
                {"id": "n1", "name": "P", "type": "prerequisite", "description": "d"},
                {"id": "n2", "name": "C", "type": "core", "description": "d"},
                {"id": "n3", "name": "E", "type": "extension", "description": "d"},
                {"id": "n4", "name": "R", "type": "related", "description": "d"},
                {"id": "n5", "name": "A", "type": "application", "description": "d"},
            ], "edges": [],
        }
        errors = [i for i in gen.validate(output) if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_edges_with_invalid_source(self, gen):
        output = {
            "current_topic": "T", "nodes": [
                {"id": "n1", "name": "P", "type": "prerequisite", "description": "d"},
                {"id": "n2", "name": "C", "type": "core", "description": "d"},
                {"id": "n3", "name": "E", "type": "extension", "description": "d"},
                {"id": "n4", "name": "A", "type": "application", "description": "d"},
            ],
            "edges": [{"source": "ghost", "target": "n2", "relation": "depends_on"}],
        }
        assert any("dangling_edge" in i.get("type", "") for i in gen.validate(output))

    def test_validate_edges_with_invalid_target(self, gen):
        output = {
            "current_topic": "T", "nodes": [
                {"id": "n1", "name": "P", "type": "prerequisite", "description": "d"},
                {"id": "n2", "name": "C", "type": "core", "description": "d"},
                {"id": "n3", "name": "E", "type": "extension", "description": "d"},
                {"id": "n4", "name": "A", "type": "application", "description": "d"},
            ],
            "edges": [{"source": "n1", "target": "n99", "relation": "extends"}],
        }
        assert any("dangling_edge" in i.get("type", "") for i in gen.validate(output))

    def test_validate_nodes_not_a_list(self, gen):
        issues = gen.validate({"current_topic": "T", "nodes": "not_list", "edges": []})
        assert any("too_few_nodes" in i.get("type", "") for i in issues)

    def test_validate_edges_with_non_dict(self, gen):
        output = {
            "current_topic": "T", "nodes": [
                {"id": "n1", "name": "P", "type": "prerequisite", "description": "d"},
                {"id": "n2", "name": "C", "type": "core", "description": "d"},
                {"id": "n3", "name": "E", "type": "extension", "description": "d"},
                {"id": "n4", "name": "A", "type": "application", "description": "d"},
            ],
            "edges": ["not a dict", None, 123],
        }
        issues = gen.validate(output)
        assert isinstance(issues, list)

    def test_validate_many_nodes(self, gen):
        import time
        output = {
            "current_topic": "T", "nodes": [
                {"id": f"n{i}", "name": f"N{i}", "type": "core", "description": "d"}
                for i in range(100)
            ], "edges": [],
        }
        start = time.monotonic()
        issues = gen.validate(output)
        assert time.monotonic() - start < 5.0

    def test_validate_no_extensions(self, gen):
        output = {
            "current_topic": "T", "nodes": [
                {"id": "n1", "name": "P", "type": "prerequisite", "description": "d"},
                {"id": "n2", "name": "C", "type": "core", "description": "d"},
                {"id": "n3", "name": "R", "type": "related", "description": "d"},
                {"id": "n4", "name": "A", "type": "application", "description": "d"},
            ], "edges": [],
        }
        assert any("no_extensions" in i.get("type", "") for i in gen.validate(output))


# ============================================================================
# Sandbox Edge Cases
# ============================================================================

class TestSandboxEdges:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("sandbox")

    def test_validate_all_languages(self, gen):
        for lang in ("python", "javascript", "java", "cpp"):
            output = {"language": lang, "starter_code": "def f(): pass",
                      "full_solution": "def f():\n    return 1\n# proper implementation",
                      "test_cases": [{"name": "T1", "input": {}, "expected_output": {}},
                                     {"name": "T2", "input": {}, "expected_output": {}}]}
            errors = [i for i in gen.validate(output) if i["severity"] == "error"]
            assert len(errors) == 0, f"language={lang} should pass"

    async def test_llm_raises(self, gen, mock_llm, plan, kg):
        mock_llm.side_effect = TimeoutError("timeout")
        with pytest.raises(TimeoutError):
            await gen.generate(teaching_plan=plan, knowledge_graph=kg, user_input="T", constraints={}, project_id="t")

    def test_validate_test_cases_not_list(self, gen):
        output = {"language": "python", "starter_code": "def f(): pass",
                  "full_solution": "def f():\n    return 1",
                  "test_cases": "not_list"}
        issues = gen.validate(output)
        assert isinstance(issues, list)

    def test_validate_editable_params_optional(self, gen):
        output = {"language": "python", "starter_code": "def f(): pass",
                  "full_solution": "def f():\n    return 1",
                  "test_cases": [{"name": "T1", "input": {}, "expected_output": {}},
                                 {"name": "T2", "input": {}, "expected_output": {}}]}
        errors = [i for i in gen.validate(output) if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_massive_code(self, gen):
        import time
        output = {"language": "python",
                  "starter_code": "def f():\n" + "    pass\n" * 100,
                  "full_solution": "def f():\n" + "    x = 1\n" * 200,
                  "test_cases": [{"name": "T1", "input": {}, "expected_output": {}},
                                 {"name": "T2", "input": {}, "expected_output": {}}]}
        start = time.monotonic()
        issues = gen.validate(output)
        assert time.monotonic() - start < 5.0
