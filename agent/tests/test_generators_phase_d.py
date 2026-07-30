"""Phase D 生成器测试 — Misconception + Pathway + Sandbox。"""

from __future__ import annotations

from unittest.mock import patch

import pytest


def _ensure_registered():
    from generators.registry import register_generator, has_generator
    if not has_generator("misconception"):
        from generators.misconception_generator import MisconceptionGenerator
        register_generator(MisconceptionGenerator())
    if not has_generator("pathway"):
        from generators.pathway_generator import PathwayGenerator
        register_generator(PathwayGenerator())
    if not has_generator("sandbox"):
        from generators.sandbox_generator import SandboxGenerator
        register_generator(SandboxGenerator())


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
    return {"objectives": ["Test"], "outline": [{"step": 1, "title": "I", "key_points": ["p"], "estimated_frames": 1}],
            "teaching_approach": "T", "estimated_total_frames": 1}


@pytest.fixture
def kg():
    return {"concepts": [{"id": "c1", "name": "Sort", "type": "definition", "common_pitfalls": ["P1"]}], "edges": []}


# ============================================================================
# Misconception
# ============================================================================

class TestMisconceptionGenerator:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("misconception")

    def test_metadata(self, gen):
        assert gen.module_id == "misconception"
        assert gen.category == "visual"

    async def test_generate(self, gen, mock_llm, plan, kg):
        mock_llm.return_value = {"items": [
            {"id": "m1", "concept": "Sort", "misconception": "Wrong idea", "correction": "Right idea",
             "counter_example": "Example", "why_it_matters": "Important", "difficulty": 2},
        ]}
        result = await gen.generate(teaching_plan=plan, knowledge_graph=kg, user_input="T", constraints={}, project_id="t")
        assert len(result["items"]) == 1

    def test_validate_passes(self, gen):
        output = {"items": [{"id": "m1", "concept": "C", "misconception": "Wrong", "correction": "Right right right"}]}
        errors = [i for i in gen.validate(output) if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_detects_empty(self, gen):
        assert any("empty_items" in i.get("type", "") for i in gen.validate({"items": []}))

    def test_validate_missing_fields(self, gen):
        issues = gen.validate({"items": [{"id": "x"}]})
        assert any("missing_misconception" in i.get("type", "") for i in issues)
        assert any("missing_correction" in i.get("type", "") for i in issues)

    def test_validate_short_correction(self, gen):
        issues = gen.validate({"items": [{"id": "x", "concept": "C", "misconception": "W", "correction": "Short"}]})
        assert any("short_correction" in i.get("type", "") for i in issues)

    def test_validate_non_dict(self, gen):
        assert any(i["severity"] == "high" for i in gen.validate(None))

    def test_validate_items_not_list(self, gen):
        issues = gen.validate({"items": "not a list"})
        assert any("invalid_items" in i.get("type", "") for i in issues)


# ============================================================================
# Pathway
# ============================================================================

class TestPathwayGenerator:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("pathway")

    def test_metadata(self, gen):
        assert gen.module_id == "pathway"

    async def test_generate(self, gen, mock_llm, plan, kg):
        mock_llm.return_value = {
            "current_topic": "Sort",
            "nodes": [
                {"id": "n1", "name": "Arrays", "type": "prerequisite", "description": "Learn arrays"},
                {"id": "n2", "name": "Sorting", "type": "core", "description": "Main topic"},
                {"id": "n3", "name": "QuickSort", "type": "extension", "description": "Advanced"},
                {"id": "n4", "name": "MergeSort", "type": "extension", "description": "Alternative"},
            ],
            "edges": [{"source": "n1", "target": "n2", "relation": "depends_on"}],
        }
        result = await gen.generate(teaching_plan=plan, knowledge_graph=kg, user_input="T", constraints={}, project_id="t")
        assert len(result["nodes"]) == 4

    def test_validate_passes(self, gen):
        output = {
            "current_topic": "T", "nodes": [
                {"id": "n1", "name": "P", "type": "prerequisite", "description": "d"},
                {"id": "n2", "name": "C", "type": "core", "description": "d"},
                {"id": "n3", "name": "E", "type": "extension", "description": "d"},
                {"id": "n4", "name": "A", "type": "application", "description": "d"},
            ], "edges": [],
        }
        errors = [i for i in gen.validate(output) if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_too_few_nodes(self, gen):
        output = {"current_topic": "T", "nodes": [{"id": "n1", "name": "A", "type": "core", "description": "d"}], "edges": []}
        assert any("too_few_nodes" in i.get("type", "") for i in gen.validate(output))

    def test_validate_no_prereqs(self, gen):
        output = {
            "current_topic": "T", "nodes": [
                {"id": "n1", "name": "C", "type": "core", "description": "d"},
                {"id": "n2", "name": "E1", "type": "extension", "description": "d"},
                {"id": "n3", "name": "E2", "type": "extension", "description": "d"},
                {"id": "n4", "name": "R", "type": "related", "description": "d"},
            ], "edges": [],
        }
        assert any("no_prereqs" in i.get("type", "") for i in gen.validate(output))

    def test_validate_dangling_edges(self, gen):
        output = {
            "current_topic": "T", "nodes": [
                {"id": "n1", "name": "P", "type": "prerequisite", "description": "d"},
                {"id": "n2", "name": "C", "type": "core", "description": "d"},
                {"id": "n3", "name": "E", "type": "extension", "description": "d"},
                {"id": "n4", "name": "R", "type": "related", "description": "d"},
            ],
            "edges": [{"source": "n1", "target": "n99", "relation": "depends_on"}],  # n99 doesn't exist
        }
        assert any("dangling_edge" in i.get("type", "") for i in gen.validate(output))

    def test_validate_non_dict(self, gen):
        assert any(i["severity"] == "high" for i in gen.validate(None))


# ============================================================================
# Sandbox
# ============================================================================

class TestSandboxGenerator:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("sandbox")

    def test_metadata(self, gen):
        assert gen.module_id == "sandbox"
        assert gen.category == "interactive"

    async def test_generate(self, gen, mock_llm, plan, kg):
        mock_llm.return_value = {
            "language": "python",
            "starter_code": "def sort(arr):\n    # TODO\n    pass",
            "full_solution": "def sort(arr):\n    return sorted(arr)",
            "test_cases": [
                {"name": "T1", "input": {"arr": [3,1,2]}, "expected_output": {"sorted": [1,2,3]}},
                {"name": "T2", "input": {"arr": []}, "expected_output": {"sorted": []}},
            ],
            "time_complexity": "O(n log n)", "space_complexity": "O(n)",
        }
        result = await gen.generate(teaching_plan=plan, knowledge_graph=kg, user_input="T", constraints={}, project_id="t")
        assert result["language"] == "python"
        assert len(result["test_cases"]) == 2

    def test_validate_passes(self, gen):
        output = {
            "language": "python", "starter_code": "def f(): pass  # TODO: implement",
            "full_solution": "def f():\n    # Full implementation with proper algorithm logic here\n    return result",
            "test_cases": [{"name": "T1", "input": {}, "expected_output": {}}, {"name": "T2", "input": {}, "expected_output": {}}],
        }
        errors = [i for i in gen.validate(output) if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_too_few_tests(self, gen):
        output = {"language": "python", "starter_code": "def f(): pass", "full_solution": "def f():\n    return 1", "test_cases": [
            {"name": "T1", "input": {}, "expected_output": {}},
        ]}
        assert any("too_few_tests" in i.get("type", "") for i in gen.validate(output))

    def test_validate_short_starter(self, gen):
        output = {"language": "python", "starter_code": "x", "full_solution": "def f():\n    return 1", "test_cases": [
            {"name": "T1", "input": {}, "expected_output": {}}, {"name": "T2", "input": {}, "expected_output": {}},
        ]}
        assert any("short_starter" in i.get("type", "") for i in gen.validate(output))

    def test_validate_short_solution(self, gen):
        output = {"language": "python", "starter_code": "def f(): pass", "full_solution": "short", "test_cases": [
            {"name": "T1", "input": {}, "expected_output": {}}, {"name": "T2", "input": {}, "expected_output": {}},
        ]}
        assert any("short_solution" in i.get("type", "") for i in gen.validate(output))

    def test_validate_non_dict(self, gen):
        assert any(i["severity"] == "high" for i in gen.validate(None))


# ============================================================================
# Integration
# ============================================================================

class TestPhaseDIntegration:
    async def test_all_three_in_dispatcher(self, mock_llm):
        from services.module_dispatcher import dispatch_modules

        mock_llm.side_effect = lambda **kw: (
            {"items": [{"id": "x", "concept": "C", "misconception": "W", "correction": "R"}]}
            if "items" in kw.get("output_schema", {}).get("properties", {})
            else {"current_topic": "T", "nodes": [
                {"id": "n1", "name": "P", "type": "prerequisite", "description": "d"},
                {"id": "n2", "name": "C", "type": "core", "description": "d"},
                {"id": "n3", "name": "E", "type": "extension", "description": "d"},
                {"id": "n4", "name": "A", "type": "application", "description": "d"},
            ], "edges": []}
            if "nodes" in kw.get("output_schema", {}).get("properties", {})
            else {"language": "python", "starter_code": "def f(): pass",
                  "full_solution": "def f():\n    return 1", "test_cases": [
                      {"name": "T1", "input": {}, "expected_output": {}},
                      {"name": "T2", "input": {}, "expected_output": {}},
                  ]}
        )

        state = {
            "user_input": "T", "project_id": "00000000-0000-0000-0000-000000000030",
            "teaching_plan": {"objectives": ["T"], "outline": [{"step": 1, "title": "I", "key_points": ["p"], "estimated_frames": 1}], "teaching_approach": "T", "estimated_total_frames": 1},
            "knowledge_graph": {"concepts": [{"id": "c1", "name": "T", "type": "definition"}], "edges": []},
            "constraints": {}, "status": "generating", "reflection_count": 0, "revision_history": [],
        }
        events = []
        async for evt in dispatch_modules("00000000-0000-0000-0000-000000000030", state, ["misconception", "pathway", "sandbox"]):
            events.append(evt)

        import json
        done_ids = {json.loads(e["data"])["module_id"] for e in events if e["event"] == "module_done"}
        assert done_ids == {"misconception", "pathway", "sandbox"}


# ============================================================================
# Security
# ============================================================================

class TestPhaseDSecurity:
    def test_all_three_handle_xss_in_validate(self):
        from generators.registry import get_generator
        for mod_id in ("misconception", "pathway", "sandbox"):
            gen = get_generator(mod_id)
            assert gen is not None, f"{mod_id} not found"
            issues = gen.validate({"items": [{"id": "x", "concept": "<script>alert(1)</script>", "misconception": "<b>W</b>", "correction": "R" * 20}]})
            assert isinstance(issues, list)
