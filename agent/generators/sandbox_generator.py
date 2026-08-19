"""Code Sandbox Generator — 代码实操沙箱生成器。

生成可运行的多语言算法代码 + 测试用例 + 可调节参数。
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseGenerator
from .registry import register_generator

logger = logging.getLogger(__name__)

SANDBOX_SYSTEM_PROMPT = """你是一位编程教学专家，擅长编写清晰、可运行、带测试的算法代码。

## 你的任务

根据教学主题和知识图谱，生成一份可供学生实操的代码沙箱配置：
包含完整的算法实现、测试用例和可调节参数。

## 输出格式

```json
{
  "language": "python",
  "starter_code": "def dijkstra(graph, start):\\n    ...\\n    return distances\\n\\n# 测试运行\\nif __name__ == '__main__':\\n    print(dijkstra(test_graph, 'A'))",
  "full_solution": "完整可运行的实现代码",
  "test_cases": [
    {
      "name": "基本功能测试",
      "input": {"graph": {"A": {"B": 1}}, "start": "A"},
      "expected_output": {"distances": {"A": 0, "B": 1}},
      "description": "单边图的最短路径"
    }
  ],
  "editable_params": [
    {"key": "graph_data", "label": "图数据", "type": "graph", "default": {...}, "description": "修改图的节点和边"},
    {"key": "start_node", "label": "起始节点", "type": "string", "default": "A", "description": "算法执行的起点"}
  ],
  "learning_notes": "这段代码实现了 Dijkstra 最短路径算法...",
  "time_complexity": "O((V+E) log V)",
  "space_complexity": "O(V)"
}
```

## 约束

- language 支持: python, javascript, java, cpp
- starter_code 包含函数签名和基本框架，留 TODO 让学生填写
- full_solution 是完整正确实现
- test_cases 至少 3 个，覆盖边界情况
- editable_params 至少 2 个可调参数
"""

SANDBOX_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "language": {"type": "string", "enum": ["python", "javascript", "java", "cpp"]},
        "starter_code": {"type": "string"},
        "full_solution": {"type": "string"},
        "test_cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}, "input": {"type": "object"},
                    "expected_output": {"type": "object"}, "description": {"type": "string"},
                },
                "required": ["name", "input", "expected_output"],
            },
        },
        "editable_params": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"}, "label": {"type": "string"},
                    "type": {"type": "string"}, "default": {},
                    "description": {"type": "string"},
                },
            },
        },
        "learning_notes": {"type": "string"},
        "time_complexity": {"type": "string"},
        "space_complexity": {"type": "string"},
    },
    "required": ["language", "starter_code", "full_solution", "test_cases"],
}


class SandboxGenerator(BaseGenerator):
    module_id = "sandbox"
    display_name = "代码沙箱"
    description = "生成可运行的算法代码、测试用例和可调节参数，支持实操练习"
    icon = "sandbox"
    category = "interactive"
    priority = 9
    version = "1.0.0"
    temperature = 0.2
    max_tokens = 16384

    @property
    def output_schema(self) -> dict[str, Any]:
        return SANDBOX_OUTPUT_SCHEMA

    def get_system_prompt(self) -> str:
        return SANDBOX_SYSTEM_PROMPT

    def _build_context(self, teaching_plan, knowledge_graph, user_input, constraints):
        return {
            "topic": user_input,
            "concepts": [c.get("name") for c in knowledge_graph.get("concepts", [])],
            "objectives": teaching_plan.get("objectives", []),
            "approach": teaching_plan.get("teaching_approach", ""),
        }

    def validate(self, output):
        issues = super().validate(output)
        if any(i["severity"] == "high" and i["type"] == "schema_error" for i in issues):
            return issues
        tests = output.get("test_cases", [])
        if isinstance(tests, list) and len(tests) < 2:
            issues.append({"severity": "medium", "type": "too_few_tests", "description": f"test_cases 至少 2 个，当前 {len(tests)}"})
        starter = output.get("starter_code", "")
        if len(starter) < 20:
            issues.append({"severity": "medium", "type": "short_starter", "description": "starter_code 过短"})
        solution = output.get("full_solution", "")
        if len(solution) < 50:
            issues.append({"severity": "medium", "type": "short_solution", "description": "full_solution 过短"})
        return issues


register_generator(SandboxGenerator())
logger.info("SandboxGenerator 已注册 (module_id=sandbox)")
