"""Algorithm Comparison Generator — 算法对比生成器。

对同一问题域的 2-3 种算法进行多维度对比分析，
生成并排对比表和场景推荐。
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseGenerator
from .registry import register_generator

logger = logging.getLogger(__name__)


COMPARISON_SYSTEM_PROMPT = """你是一位算法分析专家，擅长对同类算法进行多维度对比分析。

## 你的任务

根据教学主题和知识图谱，识别该问题域中的 2-3 种典型算法，
从多个维度进行对比分析，帮助学生理解各算法的适用场景和取舍。

## 对比维度

1. **时间复杂度**：最好/平均/最坏情况
2. **空间复杂度**：内存使用
3. **适用图/数据类型**：稠密图、稀疏图、有向无向、负权等
4. **实现复杂度**：简单/中等/复杂
5. **稳定性**：是否保持相等元素的相对顺序
6. **是否原地算法**：是否需要额外数据结构
7. **核心数据结构**：优先队列、堆、数组等
8. **典型应用场景**：实际工程中的使用

## 输出格式

```json
{
  "topic": "最短路径算法对比",
  "algorithms": [
    {
      "name": "Dijkstra",
      "description": "贪心策略，每次取距离最小的未访问节点",
      "pros": ["简单高效", "适合正权图", "结果可解释"],
      "cons": ["无法处理负权边", "每次选择开销大"]
    },
    {
      "name": "Bellman-Ford",
      "description": "对所有边进行 V-1 轮松弛操作",
      "pros": ["能处理负权边", "能检测负环", "实现简单"],
      "cons": ["时间复杂度高 O(VE)", "不适合大规模图"]
    },
    {
      "name": "A*",
      "description": "启发式搜索，f(n)=g(n)+h(n) 指导搜索方向",
      "pros": ["效率高", "可用于路径规划", "灵活可调的启发函数"],
      "cons": ["需要设计好的启发函数", "不保证最短路径（启发函数不一致时）"]
    }
  ],
  "dimensions": [
    "时间复杂度",
    "空间复杂度",
    "图类型要求",
    "实现复杂度",
    "适用场景"
  ],
  "comparison_table": [
    {
      "dimension": "时间复杂度",
      "Dijkstra": "O((V+E) log V) 用堆",
      "Bellman-Ford": "O(VE)",
      "A*": "O(E) ~ O(b^d)"
    },
    {
      "dimension": "图类型要求",
      "Dijkstra": "正权有向/无向图",
      "Bellman-Ford": "任意权值（含负权），不可有负环",
      "A*": "正权图（通常）"
    },
    {
      "dimension": "实现复杂度",
      "Dijkstra": "中等（需要优先队列）",
      "Bellman-Ford": "简单（双层循环）",
      "A*": "复杂（需要设计启发函数）"
    },
    {
      "dimension": "适用场景",
      "Dijkstra": "地图导航、网络路由（OSPF）",
      "Bellman-Ford": "距离向量路由（RIP）、负权检测",
      "A*": "游戏 AI 寻路、机器人路径规划"
    }
  ],
  "scenario_analysis": "对于没有负权边的通用最短路径问题，Dijkstra 是最佳选择，时间复杂度优秀且实现成熟。如果需要检测负权边或负环（如金融套利检测），Bellman-Ford 是唯一选择。A* 在有明确目标点的搜索中效率最高，但需要设计合理的启发函数。在实际工程中，Dijkstra 和 A* 更为常用。"
}
```

## 约束

