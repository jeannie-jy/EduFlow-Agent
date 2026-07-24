"""Manim 脚本校验器 — 集中检测已知的生成问题。

三层质量保障的第二层：生成约束在 manim_adapter 中，本模块负责检测，
修复逻辑也在 manim_adapter 中。
"""

from __future__ import annotations

import ast
import re
from typing import Any

# ═══════════════════════════════════════════════════════════════
# 已知无效的 Pygments lexer 名称
# ═══════════════════════════════════════════════════════════════
_INVALID_LEXERS = frozenset({
    "pseudocode", "plaintext", "plain", "txt", "csharp",
    "typescript", "go", "rust", "swift", "kotlin", "ruby",
    "php", "perl", "lua", "scala", "dart", "matlab", "r",
    "sql", "xml", "html", "css", "yaml", "json", "markdown",
})

# ═══════════════════════════════════════════════════════════════
# 核心校验入口
# ═══════════════════════════════════════════════════════════════


def validate_script(script: str) -> list[dict[str, Any]]:
    """校验生成的 Manim 脚本，返回发现的问题列表。

    每个问题: {"rule": str, "severity": "error"|"warn", "line": int|None, "detail": str}
    """
    issues: list[dict[str, Any]] = []

    issues.extend(_check_syntax(script))
    if issues and issues[0]["severity"] == "error":
        return issues  # 语法错误时其余检查没有意义

    issues.extend(_check_mathtex_cjk(script))
    issues.extend(_check_invalid_lexer(script))
    issues.extend(_check_code_api(script))
    issues.extend(_check_rstring_escape(script))
    issues.extend(_check_print_in_construct(script))

    return issues


def has_errors(issues: list[dict]) -> bool:
    return any(i["severity"] == "error" for i in issues)


# ═══════════════════════════════════════════════════════════════
# 各项检查
# ═══════════════════════════════════════════════════════════════


def _check_syntax(script: str) -> list[dict]:
    try:
        ast.parse(script)
    except SyntaxError as e:
        return [{"rule": "syntax", "severity": "error",
                 "line": e.lineno, "detail": str(e)}]
    return []


def _check_mathtex_cjk(script: str) -> list[dict]:
    """MathTex 中包含中日韩字符 → LaTeX 编译会失败。"""
    issues = []
    for m in re.finditer(r"MathTex\(([^)]+)\)", script):
        arg = m.group(1)
        for ch in arg:
            if "一" <= ch <= "鿿" or "぀" <= ch <= "ヿ":
                lineno = script[:m.start()].count("\n") + 1
                issues.append({
                    "rule": "mathtex-cjk", "severity": "error",
                    "line": lineno,
                    "detail": f"MathTex 含中文: {arg[:60]}",
                })
                break
    return issues


def _check_invalid_lexer(script: str) -> list[dict]:
    """检查 Code 的 language= 参数是否使用了无效的 Pygments lexer。"""
    issues = []
    for m in re.finditer(r"""language\s*=\s*['"]([^'"]+)['"]""", script):
        lang = m.group(1)
        if lang in _INVALID_LEXERS:
            lineno = script[:m.start()].count("\n") + 1
            issues.append({
                "rule": "invalid-lexer", "severity": "error",
                "line": lineno,
                "detail": f"无效的 Pygments lexer: '{lang}'，应降级为 'text'",
            })
    return issues


def _check_code_api(script: str) -> list[dict]:
    """Manim v0.20 Code 类使用 code_string= 而非 code=。"""
    issues = []
    for m in re.finditer(r"Code\(\s*code\s*=", script):
        lineno = script[:m.start()].count("\n") + 1
        issues.append({
            "rule": "code-api", "severity": "error",
            "line": lineno,
            "detail": "Code 使用了 code= 参数，Manim v0.20+ 需 code_string=",
        })
    return issues


def _check_rstring_escape(script: str) -> list[dict]:
    r"""r-string 内的 \" 或 \' 会被当作字面反斜杠，不是转义。"""
    issues = []
    for m in re.finditer(r"""(r"[^"]*\\[^ntr\\][^"]*")""", script):
        lineno = script[:m.start()].count("\n") + 1
        issues.append({
            "rule": "rstring-escape", "severity": "warn",
            "line": lineno,
            "detail": f"r-string 含反斜杠可能造成渲染问题: {m.group(1)[:60]}",
        })
    return issues


def _check_print_in_construct(script: str) -> list[dict]:
    """construct 中的直接 print() 语句可能是调试残留。

    排除字符串字面量中的 print()（如 code_string='...print(...)'）。
    """
    issues = []
    # 匹配行首（去缩进后）的 print( —— 而非字符串内部的 print(
    for m in re.finditer(r"^\s*print\s*\(", script, re.MULTILINE):
        pos = m.start()
        # 检查前面的内容：如果在字符串字面量中则跳过
        prefix = script[:pos]
        single_q = prefix.count("'") - prefix.count("\\'")
        double_q = prefix.count('"') - prefix.count('\\"')
        if single_q % 2 != 0 or double_q % 2 != 0:
            continue  # 在字符串内部
        lineno = prefix.count("\n") + 1
        issues.append({
            "rule": "print-in-construct", "severity": "warn",
            "line": lineno, "detail": "construct 中存在 print() 调试残留",
        })
    return issues
