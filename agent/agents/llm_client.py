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
            parsed = _extract_and_parse_json(tc.function.arguments)
            if parsed is not None:
                arguments = parsed
            else:
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

    使用 function calling，内置截断修复和格式纠错。
    """
    settings = get_settings()
    client = _get_llm_client()

    # 将 schema 注入 user_message，指导 LLM 输出格式
    schema_hint = (
        "\n\n请严格按照以下 JSON Schema 输出结果。"
        "注意：字符串内的双引号必须转义，不允许尾随逗号。\n"
        + json.dumps(output_schema, ensure_ascii=False, indent=2)
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message + schema_hint},
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

    if not response.choices:
        logger.error("Structured LLM call returned empty choices")
        raise RuntimeError("LLM returned empty response (no choices)")

    choice = response.choices[0]
    message = choice.message

    if not message.tool_calls:
        logger.error(
            "Structured LLM call has no tool_calls. content=%s",
            str(message.content)[:200],
        )
        raise RuntimeError("LLM returned no tool_calls — likely content filter or API error")

    raw_args = message.tool_calls[0].function.arguments
    result = _extract_and_parse_json(raw_args)

    # 检测截断：如果 finish_reason=length 或解析失败，用更大 max_tokens 重试一次
    is_truncated = (
        response.choices[0].finish_reason == "length"
        or (result is None and _looks_truncated(raw_args))
    )

    if is_truncated and max_tokens < 65536:
        logger.warning(
            "LLM 输出被截断 (finish_reason=%s)，用 max_tokens=%d 重试",
            response.choices[0].finish_reason, max_tokens * 2,
        )
        try:
            response = await client.chat.completions.create(
                model=model or settings.llm_model,
                messages=messages,
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "output_structured_result"}},
                temperature=temperature,
                max_tokens=max_tokens * 2,
            )
            if response.choices and response.choices[0].message.tool_calls:
                raw_args = response.choices[0].message.tool_calls[0].function.arguments
                result = _extract_and_parse_json(raw_args)
                logger.info("截断重试完成，解析%s", "成功" if result else "仍失败")
        except Exception as exc:
            logger.warning("截断重试失败: %s", exc)

    if result is None:
        logger.error("function calling JSON 解析失败，原始内容: %s", raw_args[:500])
        raise RuntimeError(
            f"Failed to parse structured LLM output: {raw_args[:200]}"
        )

    _log_usage(response)
    return result


def _extract_and_parse_json(text: str) -> dict[str, Any] | None:
    """从 LLM 输出中提取并解析 JSON。

    处理：markdown code block、前后说明文字、尾随逗号、截断括号、截断字符串。
    """
    import re

    if not text or not text.strip():
        return None

    text = text.strip()

    # 1. 提取 markdown code block 内容
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()

    # 2. 找到最外层 { 到 } 的范围（跳过前后说明文字）
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    # 3. 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 4. 截断修复：检测是否在字符串中间被截断
    repaired = _fix_truncated_json(text)
    if repaired != text:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    # 5. 最后手段：修复常见格式问题
    repaired = text
    repaired = re.sub(r",\s*(\}|\])", r"\1", repaired)  # 尾随逗号
    repaired = re.sub(r",\s*,", ",", repaired)           # 连续逗号
    repaired = _fix_truncated_json(repaired)              # 截断修复

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    return None


def _looks_truncated(text: str) -> bool:
    """检测 JSON 是否被截断：末尾不在合理的闭合位置。"""
    text = text.rstrip()
    if not text:
        return True
    # 正常结束应该是 } 或 ]
    if text.endswith("}") or text.endswith("]"):
        return False
    # 以逗号、冒号、引号、字母结尾 → 可能被截断
    if text[-1] in ',:"' or text[-1].isalpha():
        return True
    return False


def _fix_truncated_json(text: str) -> str:
    """修复被 max_tokens 截断的 JSON。

    处理两种情况：
    - 在字符串值中间截断：`"ty` → 闭合引号
    - 在对象/数组中间截断 → 补全括号
    """
    text = text.rstrip()

    # 去掉末尾截断的逗号/冒号
    if text.endswith(","):
        text = text[:-1]
    if text.endswith(":"):
        text = text[:-1]

    # 检测字符串是否未闭合（引号计数）
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string

    # 如果在字符串中间截断，闭合引号
    if in_string:
        text += '"'

    # 补全未闭合的括号（顺序：先数组后对象）
    open_braces = text.count("{") - text.count("}")
    open_brackets = text.count("[") - text.count("]")
    if open_brackets > 0:
        text += "]" * open_brackets
    if open_braces > 0:
        text += "}" * open_braces

    return text


def _log_usage(response) -> None:
    """记录 token 使用量。"""
    if response.usage:
        logger.info(
            "LLM token usage | prompt=%d | completion=%d | total=%d",
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
        )


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
