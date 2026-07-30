"""Quiz Generator — 小练习生成器。

根据 teaching_plan + knowledge_graph 自动生成练习题：
选择题（单选/多选）、填空题、判断题、简答题。
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseGenerator
from .registry import register_generator

logger = logging.getLogger(__name__)


QUIZ_SYSTEM_PROMPT = """你是一位教学测评专家，擅长设计高质量的练习题来检验学习效果。

## 你的任务

根据教学计划和知识图谱，生成一组覆盖核心概念的练习题。

## 题目类型

1. **multiple_choice**（选择题）
   - 题干清晰，问题指向明确
   - 4 个选项（id: a/b/c/d），标注正确答案（is_correct: true）
   - 错误选项应有迷惑性（常见误区）
   - explanation 解释为什么正确答案是对的、错误选项为什么不对

2. **true_false**（判断题）
   - 提供一个陈述，判断正误
   - correct_answer: "true" 或 "false"
   - explanation 解释判断依据

3. **fill_blank**（填空题）
   - 题干中用 ___ 标记空白处
   - correct_answer 填写正确答案
   - 答案可能有多种合理写法，用 / 分隔

4. **short_answer**（简答题）
   - 开放性问题，考察理解和表达能力
   - expected_keywords 列出答案应包含的关键词
   - 不自动判分，供教师参考

## 出题原则

1. **覆盖核心概念**：每个 core_mechanism 类型的概念至少 1 题
2. **难度递进**：difficulty 1=记忆理解, 2=应用分析, 3=综合评估
3. **考察理解而非记忆**：避免"XX 的全称是什么"这类纯记忆题
4. **错误选项有教学价值**：每个错误选项对应一个常见误区
5. **解释详尽**：explanation 不仅说答案，还要说为什么

## 输出格式

```json
{
  "questions": [
    {
      "id": "q1",
      "type": "multiple_choice",
      "question": "Dijkstra 算法不能处理以下哪种情况？",
      "options": [
        {"id": "a", "text": "有向图"},
        {"id": "b", "text": "负权边", "is_correct": true},
        {"id": "c", "text": "无权图"},
        {"id": "d", "text": "带环图"}
      ],
      "explanation": "Dijkstra 的贪心策略基于「当前已知最短路径不会再被更新」的假设，负权边会破坏这个假设。有向图、无权图、带环图都可以用 Dijkstra 处理。",
      "related_concept": "c2",
      "difficulty": 1
    },
    {
      "id": "q2",
      "type": "true_false",
      "question": "Dijkstra 算法使用动态规划思想。",
      "correct_answer": "false",
      "explanation": "Dijkstra 使用的是贪心策略，每次选择当前距离最短的未处理节点。动态规划需要最优子结构和重叠子问题，Dijkstra 不具备后者。",
      "related_concept": "c1",
      "difficulty": 2
    },
    {
      "id": "q3",
      "type": "fill_blank",
      "question": "Dijkstra 算法中，每次从优先队列中取出距离 ___ 的节点进行处理。",
      "correct_answer": "最小/最短/最小距离",
      "explanation": "Dijkstra 的核心操作是每次选出当前已知距离最小的未访问节点，这是贪心策略的关键步骤。",
      "related_concept": "c2",
      "difficulty": 1
    }
  ],
  "metadata": {
    "total": 5,
    "by_type": {"multiple_choice": 3, "true_false": 1, "fill_blank": 1},
    "by_difficulty": {"1": 2, "2": 2, "3": 1},
    "concepts_covered": ["c1", "c2", "c3"]
  }
}
```

## 约束

