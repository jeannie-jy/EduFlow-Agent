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

_MANIM_NAMES_CACHE: frozenset[str] | None = None

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
    issues.extend(_check_table_text_data(script))

    # ── AST 静态检查（比上面的语义检查更通用）──
    issues.extend(_check_undefined_names(script))

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
    from adapters.manim_adapter import _has_cjk
    issues = []
    for m in re.finditer(r"MathTex\(([^)]+)\)", script):
        arg = m.group(1)
        if any(_has_cjk(ch) for ch in arg):
            lineno = script[:m.start()].count("\n") + 1
            issues.append({
                "rule": "mathtex-cjk", "severity": "error",
                "line": lineno,
                "detail": f"MathTex 含 CJK: {arg[:60]}",
            })
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


def _check_table_text_data(script: str) -> list[dict]:
    """Table() 的数据必须是字符串，不能是 Text() 对象。

    Manim Table 内部会对单元格做 "\\n".join(list(text))，
    传 Text 对象会报 TypeError: expected str instance, Text found。
    """
    issues = []
    # 匹配 Table( 后面直到匹配的 ) 之前，[ ... Text(...) ... ] 的模式
    # 简化检测：在 Table( 调用的上下文中查找 Text( 对象作为数据元素的模式
    for m in re.finditer(r"Table\(.*?\[.*?Text\s*\(.*?\].*?\)", script, re.DOTALL):
        lineno = script[:m.start()].count("\n") + 1
        ctx = m.group(0)[:120]
        issues.append({
            "rule": "table-text-data",
            "severity": "error",
            "line": lineno,
            "detail": f"Table() 的数据中使用了 Text() 对象，应改为纯字符串。片段: {ctx}",
        })
    return issues


# Python 内置常量/函数（不随 Manim 变化）
_PYTHON_BUILTINS: frozenset[str] = frozenset({
    "True", "False", "None", "int", "str", "float", "list", "dict", "set",
    "tuple", "range", "len", "zip", "enumerate", "reversed", "sorted",
    "print", "min", "max", "sum", "abs", "round", "type", "isinstance",
    "super", "object", "Exception", "ValueError", "TypeError",
    "self", "np", "math", "json", "os", "sys", "time", "itertools", "re",
})


def _get_manim_public_names() -> frozenset[str]:
    """动态导入 Manim，获取 ``from manim import *`` 导出的全部公开名。

    结果缓存在模块级别避免重复导入。
    """
    global _MANIM_NAMES_CACHE
    if _MANIM_NAMES_CACHE is not None:
        return _MANIM_NAMES_CACHE
    try:
        import manim as _manim
        if hasattr(_manim, "__all__"):
            _MANIM_NAMES_CACHE = frozenset(n for n in _manim.__all__ if isinstance(n, str))
        else:
            _MANIM_NAMES_CACHE = frozenset(n for n in dir(_manim) if n[0].isupper() or n.startswith("__"))
    except Exception:
        _MANIM_NAMES_CACHE = frozenset()
    return _MANIM_NAMES_CACHE


def _collect_defined_names(tree: ast.AST) -> set[str]:
    """收集 AST 中所有被赋值/定义的变量名。"""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.FunctionDef):
            names.add(node.name)
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                names.add(arg.arg)
            if node.args.vararg:
                names.add(node.args.vararg.arg)
            if node.args.kwarg:
                names.add(node.args.kwarg.arg)
    return names


def _check_undefined_names(script: str) -> list[dict]:
    """检测函数中引用了未定义的变量名。

    遍历所有函数定义，检查函数体内的 Name(Load) 引用是否在以下范围中定义：
    - 函数参数
    - 函数体内赋值
    - 外层作用域（通常为 construct 方法的局部变量）
    - Python / Manim 内置名
    """
    issues: list[dict] = []
    try:
        tree = ast.parse(script)
    except SyntaxError:
        return issues  # 语法错误已被 _check_syntax 处理

    # 收集顶层和 construct 中的定义
    top_level_names = _collect_defined_names(tree)
    # 额外：from manim import * 导入的名称视为已定义
    top_level_names |= {"np", "math", "json", "os", "sys", "time", "itertools"}

    class FuncChecker(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            param_names = set()
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                param_names.add(arg.arg)
            if node.args.vararg:
                param_names.add(node.args.vararg.arg)
            if node.args.kwarg:
                param_names.add(node.args.kwarg.arg)

            # 收集函数体内的赋值
            body_defined = _collect_defined_names(node)
            manim_names = _get_manim_public_names()
            defined = param_names | body_defined | top_level_names | _PYTHON_BUILTINS | manim_names

            # 检查函数体中的 Name(Load)
            for child in ast.walk(node):
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                    if child.id not in defined:
                        issues.append({
                            "rule": "undefined-name",
                            "severity": "error",
                            "line": child.lineno,
                            "detail": f"函数 '{node.name}' 中使用了未定义的变量 '{child.id}'",
                        })
                        break  # 每个函数只报第一个错误
            self.generic_visit(node)

    FuncChecker().visit(tree)
    return issues
