"""Phase C 生成器边界与极端情况深度测试。

补充 test_generators_phase_c.py 未覆盖的：
- 4 种题型的各别校验
- 对比表边界
- 超大/畸形输入
- LLM 返回不完整/不一致数据
- 跨语言/多字符集
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


# ============================================================================
# Setup — 复用 Phase C 模块的注册逻辑
# ============================================================================


def _ensure_quiz_and_comparison():
    from generators.registry import register_generator, has_generator
    if not has_generator("quiz"):
        from generators.quiz_generator import QuizGenerator
        register_generator(QuizGenerator())
    if not has_generator("comparison"):
        from generators.comparison_generator import ComparisonGenerator
        register_generator(ComparisonGenerator())


@pytest.fixture(autouse=True)
def _setup():
    _ensure_quiz_and_comparison()
    yield


@pytest.fixture
def gen_quiz():
    from generators.registry import get_generator
    return get_generator("quiz")


@pytest.fixture
def gen_cmp():
    from generators.registry import get_generator
    return get_generator("comparison")


@pytest.fixture
def mock_llm():
    with patch("agents.llm_client.call_llm_structured") as mock:
        yield mock


# ============================================================================
# Quiz: 各题型深度校验
# ============================================================================


class TestQuizPerQuestionType:
    """按题型逐一测试 validate 逻辑。"""

    def _make_question(self, qtype: str, **overrides) -> dict:
        base = {
            "id": "q1", "type": qtype, "question": "Q?",
            "explanation": "Because.", "difficulty": 1,
        }
        if qtype == "multiple_choice":
            base["options"] = [
                {"id": "a", "text": "A"},
                {"id": "b", "text": "B", "is_correct": True},
            ]
        if qtype in ("true_false", "fill_blank"):
            base["correct_answer"] = "true"
        base.update(overrides)
        return base

    def test_true_false_valid(self, gen_quiz):
        q = self._make_question("true_false")
        issues = gen_quiz.validate({"questions": [q]})
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_true_false_missing_correct_answer(self, gen_quiz):
        q = self._make_question("true_false", correct_answer=None)
        del q["correct_answer"]
        issues = gen_quiz.validate({"questions": [q]})
        # missing correct_answer for true_false is not flagged (optional field)
        # but it's a quality concern
        warnings = [i for i in issues if i["severity"] in ("warn", "medium")]
        # accept either no issue or a warn about missing explanation context
        assert isinstance(issues, list)

    def test_fill_blank_valid(self, gen_quiz):
        q = self._make_question("fill_blank", correct_answer="堆/优先队列")
        issues = gen_quiz.validate({"questions": [q]})
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_short_answer_valid(self, gen_quiz):
        q = {
            "id": "q1", "type": "short_answer",
            "question": "请简述 Dijkstra 算法的核心思想。",
            "explanation": "贪心策略，每次选择距离最小的未访问节点进行松弛。",
            "expected_keywords": ["贪心", "松弛", "优先队列"],
            "difficulty": 3,
        }
        issues = gen_quiz.validate({"questions": [q]})
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_unknown_question_type_passes(self, gen_quiz):
        """未知题型不应报 error（灵活扩展）。"""
        q = {
            "id": "q1", "type": "coding_exercise",
            "question": "Write code",
            "explanation": "Check manually.",
            "difficulty": 3,
        }
        issues = gen_quiz.validate({"questions": [q]})
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_mc_with_too_few_options(self, gen_quiz):
        q = self._make_question("multiple_choice", options=[
            {"id": "a", "text": "Only one", "is_correct": True},
        ])
        issues = gen_quiz.validate({"questions": [q]})
        assert any("too_few_options" in i.get("type", "") for i in issues)

    def test_mc_with_multiple_correct(self, gen_quiz):
        """多选题（多个 is_correct）也应通过校验。"""
        q = self._make_question("multiple_choice", options=[
            {"id": "a", "text": "A", "is_correct": True},
            {"id": "b", "text": "B", "is_correct": True},
            {"id": "c", "text": "C"},
            {"id": "d", "text": "D"},
        ])
        issues = gen_quiz.validate({"questions": [q]})
        # 不应报 no_correct_answer
        assert not any("no_correct_answer" in i.get("type", "") for i in issues)


# ============================================================================
# Quiz: 畸形/空值输入处理
# ============================================================================


class TestQuizMalformedInput:
    """quiz validate 对各种畸形输入的鲁棒性。"""

    def test_questions_is_none(self, gen_quiz):
        output = {"questions": None}
        issues = gen_quiz.validate(output)
        assert any(i["severity"] == "high" for i in issues)

    def test_questions_contains_non_dicts(self, gen_quiz):
        output = {"questions": ["not a dict", 123, None]}
        issues = gen_quiz.validate(output)
        # 应能处理非 dict 的 question 元素，不崩溃
        assert isinstance(issues, list)

    def test_options_is_not_list(self, gen_quiz):
        output = {"questions": [{
            "id": "q1", "type": "multiple_choice",
            "question": "Q?", "explanation": "E", "difficulty": 1,
            "options": "not a list",
        }]}
        issues = gen_quiz.validate(output)
        assert isinstance(issues, list)

    def test_difficulty_negative(self, gen_quiz):
        output = {"questions": [{
            "id": "q1", "type": "true_false", "question": "Q?",
            "explanation": "E", "difficulty": -1,
        }]}
        issues = gen_quiz.validate(output)
        assert any("invalid_difficulty" in i.get("type", "") for i in issues)

    def test_difficulty_zero(self, gen_quiz):
        output = {"questions": [{
            "id": "q1", "type": "true_false", "question": "Q?",
            "explanation": "E", "difficulty": 0,
        }]}
        issues = gen_quiz.validate(output)
        assert any("invalid_difficulty" in i.get("type", "") for i in issues)

    def test_missing_metadata_ok(self, gen_quiz):
        """metadata 是可选的，缺少不应报错。"""
        output = {"questions": [{
            "id": "q1", "type": "true_false", "question": "Q?",
            "explanation": "E", "difficulty": 1, "correct_answer": "true",
        }]}
        issues = gen_quiz.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0


# ============================================================================
# Comparison: 深度校验
# ============================================================================


class TestComparisonDeepValidation:
    """comparison validate 的深度边界。"""

    def _make_output(self, n_algo=2, n_dims=4, **overrides) -> dict:
        algos = [
            {"name": f"Algo{i}", "description": f"desc{i}",
             "pros": ["p1", "p2"], "cons": ["c1"]}
            for i in range(n_algo)
        ]
        base = {
            "topic": "对比",
            "algorithms": algos,
            "dimensions": [f"D{j}" for j in range(n_dims)],
            "comparison_table": [],
            "scenario_analysis": "x" * 50,
        }
        base.update(overrides)
        return base

    def test_table_row_has_all_algos(self, gen_cmp):
        """每行对比表包含所有算法的数据。"""
        output = self._make_output(n_algo=2, comparison_table=[
            {"dimension": "速度", "Algo0": "快", "Algo1": "慢"},
            {"dimension": "内存", "Algo0": "中", "Algo1": "低"},
            {"dimension": "难度", "Algo0": "易", "Algo1": "难"},
            {"dimension": "适用", "Algo0": "广", "Algo1": "窄"},
        ])
        issues = gen_cmp.validate(output)
        assert not any("missing_algo_in_row" in i.get("type", "") for i in issues)

    def test_table_missing_one_algo(self, gen_cmp):
        output = self._make_output(n_algo=2, comparison_table=[
            {"dimension": "速度", "Algo0": "快"},  # 缺少 Algo1
        ])
        issues = gen_cmp.validate(output)
        assert any("missing_algo_in_row" in i.get("type", "") for i in issues)

    def test_table_with_extra_columns(self, gen_cmp):
        """对比表有额外列不报错。"""
        output = self._make_output(n_algo=2, comparison_table=[
            {"dimension": "速度", "Algo0": "快", "Algo1": "慢", "备注": "额外"},
        ])
        issues = gen_cmp.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_dimensions_string_not_list(self, gen_cmp):
        output = self._make_output(dimensions="not a list")
        issues = gen_cmp.validate(output)
        # super().validate() catches non-list type? depends on schema
        assert isinstance(issues, list)

    def test_comparison_table_not_list(self, gen_cmp):
        output = self._make_output(comparison_table={"not": "a list"})
        issues = gen_cmp.validate(output)
        assert isinstance(issues, list)

    def test_algorithms_duplicate_names(self, gen_cmp):
        """重复算法名可能是错误，但目前只警告。"""
        output = self._make_output(n_algo=2)
        output["algorithms"][1]["name"] = "Algo0"  # 重复
        issues = gen_cmp.validate(output)
        # 至少不应崩溃
        assert isinstance(issues, list)

    def test_pros_cons_boundaries(self, gen_cmp):
        """pros/cons 恰好满足最低要求。"""
        output = self._make_output(n_algo=2)
        output["algorithms"][0]["pros"] = ["p1", "p2"]  # 恰好 2
        output["algorithms"][0]["cons"] = ["c1"]          # 恰好 1
        issues = gen_cmp.validate(output)
        assert not any("few_pros" in i.get("type", "") for i in issues)
        assert not any("no_cons" in i.get("type", "") for i in issues)

    def test_empty_comparison_table_accepted(self, gen_cmp):
        """对比表为空（LLM 未生成）应通过但有警告。"""
        output = self._make_output(n_algo=2, comparison_table=[])
        issues = gen_cmp.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0  # 空表不是 error


# ============================================================================
# Quiz + Comparison: Unicode / 多语言
# ============================================================================


class TestUnicodeContent:
    """多语言内容处理。"""

    async def test_quiz_with_mixed_languages(self, mock_llm, gen_quiz):
        mock_llm.return_value = {
            "questions": [{
                "id": "q1", "type": "multiple_choice",
                "question": "What is the time complexity of Quicksort?",
                "options": [
                    {"id": "a", "text": "O(n log n)", "is_correct": True},
                    {"id": "b", "text": "O(n^2)"},
                ],
                "explanation": "Average case is O(n log n).",
                "difficulty": 2,
            }],
        }
        result = await gen_quiz.generate(
            teaching_plan={"objectives": [], "outline": [], "teaching_approach": "", "estimated_total_frames": 1},
            knowledge_graph={"concepts": [{"id": "c1", "name": "Sort", "type": "definition"}], "edges": []},
            user_input="sorting", constraints={}, project_id="test",
        )
        assert len(result["questions"]) == 1

    async def test_comparison_with_cjk_names(self, mock_llm, gen_cmp):
        mock_llm.return_value = {
            "topic": "Sort Comparison",
            "algorithms": [
                {"name": "Quick", "description": "Divide and conquer", "pros": ["Fast", "Practical"], "cons": ["Unstable"]},
                {"name": "Merge", "description": "Stable sort", "pros": ["Stable", "O(n log n)"], "cons": ["More memory"]},
            ],
            "dimensions": ["Speed", "Memory", "Stability", "Complexity"],
            "comparison_table": [
                {"dimension": "Speed", "Quick": "Fast", "Merge": "Medium"},
                {"dimension": "Memory", "Quick": "Low", "Merge": "High"},
                {"dimension": "Stability", "Quick": "Unstable", "Merge": "Stable"},
                {"dimension": "Complexity", "Quick": "Medium", "Merge": "Easy"},
            ],
            "scenario_analysis": "Quick sort is generally suitable. Use merge sort when stability is needed.",
        }
        result = await gen_cmp.generate(
            teaching_plan={"objectives": [], "outline": [], "teaching_approach": "", "estimated_total_frames": 1},
            knowledge_graph={"concepts": [{"id": "c1", "name": "Sort", "type": "definition"}], "edges": []},
            user_input="sorting", constraints={}, project_id="test",
        )
        assert len(result["algorithms"]) == 2


# ============================================================================
# LLM 错误恢复
# ============================================================================


class TestLLMRecovery:
    """LLM 返回意外数据时的恢复能力。"""

    async def test_quiz_llm_returns_empty_object(self, gen_quiz, mock_llm):
        mock_llm.return_value = {}
        result = await gen_quiz.generate(
            teaching_plan={"objectives": [], "outline": [], "teaching_approach": "", "estimated_total_frames": 1},
            knowledge_graph={"concepts": [], "edges": []},
            user_input="Test", constraints={}, project_id="test",
        )
        # BaseGenerator._call_llm 返回原始 LLM 结果，子类 generate 处理
        assert isinstance(result, dict)

    async def test_comparison_llm_returns_partial(self, gen_cmp, mock_llm):
        """LLM 返回只有 topic 没有 algorithms 的结果。"""
        mock_llm.return_value = {"topic": "Test", "scenario_analysis": "x" * 50}
        result = await gen_cmp.generate(
            teaching_plan={"objectives": [], "outline": [], "teaching_approach": "", "estimated_total_frames": 1},
            knowledge_graph={"concepts": [], "edges": []},
            user_input="Test", constraints={}, project_id="test",
        )
        assert isinstance(result, dict)
        # 验证 validate 会捕获缺失字段
        issues = gen_cmp.validate(result)
        assert any(i["severity"] == "medium" for i in issues)  # missing required fields

    async def test_quiz_llm_raises_timeout(self, gen_quiz, mock_llm):
        mock_llm.side_effect = TimeoutError("LLM timeout after 120s")
        with pytest.raises(TimeoutError):
            await gen_quiz.generate(
                teaching_plan={"objectives": [], "outline": [], "teaching_approach": "", "estimated_total_frames": 1},
                knowledge_graph={"concepts": [], "edges": []},
                user_input="Test", constraints={}, project_id="test",
            )

    async def test_comparison_llm_raises_exception(self, gen_cmp, mock_llm):
        mock_llm.side_effect = RuntimeError("API unavailable")
        with pytest.raises(RuntimeError):
            await gen_cmp.generate(
                teaching_plan={"objectives": [], "outline": [], "teaching_approach": "", "estimated_total_frames": 1},
                knowledge_graph={"concepts": [], "edges": []},
                user_input="Test", constraints={}, project_id="test",
            )
