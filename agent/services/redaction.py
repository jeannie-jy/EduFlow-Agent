"""Boundary-safe diagnostic redaction.

Internal logs may retain exception types and stack traces, but API/SSE payloads must
never echo model output, credentials, prompts, or filesystem paths.
"""

from __future__ import annotations

import re

_REDACTIONS = (
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(postgres(?:ql)?(?:\+asyncpg)?://[^:\s]+:)[^@\s]+@"), r"\1[REDACTED]@"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"(?i)\b[A-Z]:\\[^\r\n\t]+"), "[REDACTED_PATH]"),
    (re.compile(r"(?<!:)\b/(?:app|home|users|tmp|var)/[^\r\n\t]+", re.I), "[REDACTED_PATH]"),
)


def redact_diagnostic(value: object, *, max_length: int = 500) -> str:
    """Redact common secret/path forms and bound diagnostic payload size."""
    text = str(value).replace("\x00", "")
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text[:max_length]


def public_failure_message(kind: str) -> str:
    """Return a stable user-facing message without interpolating an exception."""
    messages = {
        "module": "模块生成失败，请稍后重试",
        "render": "视频渲染失败，请检查输入后重试",
        "export": "导出处理失败，请稍后重试",
    }
    return messages.get(kind, "处理失败，请稍后重试")
