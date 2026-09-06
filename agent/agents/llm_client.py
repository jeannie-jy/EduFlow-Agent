"""LLM 客户端工厂。

统一封装 OpenAI 兼容的 LLM 调用（DeepSeek API）。
支持 function calling 和结构化 JSON 输出。

客户端为「线程本地」单例：httpx AsyncClient 绑定创建它的事件循环，
模块级全局单例在导出线程（独立事件循环）复用会触发跨 loop 错误
（got Future attached to a different loop），因此每个线程持有自己的客户端。
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)

# ── 线程本地客户端（httpx 绑定事件循环，跨线程/跨 loop 复用会崩）────

_llm_client_local = threading.local()
_embedding_client_local = threading.local()


def _get_llm_client(provider: str = "primary") -> AsyncOpenAI:
    """获取当前线程的 LLM 客户端（每个线程首次调用时创建）。"""
    attribute = "client" if provider == "primary" else "backup_client"
    client = getattr(_llm_client_local, attribute, None)
    if client is None:
        import httpx
        settings = get_settings()
        if provider == "backup":
            if not _backup_available(settings):
                raise RuntimeError("Backup LLM provider is not configured")
            endpoint = settings.llm_backup_endpoint
            api_key = settings.llm_backup_api_key
        else:
            endpoint = settings.llm_endpoint
            api_key = settings.llm_api_key
        client = AsyncOpenAI(
            base_url=endpoint,
            api_key=api_key,
            timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=10.0),
            max_retries=0,
        )
        setattr(_llm_client_local, attribute, client)
    return client


def _backup_available(settings) -> bool:
    return bool(
        getattr(settings, "llm_backup_endpoint", "")
        and getattr(settings, "llm_backup_model", "")
        and getattr(settings, "llm_backup_api_key", "")
    )


def _routed_model(settings, explicit_model: str | None, routing_key: str | None) -> str:
    if explicit_model:
        return explicit_model
    route = (routing_key or "").split(":", 1)[0]
    configured = getattr(settings, f"llm_{route}_model", "") if route else ""
    return configured or settings.llm_model


def _get_embedding_client() -> AsyncOpenAI:
    """获取当前线程的 Embedding 客户端。"""
    client = getattr(_embedding_client_local, "client", None)
    if client is None:
        settings = get_settings()
        client = AsyncOpenAI(
            base_url=settings.embedding_endpoint,
            api_key=settings.embedding_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
        _embedding_client_local.client = client
    return client


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
    routing_key: str | None = None,
    disable_thinking: bool = False,
    conversation: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """通用 LLM 调用封装。

    Args:
        disable_thinking: DeepSeek 新版 API 默认开启 thinking mode。长代码/长
            文本生成场景（如 Manim 代码）下模型会在推理上耗尽 token 预算，
            返回空 content 或超时；置 True 可关闭，生成更快且确定。

    Returns:
        {
            "content": str | None,
            "tool_calls": list[dict],
            "finish_reason": str | None,
            "refusal": str | None,
            "usage": {"input": int, "output": int},
        }
    """
    settings = get_settings()
    client = _get_llm_client("primary")
    selected_model = _routed_model(settings, model, routing_key)
    prompt_version = _prompt_fingerprint(system_prompt)

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    if conversation is None:
        messages.append({"role": "user", "content": user_message})
    else:
        # The runtime, not the model, creates tool-result messages. Keep this
        # explicit so a caller can continue a standards-compliant multi-turn
        # OpenAI-compatible tool conversation.
        messages.extend(conversation)

    kwargs: dict[str, Any] = dict(
        model=selected_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
        # DeepSeek 新版 API 默认开启 thinking mode，与 tool_choice 不兼容
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    elif disable_thinking:
        # 长代码生成场景：thinking 模式耗尽 token 预算导致空内容/超时
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    request_started = time.perf_counter()
    from services.llm_gateway import execute_llm_call_with_fallback

    backup_client = _get_llm_client("backup") if _backup_available(settings) else None
    backup_kwargs = {key: value for key, value in kwargs.items() if key != "extra_body"}
    response, used_fallback = await execute_llm_call_with_fallback(
        settings.llm_endpoint,
        "chat",
        lambda: client.chat.completions.create(**kwargs),
        fallback_provider=settings.llm_backup_endpoint if backup_client else None,
        fallback_call=(
            lambda: backup_client.chat.completions.create(
                **{**backup_kwargs, "model": settings.llm_backup_model}
            )
            if backup_client
            else None
        ),
    )
    duration_ms = (time.perf_counter() - request_started) * 1000

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

    _log_usage(
        response,
        model=settings.llm_backup_model if used_fallback else kwargs["model"],
        operation="chat",
        duration_ms=duration_ms,
        prompt_version=prompt_version,
        endpoint=(
            settings.llm_backup_endpoint if used_fallback else settings.llm_endpoint
        ),
    )
    return {
        "content": choice.message.content,
        "tool_calls": tool_calls,
        "assistant_message": {
            "role": "assistant",
            "content": choice.message.content,
            "tool_calls": [
                {
                    "id": item["id"],
                    "type": "function",
                    "function": {
                        "name": item["name"],
                        "arguments": json.dumps(item["arguments"], ensure_ascii=False),
                    },
                }
                for item in tool_calls
            ],
        },
        # 诊断字段：空内容时靠 finish_reason/refusal 区分限流、内容过滤等
        "finish_reason": choice.finish_reason,
        "refusal": getattr(choice.message, "refusal", None),
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
    routing_key: str | None = None,
    disable_thinking: bool = True,
    json_mode: bool = True,
) -> dict[str, Any]:
    """调用 LLM 并以结构化 JSON 格式输出。

    结构化提取默认关闭 DeepSeek V4 的 thinking mode：推理 token 与最终
    JSON 共用输出预算，默认 high effort 会让小型 JSON 也频繁触发 length。
    同时启用 OpenAI-compatible JSON mode，function calling 仍保留给真正的
    Tool Runtime，避免把数据生成伪装成工具调用。
    """
    settings = get_settings()
    client = _get_llm_client("primary")
    selected_model = _routed_model(settings, model, routing_key)
    backup_client = _get_llm_client("backup") if _backup_available(settings) else None

    # Schema 供模型读取而非人类阅读；紧凑序列化可显著减少每个模块都会
    # 重复发送的输入 token，字段约束本身不受影响。
    schema_json = json.dumps(output_schema, ensure_ascii=False, separators=(",", ":"))

    system_full = (
        system_prompt
        + "\n\n## 输出格式要求\n"
        + "你必须**只输出**一个合法的 JSON 对象，不要包含 markdown 代码块标记，不要有任何额外文字。\n"
        + "严格按照以下 JSON Schema：\n"
        + schema_json
    )
    prompt_version = _prompt_fingerprint(system_full)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_full},
        {"role": "user", "content": user_message},
    ]

    raw_text = ""
    result = None
    retry_hint_added = False

    # JSON mode + non-thinking 下，一次有界重试足以覆盖偶发空响应/截断。
    # 继续进行 4 次指数扩容只会放大延迟和费用，且掩盖无界 schema 问题。
    max_attempts = 2
    hard_max_tokens = 32768
    current_max_tokens = min(max_tokens, hard_max_tokens)
    prev_max_tokens = 0
    for attempt in range(max_attempts):
        request_started = time.perf_counter()
        from services.llm_gateway import execute_llm_call_with_fallback

        primary_kwargs: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": current_max_tokens,
        }
        if json_mode:
            primary_kwargs["response_format"] = {"type": "json_object"}
        if disable_thinking and "deepseek.com" in settings.llm_endpoint.lower():
            primary_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        backup_kwargs = {
            key: value for key, value in primary_kwargs.items() if key != "extra_body"
        }
        backup_kwargs["model"] = settings.llm_backup_model
        if (
            disable_thinking
            and backup_client
            and "deepseek.com" in settings.llm_backup_endpoint.lower()
        ):
            backup_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        response, used_fallback = await execute_llm_call_with_fallback(
            settings.llm_endpoint,
            "structured",
            lambda: client.chat.completions.create(**primary_kwargs),
            fallback_provider=settings.llm_backup_endpoint if backup_client else None,
            fallback_call=(
                lambda: backup_client.chat.completions.create(**backup_kwargs)
                if backup_client
                else None
            ),
        )

        if not response.choices:
            logger.error("Structured LLM call returned empty choices")
            raise RuntimeError("LLM returned empty response")

        choice = response.choices[0]
        raw_text = choice.message.content or ""

        # Every provider response is billable, including malformed/truncated
        # attempts. Recording only the successful parse hid retries from the
        # workflow trace and allowed the real request budget to be exceeded.
        _log_usage(
            response,
            model=settings.llm_backup_model if used_fallback else selected_model,
            operation="structured",
            duration_ms=(time.perf_counter() - request_started) * 1000,
            prompt_version=prompt_version,
            endpoint=(
                settings.llm_backup_endpoint if used_fallback else settings.llm_endpoint
            ),
        )

        # 如果 content 为空但存在 tool_calls，回退到解析 tool_calls 参数
        if not raw_text.strip() and choice.message.tool_calls:
            raw_text = choice.message.tool_calls[0].function.arguments

        result = _extract_and_parse_json(raw_text)

        if result is not None:
            return result

        # 检查是否因截断导致解析失败
        is_truncated = (
            choice.finish_reason == "length"
            or _looks_truncated(raw_text)
        )
        if not is_truncated:
            break  # 不是截断问题，重试也没用

        if attempt + 1 >= max_attempts:
            break

        from services.telemetry import record_gateway_retry

        record_gateway_retry(
            operation="structured",
            reason=str(choice.finish_reason or "incomplete_json"),
        )
        prev_max_tokens = current_max_tokens
        current_max_tokens = min(current_max_tokens * 2, hard_max_tokens)
        if current_max_tokens == prev_max_tokens:
            break  # token 已达上限，无法继续加倍
        if not retry_hint_added:
            # A larger budget alone often causes the model to produce an even
            # larger DSL. Add one compact retry instruction so the next call
            # prefers concise narration/metadata and reserves tokens for the
            # remaining JSON structure.
            messages.append({
                "role": "user",
                "content": (
                    "上一轮输出未形成完整 JSON。请重试并严格只输出合法 JSON；"
                    "压缩 narration、解释和重复 metadata，优先保证所有括号闭合，"
                    "不要输出 markdown 或额外说明。"
                ),
            })
            retry_hint_added = True
        logger.warning(
            "LLM 结构化输出不完整 (finish_reason=%s, used_max_tokens=%d); "
            "next_max_tokens=%d retry=%d/%d",
            response.choices[0].finish_reason,
            prev_max_tokens,
            current_max_tokens,
            attempt + 1,
            max_attempts - 1,
        )

    # 解析失败 — 输出诊断
    _diagnose_json_error(raw_text)
    logger.error(
        "JSON 解析失败 | output_chars=%d output_sha256=%s",
        len(raw_text),
        hashlib.sha256(raw_text.encode("utf-8", errors="replace")).hexdigest()[:16],
    )
    raise RuntimeError("Failed to parse structured LLM output")


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
    """Log parse coordinates without recording model-generated content."""
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


def _log_usage(
    response,
    *,
    model: str = "unknown",
    operation: str = "unknown",
    duration_ms: float = 0,
    prompt_version: str = "unknown",
    endpoint: str | None = None,
) -> None:
    """记录 token 使用量。"""
    if response.usage:
        from services.telemetry import record_llm_call, request_id_var

        record_llm_call(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            duration_ms=duration_ms,
            model=model,
            operation=operation,
            estimated_cost_usd=(
                response.usage.prompt_tokens * get_settings().llm_input_cost_per_million
                + response.usage.completion_tokens
                * get_settings().llm_output_cost_per_million
            )
            / 1_000_000,
            endpoint=endpoint,
            prompt_version=prompt_version,
        )
        logger.info(
            "LLM call | request_id=%s model=%s operation=%s prompt_version=%s duration_ms=%.1f "
            "prompt_tokens=%d completion_tokens=%d total_tokens=%d",
            request_id_var.get(),
            model,
            operation,
            prompt_version,
            duration_ms,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
        )


def _prompt_fingerprint(prompt: str) -> str:
    """Content-address prompts without logging their potentially sensitive text."""
    return hashlib.sha256(prompt.encode("utf-8", errors="replace")).hexdigest()[:16]


async def generate_embedding(text: str) -> list[float]:
    """生成文本的向量嵌入。"""
    client = _get_embedding_client()

    settings = get_settings()
    from services.llm_gateway import execute_llm_call

    response = await execute_llm_call(
        settings.embedding_endpoint,
        "embedding",
        lambda: client.embeddings.create(
            model=settings.embedding_model,
            input=text,
        ),
    )

    if not response.data:
        raise RuntimeError("Embedding API returned empty data")

    return response.data[0].embedding
