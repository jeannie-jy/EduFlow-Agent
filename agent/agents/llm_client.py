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

    绕过 function calling，直接在 content 中输出 JSON——
    DeepSeek 的 function calling 中文长文本场景格式不稳定。
    """
    settings = get_settings()
    client = _get_llm_client()

    schema_json = json.dumps(output_schema, ensure_ascii=False, indent=2)

    system_full = (
        system_prompt
        + "\n\n## 输出格式要求\n"
        + "你必须**只输出**一个合法的 JSON 对象，不要包含 markdown 代码块标记，不要有任何额外文字。\n"
        + "严格按照以下 JSON Schema：\n"
        + schema_json
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_full},
        {"role": "user", "content": user_message},
    ]

    raw_text = ""
    result = None

    # 逐次加倍 max_tokens 直到成功解析或达到上限（最多 4 次尝试：初始 + 3 次加倍）
    current_max_tokens = max_tokens
    prev_max_tokens = 0
    import httpx as _httpx
    for attempt in range(4):
        response = await client.chat.completions.create(
            model=model or settings.llm_model,
            messages=messages,
            temperature=temperature,
            max_tokens=current_max_tokens,
            timeout=_httpx.Timeout(120.0),
        )

        if not response.choices:
            logger.error("Structured LLM call returned empty choices")
            raise RuntimeError("LLM returned empty response")

        raw_text = response.choices[0].message.content or ""
        result = _extract_and_parse_json(raw_text)

        if result is not None:
            _log_usage(response)
            return result

        # 检查是否因截断导致解析失败
        is_truncated = (
            response.choices[0].finish_reason == "length"
            or _looks_truncated(raw_text)
        )
        if not is_truncated:
            break  # 不是截断问题，重试也没用

        prev_max_tokens = current_max_tokens
        current_max_tokens = min(current_max_tokens * 2, 65536)
        if current_max_tokens == prev_max_tokens:
            break  # token 已达上限，无法继续加倍
        logger.warning(
            "LLM 输出截断 (finish_reason=%s)，max_tokens=%d 重试 (attempt %d)",
            response.choices[0].finish_reason, current_max_tokens, attempt + 1,
        )

    # 解析失败 — 输出诊断
    _diagnose_json_error(raw_text)
    logger.error("JSON 解析失败，原始内容(前 1000 字符): %s", raw_text[:1000])
    raise RuntimeError(
        f"Failed to parse structured LLM output: {raw_text[:200]}"
    )


def _extract_and_parse_json(text: str) -> dict[str, Any] | None:
    """从 LLM 输出中提取并解析 JSON。

    处理：markdown code block、前后说明文字、尾随逗号、截断括号、截断字符串。
    """
    import re

    if not text or not text.strip():
        return None

    text = text.strip()

    # 0. 清理 BOM 和空字符
    text = text.replace("﻿", "").replace("\x00", "")
    # 1. 提取 markdown code block 内容
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()

    # 2. 找到最外层 { 到 } 的范围（跳过前后说明文字）
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    def _try_parse(s: str) -> dict[str, Any] | None:
        try:
            return json.loads(s)
        except json.JSONDecodeError as e:
            logger.debug("JSON parse error at pos %d: %s", e.pos, str(e)[:120])
            return None

    # 3. 直接解析
    result = _try_parse(text)
    if result is not None:
        return result

    # 4. 尾随逗号修复
    repaired = re.sub(r",\s*(\}|\])", r"\1", text)
    repaired = re.sub(r",\s*,", ",", repaired)
    result = _try_parse(repaired)
    if result is not None:
        return result

    # 5. 截断修复
    fixed = _fix_truncated_json(repaired)
    if fixed != repaired:
        result = _try_parse(fixed)
        if result is not None:
            return result

    # 6. 字符串内未转义换行修复：JSON 字符串值中不应有裸换行
    fixed = _fix_unescaped_newlines(repaired)
    result = _try_parse(fixed)
    if result is not None:
        return result

    # 7. 最后手段：demjson3 / 暴力修复
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


def _fix_unescaped_newlines(text: str) -> str:
    """修复 JSON 字符串值中的裸换行符。

    LLM 有时会在 narration 等长文本中输出实际换行，这在 JSON 中不合法。
    """
    result = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            result.append(ch)
            continue
        if ch == "\\":
            escape = True
            result.append(ch)
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and ch in "\n\r\t":
            result.append({"\\n": "\\n", "\\r": "\\r", "\\t": "\\t"}[ch])
            continue
        result.append(ch)
    return "".join(result)


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


def _diagnose_json_error(text: str) -> None:
    """诊断 JSON 解析错误，输出错误位置附近的上下文。"""
    import re

    # 提取有效 JSON 部分
    cleaned = text.strip()
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
    if m:
        cleaned = m.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start:end + 1]

    try:
        json.loads(cleaned)
        return  # 能解析，不需要诊断
    except json.JSONDecodeError as e:
        pos = e.pos
        lineno = e.lineno
        colno = e.colno
        logger.error(
            "JSON 解析错误: %s | line=%d col=%d pos=%d",
            e.msg, lineno, colno, pos,
        )
        # 输出错误位置前后各 100 字符
        ctx_start = max(0, pos - 100)
        ctx_end = min(len(cleaned), pos + 100)
        logger.error(
            "JSON 错误上下文 [%d:%d]: ...%s[>>>HERE<<<]%s...",
            ctx_start, ctx_end,
            cleaned[ctx_start:pos], cleaned[pos:ctx_end],
        )


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
