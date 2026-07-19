"""Tool 注册中心。

提供统一的 Tool 注册、查找和执行机制。
每个 Tool 的接口定义与 MCP Tool 规范对齐。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolDef(BaseModel):
    """Tool 定义 — 接口与 MCP Tool 规范对齐。"""
    name: str
    description: str
    parameters: dict[str, Any]          # JSON Schema
    returns: dict[str, Any]             # 返回值 JSON Schema
    errors: list[str] = Field(default_factory=list)
    retryable: bool = True
    timeout_ms: int = 30_000

    # 运行时绑定
    func: Callable | None = Field(default=None, exclude=True)


class ToolRegistry:
    """Tool 注册中心。

    用法:
        registry = ToolRegistry()
        registry.register(my_tool_def, my_func)
        result = await registry.call("my_tool", **kwargs)
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool_def: ToolDef, func: Callable) -> None:
        """注册一个 Tool。"""
        tool_def.func = func
        self._tools[tool_def.name] = tool_def
        logger.info("Tool registered: %s", tool_def.name)

    def get(self, name: str) -> ToolDef | None:
        """按名称获取 Tool 定义。"""
        return self._tools.get(name)

    def list_defs(self) -> list[ToolDef]:
        """获取所有已注册 Tool 定义（不含函数引用，可序列化）。"""
        return [
            ToolDef(
                name=t.name,
                description=t.description,
                parameters=t.parameters,
                returns=t.returns,
                errors=t.errors,
                retryable=t.retryable,
                timeout_ms=t.timeout_ms,
            )
            for t in self._tools.values()
        ]

    def get_tools_for_llm(self) -> list[dict[str, Any]]:
        """生成 LLM function-calling 格式的 tool 列表。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    async def call(self, name: str, **kwargs: Any) -> Any:
        """调用已注册的 Tool。"""
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        if tool.func is None:
            raise RuntimeError(f"Tool '{name}' has no bound function")

        logger.info("Tool call: %s | args=%s", name, kwargs)
        try:
            result = await tool.func(**kwargs)
            return result
        except Exception as exc:
            logger.error("Tool '%s' failed: %s", name, exc)
            if tool.retryable:
                raise
            raise


# 全局注册中心单例
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """获取全局 ToolRegistry 单例。"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
