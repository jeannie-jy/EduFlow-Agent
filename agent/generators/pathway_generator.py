"""Learning Pathway Generator — 学习路径生成器。

生成结构化学习路线图：前置知识 → 当前主题 → 进阶延伸 → 相关领域。
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseGenerator
from .registry import register_generator

logger = logging.getLogger(__name__)

PATHWAY_SYSTEM_PROMPT = """你是一位计算机科学课程设计专家，擅长规划知识学习路径。

## 你的任务

根据教学主题和知识图谱，生成一条完整的学习路径图，
包含：前置知识、当前主题、进阶延伸和相关领域。

## 节点类型

- **prerequisite**：学习当前主题前必须掌握的知识（2-4个）
- **core**：当前主题本身及核心子主题（1-3个）
- **extension**：学完后可以进一步探索的进阶主题（2-3个）
- **related**：相关但不直接依赖的平行领域（1-2个）
- **application**：该知识在工程实践中的典型应用（1-2个）

## 输出格式

```json
{
  "current_topic": "Dijkstra 最短路径算法",
  "nodes": [
    {"id": "n1", "name": "图的邻接表表示", "type": "prerequisite", "description": "理解图如何存储和遍历", "difficulty": 1},
    {"id": "n2", "name": "贪心算法思想", "type": "prerequisite", "description": "理解局部最优选择策略", "difficulty": 2},
    {"id": "n3", "name": "Dijkstra 算法", "type": "core", "description": "本次学习目标", "difficulty": 2},
    {"id": "n4", "name": "Bellman-Ford 算法", "type": "extension", "description": "支持负权边的最短路径", "difficulty": 3},
    {"id": "n5", "name": "A* 搜索算法", "type": "extension", "description": "启发式最短路径搜索", "difficulty": 3},
    {"id": "n6", "name": "最小生成树 (Prim/Kruskal)", "type": "related", "description": "图论中另一个核心主题", "difficulty": 2},
    {"id": "n7", "name": "网络路由协议 OSPF", "type": "application", "description": "Dijkstra 在 Internet 中的应用", "difficulty": 3}
  ],
  "edges": [
    {"source": "n1", "target": "n3", "relation": "depends_on"},
    {"source": "n2", "target": "n3", "relation": "depends_on"},
    {"source": "n3", "target": "n4", "relation": "extends"},
    {"source": "n3", "target": "n5", "relation": "extends"},
    {"source": "n3", "target": "n6", "relation": "related_to"},
    {"source": "n3", "target": "n7", "relation": "applied_in"}
  ],
  "estimated_hours": 3,
  "learning_tips": ["建议先手写几次图的邻接表", "用不同尺寸的图做练习", "注意对比 BFS 和 Dijkstra 的区别"]
}
```

## 约束

- 总节点 6-12 个
- 至少 2 个 prerequisite
- 至少 2 个 extension
- edges 中每个 source/target 必须引用 nodes 中的 id
- estimated_hours 为估算学习时间（小时）
"""

PATHWAY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "current_topic": {"type": "string"},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"}, "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["prerequisite", "core", "extension", "related", "application"]},
                    "description": {"type": "string"}, "difficulty": {"type": "integer", "minimum": 1, "maximum": 3},
                },
                "required": ["id", "name", "type", "description"],
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"source": {"type": "string"}, "target": {"type": "string"}, "relation": {"type": "string"}},
                "required": ["source", "target", "relation"],
            },
        },
        "estimated_hours": {"type": "integer"},
        "learning_tips": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["current_topic", "nodes", "edges"],
}


class PathwayGenerator(BaseGenerator):
    module_id = "pathway"
    display_name = "学习路径"
    description = "生成结构化学习路线图，展示前置知识→当前主题→进阶延伸"
    icon = "pathway"
    category = "visual"
    priority = 8
    version = "1.0.0"
    temperature = 0.3
    max_tokens = 4096

    @property
    def output_schema(self) -> dict[str, Any]:
        return PATHWAY_OUTPUT_SCHEMA

    def get_system_prompt(self) -> str:
        return PATHWAY_SYSTEM_PROMPT

    def _build_context(self, teaching_plan, knowledge_graph, user_input, constraints):
        concepts = knowledge_graph.get("concepts", [])
        return {
            "topic": user_input,
            "concepts": [c.get("name") for c in concepts],
            "objectives": teaching_plan.get("objectives", []),
            "prerequisites": teaching_plan.get("prerequisites", []),
        }

    def validate(self, output):
        issues = super().validate(output)
        if any(i["severity"] == "high" and i["type"] == "schema_error" for i in issues):
            return issues
        nodes = output.get("nodes", [])
        if not isinstance(nodes, list) or len(nodes) < 4:
            issues.append({"severity": "high", "type": "too_few_nodes", "description": f"节点至少 4 个，当前 {len(nodes) if isinstance(nodes, list) else 0}"})
            return issues
        node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}
        node_types = [n.get("type") for n in nodes if isinstance(n, dict)]
        if "prerequisite" not in node_types:
            issues.append({"severity": "medium", "type": "no_prereqs", "description": "缺少前置知识节点"})
        if "extension" not in node_types:
            issues.append({"severity": "medium", "type": "no_extensions", "description": "缺少进阶延伸节点"})
        edges = output.get("edges", [])
        if isinstance(edges, list):
            for e in edges:
                if not isinstance(e, dict):
                    continue
                src, tgt = e.get("source"), e.get("target")
                if src and src not in node_ids:
                    issues.append({"severity": "medium", "type": "dangling_edge", "description": f"边 source={src} 不在节点列表中"})
                if tgt and tgt not in node_ids:
                    issues.append({"severity": "medium", "type": "dangling_edge", "description": f"边 target={tgt} 不在节点列表中"})
        return issues


register_generator(PathwayGenerator())
logger.info("PathwayGenerator 已注册 (module_id=pathway)")
