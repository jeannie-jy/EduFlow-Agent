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
    issues.extend(_check_undefined_names(script))
    issues.extend(_check_invalid_kwargs(script))

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


# ═══════════════════════════════════════════════════════════════
# 非法关键字参数检测（LLM 常把某类的参数误用到另一类）
# ═══════════════════════════════════════════════════════════════

# manim 0.20 中「类名 → 不存在的关键字参数」映射（新增误用在此扩展）。
# 例：markdown 参数属于 Code，Text 没有 → Text(..., markdown=False) 运行时 TypeError。
_INVALID_KWARGS: dict[str, set[str]] = {
    "Text": {"markdown"},
    "MarkupText": {"markdown"},
}


def _check_invalid_kwargs(script: str) -> list[dict]:
    """AST 检测常见 API 误用：给不支持的类传了不存在的关键字参数。"""
    try:
        tree = ast.parse(script)
    except SyntaxError:
        return []  # 语法错误由 _check_syntax 负责

    issues: list[dict] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        invalid = _INVALID_KWARGS.get(node.func.id)
        if not invalid:
            continue
        for kw in node.keywords:
            if kw.arg in invalid:
                issues.append({
                    "rule": "invalid-kwarg",
                    "severity": "error",
                    "line": getattr(node, "lineno", None),
                    "detail": (
                        f"{node.func.id}() 不支持参数 '{kw.arg}'"
                        f"（manim 0.20，该参数属于 Code），请移除"
                    ),
                })
    return issues


# ═══════════════════════════════════════════════════════════════
# 未定义变量检测（运行时 NameError 的静态前置检查）
# ═══════════════════════════════════════════════════════════════

# manim 模块导出名（from manim import * 的展开）与 Python builtins 缓存
_MANIM_EXPORTS: frozenset[str] | None = None
_BUILTIN_NAMES: frozenset[str] | None = None


def _get_manim_exports() -> frozenset[str]:
    """动态获取 manim 包的实际导出名（import * 的展开）。"""
    global _MANIM_EXPORTS
    if _MANIM_EXPORTS is None:
        try:
            import manim as _manim
            _MANIM_EXPORTS = frozenset(
                n for n in dir(_manim) if not n.startswith("_")
            )
        except Exception:
            _MANIM_EXPORTS = frozenset()
    return _MANIM_EXPORTS


def _get_builtin_names() -> frozenset[str]:
    global _BUILTIN_NAMES
    if _BUILTIN_NAMES is None:
        import builtins as _builtins
        _BUILTIN_NAMES = frozenset(dir(_builtins))
    return _BUILTIN_NAMES


def _iter_names(node) -> list[str]:
    """提取赋值目标的绑定名（Name/Tuple/List/Starred）。"""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        out: list[str] = []
        for el in node.elts:
            out.extend(_iter_names(el))
        return out
    if isinstance(node, ast.Starred):
        return _iter_names(node.value)
    return []


def _import_names(node) -> list[str]:
    """提取 import 语句绑定的名字（去别名）。"""
    if isinstance(node, ast.Import):
        return [(a.asname or a.name).split(".")[0] for a in node.names]
    if isinstance(node, ast.ImportFrom):
        # from manim import * 由 _get_manim_exports 覆盖，这里跳过 *
        return [a.asname or a.name for a in node.names if a.name != "*"]
    return []


def _iter_direct(node):
    """遍历节点的直接子树；嵌套的 FunctionDef/ClassDef 只产出节点本身（收集名字），不下钻。"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield child  # 仅用于收集 def/class 名
            continue
        yield child
        yield from _iter_direct(child)


def _collect_direct_bindings(fn_node) -> set[str]:
    """收集函数/类的直接绑定（函数参数 + 直属赋值/def/import/for/with/except）。"""
    bound: set[str] = set()
    if isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = list(fn_node.args.args) + list(fn_node.args.kwonlyargs)
        if fn_node.args.vararg:
            args.append(fn_node.args.vararg)
        if fn_node.args.kwarg:
            args.append(fn_node.args.kwarg)
        for arg in args:
            bound.add(arg.arg)

    for n in _iter_direct(fn_node):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                bound.update(_iter_names(t))
        elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
            bound.update(_iter_names(n.target))
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            bound.update(_import_names(n))
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            bound.update(_iter_names(n.target))
        elif isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            # 推导式循环变量（如 [make_cell(v) for v in values] 中的 v）
            for gen in n.generators:
                bound.update(_iter_names(gen.target))
        elif isinstance(n, ast.Lambda):
            # lambda 参数（如 lambda x: x * 2 中的 x）
            for arg in n.args.args:
                bound.add(arg.arg)
        elif isinstance(n, ast.With) and n.optional_vars:
            bound.update(_iter_names(n.optional_vars))
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)
    return bound


def _check_undefined_names(script: str) -> list[dict]:
    """AST 检测未定义变量（如 LLM 生成代码常见的 NameError: font_size is not defined）。

    作用域处理：函数参数 + 直属赋值 + 闭包链（外层函数绑定）+ 模块级绑定 +
    from manim import * 导出名 + Python builtins。只检查 Load 上下文的 Name。

    Returns:
        问题列表；rule="undefined-name"，severity="error"。
    """
    try:
        tree = ast.parse(script)
    except SyntaxError:
        return []  # 语法错误由 _check_syntax 负责

    manim_names = _get_manim_exports()
    builtin_names = _get_builtin_names()
    issues: list[dict] = []

    # 模块级绑定（class/def/赋值/import 名）
    module_bound: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_bound.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                module_bound.update(_iter_names(t))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            module_bound.update(_iter_names(node.target))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            module_bound.update(_import_names(node))

    def is_known(name: str, chain: set[str]) -> bool:
        return (
            name in chain
            or name in module_bound
            or name in manim_names
            or name in builtin_names
        )

    def walk_scope(fn_node, chain: set[str]) -> None:
        """检查函数体（含嵌套函数的闭包链），递归处理嵌套函数。"""
        local = set(chain)
        local |= _collect_direct_bindings(fn_node)

        for n in _iter_direct(fn_node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                if not is_known(n.id, local):
                    issues.append({
                        "rule": "undefined-name",
                        "severity": "error",
                        "line": getattr(n, "lineno", None),
                        "detail": f"未定义变量 '{n.id}'（函数 {fn_node.name}）",
                    })

        for child in fn_node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk_scope(child, local)

    def walk_class(class_node, chain: set[str]) -> None:
        """类：方法以类级绑定 + 外层链为作用域。"""
        class_chain = set(chain)
        class_chain |= _collect_direct_bindings(class_node)
        for child in class_node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk_scope(child, class_chain)
            elif isinstance(child, ast.ClassDef):
                walk_class(child, class_chain)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            walk_scope(node, set())
        elif isinstance(node, ast.ClassDef):
            walk_class(node, set())

    return issues
