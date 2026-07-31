"""BaseGenerator — 模块生成器抽象基类。

提供共享的 LLM 调用、结果校验和错误处理逻辑。
所有具体模块生成器继承此类，只需覆写 system_prompt 和 output_schema。
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseGenerator(ABC):
    """模块生成器抽象基类。

    子类必须覆写:
      - module_id, display_name, description, icon, category, priority
      - output_schema
      - get_system_prompt()

    可选覆写:
      - validate() — 默认用 output_schema 做 JSON Schema 校验
      - generate() — 默认调用 _call_llm()  + validate()
    """

    # ── 元信息（子类覆写）─────────────────────────────────────

    module_id: str = ""
    display_name: str = ""
    description: str = ""
    icon: str = ""
    category: str = "visual"
    priority: int = 5
    version: str = "1.0.0"

    # ── LLM 生成参数（子类可覆写）─────────────────────────────

    temperature: float = 0.3
    max_tokens: int = 8192

    @property
    @abstractmethod
    def output_schema(self) -> dict[str, Any]:
        """返回 JSON Schema 用于 LLM structured output。"""
        ...

    @abstractmethod
    def get_system_prompt(self) -> str:
        """返回该模块的 LLM 系统提示词。"""
        ...

    # ── 核心方法 ──────────────────────────────────────────────

    async def generate(
        self,
        teaching_plan: dict[str, Any],
        knowledge_graph: dict[str, Any],
        user_input: str,
        constraints: dict[str, Any],
        project_id: str,
        existing_outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """默认生成实现：调用 LLM 并校验结果。

        子类可覆写以添加预处理/后处理逻辑。
        """
        context = self._build_context(
            teaching_plan=teaching_plan,
            knowledge_graph=knowledge_graph,
            user_input=user_input,
            constraints=constraints,
        )
        result = await self._call_llm(context)
        return result

    def get_output_schema(self) -> dict[str, Any]:
        """返回 output_schema（供协议兼容）。"""
        return self.output_schema

    def validate(self, output: dict[str, Any]) -> list[dict[str, Any]]:
        """默认校验：检查 output 是否包含预期顶层键。

        子类应覆写以添加模块特定校验。
        """
        issues: list[dict[str, Any]] = []

        if not isinstance(output, dict):
            return [{"severity": "high", "type": "schema_error",
                     "description": f"Expected dict, got {type(output).__name__}"}]

        # 检查 output_schema 中 required 字段是否存在
        schema = self.output_schema
        if "required" in schema:
            for key in schema["required"]:
                if key not in output:
                    issues.append({
                        "severity": "medium",
                        "type": "missing_field",
                        "description": f"Missing required field: {key}",
                    })
                elif output[key] is None:
                    issues.append({
                        "severity": "low",
                        "type": "null_field",
                        "description": f"Required field is null: {key}",
                    })

        return issues

    # ── 内部方法 ──────────────────────────────────────────────

    def _build_context(
        self,
        teaching_plan: dict[str, Any],
        knowledge_graph: dict[str, Any],
        user_input: str,
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """构建发送给 LLM 的上下文消息（JSON 格式）。

        子类可覆写以调整上下文结构。
        """
        return {
            "topic": user_input,
            "teaching_plan": teaching_plan,
            "knowledge_graph": knowledge_graph,
            "constraints": constraints,
        }

    async def _call_llm(self, context: dict[str, Any]) -> dict[str, Any]:
        """调用 LLM 生成结构化结果。

        延迟导入 call_llm_structured 避免循环依赖。
        """
        from agents.llm_client import call_llm_structured

        user_message = json.dumps(context, ensure_ascii=False, indent=2)

        try:
            result = await call_llm_structured(
                system_prompt=self.get_system_prompt(),
                user_message=user_message,
                output_schema=self.output_schema,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return result
        except Exception as exc:
            logger.error("Module '%s' LLM 调用失败: %s", self.module_id, exc)
            raise

    def _sse_event(self, phase: str, data: dict[str, Any]) -> dict[str, Any]:
        """构建 SSE 事件字典（模块级进度）。"""
        data["module_id"] = self.module_id
        return {"event": phase, "data": data}