- 至少 3 题，最多 10 题
- 选择题至少 1 题，作为入门检查
- 每题必须有 explanation
- 每题的 related_concept 必须引用 knowledge_graph 中已有的 concept id
- difficulty 取值 1-3
"""


QUIZ_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": ["multiple_choice", "true_false", "fill_blank", "short_answer"]},
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "text": {"type": "string"},
                                "is_correct": {"type": "boolean"},
                            },
                        },
                    },
                    "correct_answer": {"type": "string"},
                    "explanation": {"type": "string"},
                    "expected_keywords": {"type": "array", "items": {"type": "string"}},
                    "related_concept": {"type": "string"},
                    "difficulty": {"type": "integer", "minimum": 1, "maximum": 3},
                },
                "required": ["id", "type", "question", "explanation", "difficulty"],
            },
        },
        "metadata": {
            "type": "object",
            "properties": {
                "total": {"type": "integer"},
                "by_type": {"type": "object"},
                "by_difficulty": {"type": "object"},
                "concepts_covered": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "required": ["questions"],
}


class QuizGenerator(BaseGenerator):
    """小练习生成器。

    根据教学计划和知识图谱生成自动判分的练习题。
    """

    module_id = "quiz"
    display_name = "小练习"
    description = "自动生成选择题、判断题、填空题和简答题，检验学生对知识点的理解"
    icon = "quiz"
    category = "interactive"
    priority = 4
    version = "1.0.0"

    temperature = 0.3
    max_tokens = 8192

    @property
    def output_schema(self) -> dict[str, Any]:
        return QUIZ_OUTPUT_SCHEMA

    def get_system_prompt(self) -> str:
        return QUIZ_SYSTEM_PROMPT

    def _build_context(
        self,
        teaching_plan: dict[str, Any],
        knowledge_graph: dict[str, Any],
        user_input: str,
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        concepts = knowledge_graph.get("concepts", [])
        simple_concepts = [
            {
                "id": c.get("id", ""),
                "name": c.get("name", ""),
                "type": c.get("type", "definition"),
                "description": c.get("description", ""),
                "pitfalls": c.get("common_pitfalls", []),
            }
            for c in concepts
        ]

        return {
            "topic": user_input,
            "objectives": teaching_plan.get("objectives", []),
            "concepts": simple_concepts,
            "outline_titles": [
                s.get("title", "") for s in teaching_plan.get("outline", [])
            ],
        }

    def validate(self, output: dict[str, Any]) -> list[dict[str, Any]]:
        issues = super().validate(output)
        if any(i["severity"] == "high" and i["type"] == "schema_error" for i in issues):
            return issues

        questions = output.get("questions", [])
        if not isinstance(questions, list):
            issues.append({"severity": "high", "type": "invalid_questions",
                           "description": f"questions 应为列表，实际为 {type(questions).__name__}"})
            return issues
        if len(questions) == 0:
            issues.append({"severity": "high", "type": "empty_quiz", "description": "未生成任何练习题"})
            return issues

        if len(questions) > 15:
            issues.append({"severity": "warn", "type": "too_many_questions",
                           "description": f"题目过多 ({len(questions)} 题)，建议 3-10 题"})

        has_mc = False
        for i, q in enumerate(questions):
            if not isinstance(q, dict):
                issues.append({"severity": "high", "type": "invalid_question_object",
                               "description": f"Question at index {i} is not a dict: {type(q).__name__}"})
                continue
            qid = q.get("id", f"q_{i}")
            qtype = q.get("type", "")

            if qtype == "multiple_choice":
                has_mc = True
                options = q.get("options", [])
                if not isinstance(options, list):
                    issues.append({"severity": "medium", "type": "invalid_options",
                                   "description": f"选择题 {qid} 的 options 不是列表"})
                    continue
                correct_opts = [o for o in options if isinstance(o, dict) and o.get("is_correct")]
                if len(options) < 2:
                    issues.append({"severity": "medium", "type": "too_few_options",
                                   "description": f"选择题 {qid} 选项不足 ({len(options)} 个)"})
                if len(correct_opts) == 0:
                    issues.append({"severity": "high", "type": "no_correct_answer",
                                   "description": f"选择题 {qid} 没有正确答案"})

            if not q.get("explanation"):
                issues.append({"severity": "medium", "type": "missing_explanation",
                               "description": f"题目 {qid} 缺少解答说明"})

            difficulty = q.get("difficulty", 0)
            if not (1 <= difficulty <= 3):
                issues.append({"severity": "warn", "type": "invalid_difficulty",
                               "description": f"题目 {qid} difficulty={difficulty} 应在 1-3 之间"})

        if not has_mc:
            issues.append({"severity": "warn", "type": "no_multiple_choice",
                           "description": "建议至少包含 1 道选择题作为入门检查"})

        return issues


register_generator(QuizGenerator())
logger.info("QuizGenerator 已注册 (module_id=quiz)")
