"""LLM 客户端工厂。

统一封装 OpenAI 兼容的 LLM 调用（DeepSeek API）。
支持 function calling 和结构化 JSON 输出。

使用模块级单例避免每次调用创建新客户端（防止连接泄漏）。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)

# ── 模块级单例（避免连接泄漏）────────────────────────────────

_llm_client: AsyncOpenAI | None = None
_embedding_client: AsyncOpenAI | None = None


def _get_llm_client() -> AsyncOpenAI:
    """获取 LLM 客户端单例。"""
    global _llm_client
    if _llm_client is None:
        settings = get_settings()
        _llm_client = AsyncOpenAI(
            base_url=settings.llm_endpoint,
            api_key=settings.llm_api_key,
        )
    return _llm_client


def _get_embedding_client() -> AsyncOpenAI:
    """获取 Embedding 客户端单例。"""
    global _embedding_client
    if _embedding_client is None:
        settings = get_settings()
        _embedding_client = AsyncOpenAI(
            base_url=settings.embedding_endpoint,
            api_key=settings.embedding_api_key,
        )
    return _embedding_client


# ── 向后兼容的别名（弃用）────────────────────────────────────


def create_llm_client() -> AsyncOpenAI:
    """创建 LLM 客户端。已改为单例模式，推荐直接使用 _get_llm_client()。"""
    return _get_llm_client()


def create_embedding_client() -> AsyncOpenAI:
    """创建 Embedding 客户端。已改为单例模式。"""
    return _get_embedding_client()


# ── LLM 调用工具 ────────────────────────────────────────────


async def call_llm(
    system_prompt: str,
    user_message: str,
    *,
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    model: str | None = None,
) -> dict[str, Any]:
    """通用 LLM 调用封装。

    Returns:
        {
            "content": str | None,
            "tool_calls": list[dict],
            "usage": {"input": int, "output": int},
        }
    """
    settings = get_settings()
    client = _get_llm_client()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    kwargs: dict[str, Any] = dict(
        model=model or settings.llm_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = await client.chat.completions.create(**kwargs)

    if not response.choices:
        logger.warning("LLM returned empty choices")
        return {"content": None, "tool_calls": [], "usage": {"input": 0, "output": 0}}

    choice = response.choices[0]
    tool_calls = []

    if choice.message.tool_calls:
        for tc in choice.message.tool_calls:
            try:
                arguments = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, AttributeError):
                arguments = {"raw": tc.function.arguments}
            tool_calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "arguments": arguments,
            })

    return {
        "content": choice.message.content,
        "tool_calls": tool_calls,
        "usage": {
            "input": response.usage.prompt_tokens if response.usage else 0,
            "output": response.usage.completion_tokens if response.usage else 0,
        },
    }


async def call_llm_structured(
    system_prompt: str,
    user_message: str,
    *,
    output_schema: dict[str, Any],
    temperature: float = 0.2,
    max_tokens: int = 8192,
    model: str | None = None,
) -> dict[str, Any]:
    """调用 LLM 并以结构化 JSON 格式输出。

    通过 function calling 的严格模式确保输出符合 schema。
    """
    settings = get_settings()
    client = _get_llm_client()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    tools = [{
        "type": "function",
        "function": {
            "name": "output_structured_result",
            "description": "以 JSON 格式输出结构化结果",
            "parameters": output_schema,
        },
    }]

    response = await client.chat.completions.create(
        model=model or settings.llm_model,
        messages=messages,
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "output_structured_result"}},
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # 保护：检查 choices 非空
    if not response.choices:
        logger.error("Structured LLM call returned empty choices")
        raise RuntimeError("LLM returned empty response (no choices)")

    choice = response.choices[0]
    message = choice.message

    # 保护：检查 tool_calls 非空
    if not message.tool_calls:
        logger.error(
            "Structured LLM call has no tool_calls. content=%s",
            str(message.content)[:200],
        )
        raise RuntimeError("LLM returned no tool_calls — likely content filter or API error")

    try:
        result = json.loads(message.tool_calls[0].function.arguments)
    except (json.JSONDecodeError, AttributeError, IndexError) as exc:
        logger.error("Failed to parse structured output: %s", exc)
        raise RuntimeError(f"Failed to parse structured LLM output: {exc}") from exc

    # Token 使用追踪
    if response.usage:
        logger.info(
            "LLM token usage | prompt=%d | completion=%d | total=%d",
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
        )

    return result


async def generate_embedding(text: str) -> list[float]:
    """生成文本的向量嵌入。"""
    client = _get_embedding_client()

    response = await client.embeddings.create(
        model=get_settings().embedding_model,
        input=text,
    )

    if not response.data:
        raise RuntimeError("Embedding API returned empty data")

    return response.data[0].embedding