- 对比 2-3 个有代表性的算法
- 至少 4 个对比维度
- comparison_table 每个维度必须覆盖所有算法
- 每个算法的 pros/cons 各至少 2 条
- scenario_analysis 给出具体、可操作的选型建议
- 如果 knowledge_graph 中概念少于 2 个，可以基于 topic 自行补充算法
"""


COMPARISON_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "algorithms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "pros": {"type": "array", "items": {"type": "string"}},
                    "cons": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "description", "pros", "cons"],
            },
        },
        "dimensions": {"type": "array", "items": {"type": "string"}},
        "comparison_table": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "dimension": {"type": "string"},
                },
                "required": ["dimension"],
                "additionalProperties": {"type": "string"},
            },
        },
        "scenario_analysis": {"type": "string"},
    },
    "required": ["topic", "algorithms", "dimensions", "comparison_table", "scenario_analysis"],
}


class ComparisonGenerator(BaseGenerator):
    """算法对比生成器。

    对同一问题域的算法进行多维度对比分析。
    """

    module_id = "comparison"
    display_name = "算法对比"
    description = "对同类算法进行多维度对比分析，生成并排对比表和场景推荐"
    icon = "comparison"
    category = "visual"
    priority = 6
    version = "1.0.0"

    temperature = 0.2
    max_tokens = 8192

    @property
    def output_schema(self) -> dict[str, Any]:
        return COMPARISON_OUTPUT_SCHEMA

    def get_system_prompt(self) -> str:
        return COMPARISON_SYSTEM_PROMPT

    def _build_context(
        self,
        teaching_plan: dict[str, Any],
        knowledge_graph: dict[str, Any],
        user_input: str,
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        concepts = knowledge_graph.get("concepts", [])
        concept_names = [c.get("name", "") for c in concepts]

        return {
            "topic": user_input,
            "objectives": teaching_plan.get("objectives", []),
            "concepts": concept_names,
            "approach": teaching_plan.get("teaching_approach", ""),
        }

    def validate(self, output: dict[str, Any]) -> list[dict[str, Any]]:
        issues = super().validate(output)
        if any(i["severity"] == "high" and i["type"] == "schema_error" for i in issues):
            return issues

        algorithms = output.get("algorithms", [])
        if len(algorithms) < 2:
            issues.append({"severity": "high", "type": "too_few_algorithms",
                           "description": f"需要至少 2 个算法进行对比，当前 {len(algorithms)} 个"})
        if len(algorithms) > 5:
            issues.append({"severity": "low", "type": "too_many_algorithms",
                           "description": f"对比算法过多 ({len(algorithms)} 个)，建议 2-3 个"})

        for i, algo in enumerate(algorithms):
            if not isinstance(algo, dict):
                issues.append({
                    "severity": "high",
                    "type": "invalid_algo_object",
                    "description": f"Algorithm at index {i} is not a dict: {type(algo).__name__}",
                })
                continue
            name = algo.get("name", f"algo_{i}")
            pros = algo.get("pros", [])
            cons = algo.get("cons", [])
            if len(pros) < 2:
                issues.append({"severity": "low", "type": "few_pros",
                               "description": f"算法 {name} 的优点不足 ({len(pros)} 条)"})
            if len(cons) < 1:
                issues.append({"severity": "low", "type": "no_cons",
                               "description": f"算法 {name} 没有列出缺点，缺乏客观性"})
            if not algo.get("description"):
                issues.append({"severity": "medium", "type": "missing_description",
                               "description": f"算法 {name} 缺少描述"})

        dimensions = output.get("dimensions", [])
        if len(dimensions) < 4:
            issues.append({"severity": "medium", "type": "too_few_dimensions",
                           "description": f"对比维度不足 ({len(dimensions)} 个)，建议至少 4 个"})

        table = output.get("comparison_table", [])
        if not isinstance(table, list):
            issues.append({"severity": "high", "type": "invalid_table",
                           "description": f"comparison_table 应为列表，实际为 {type(table).__name__}"})
            return issues
        algo_names = {a.get("name", f"algo_{i}") for i, a in enumerate(algorithms) if isinstance(a, dict)}
        for row in table:
            if not isinstance(row, dict):
                continue
            for name in algo_names:
                if name not in row:
                    issues.append({"severity": "medium", "type": "missing_algo_in_row",
                                   "description": f"维度 '{row.get('dimension', '?')}' 缺少算法 {name} 的数据"})

        scenario = output.get("scenario_analysis", "")
        if len(scenario) < 30:
            issues.append({"severity": "low", "type": "short_analysis",
                           "description": "场景分析过短，建议给出具体的选型建议"})

        return issues


register_generator(ComparisonGenerator())
logger.info("ComparisonGenerator 已注册 (module_id=comparison)")
