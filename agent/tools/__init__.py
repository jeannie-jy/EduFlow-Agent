"""Tool 层：Agent 可调用的工具函数。

每个 Tool 遵循统一接口（ToolDef），预留 MCP 兼容性。
对齐设计文档第 4 节。
"""

from .registry import ToolDef, ToolRegistry, get_registry

__all__ = ["ToolDef", "ToolRegistry", "get_registry"]
