"""Manim LLM Adapter — 使用 LLM 将 DSL 转化为高质量 Manim 代码。

LLM 拥有完全创作自由，根据教学语义自主设计可视化、布局、配色和动画。
"""

from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any

from agents.prompts import MANIM_CODER_SYSTEM_PROMPT
from adapters.manim_adapter import generate_render_config, generate_subtitles_srt

logger = logging.getLogger(__name__)


def _extract_python_code(raw: str) -> str:
    """从 LLM 响应中提取 Python 代码。"""
    md = re.search(r"```(?:python)?\s*\n(.*?)```", raw, re.DOTALL)
    if md:
        return md.group(1).strip()
    for marker in ("from manim import", "#!/usr/bin/env python"):
        idx = raw.find(marker)
        if idx >= 0:
            return raw[idx:].strip()
    return raw.strip()


def _skip_string_literal(text: str, i: int) -> int:
    """跳过从 i 开始的字符串字面量（含转义），返回字符串结束后的索引。"""
    quote = text[i]
    n = len(text)
    j = i + 1
    while j < n:
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == quote:
            break
        j += 1
    return min(j + 1, n)


# manim 0.20.1 Code 不接受的 Text 样式参数（Text 有而 Code 的
# __init__ 签名没有，且无 **kwargs → 传了渲染期 TypeError）。
# LLM 会持续把 Text 习惯带过来（font_size → font → color → ...），
# 所以整体剥离而非逐个打补丁。新增名字前需对照
# inspect.signature(Code.__init__) 确认确实不在签名中。
_CODE_TEXT_STYLE_KWARGS = frozenset({
    "font", "font_size", "color", "fill_color", "fill_opacity",
    "stroke_width", "stroke_color", "background_color",
    "line_spacing", "slant", "weight",
})


def _strip_code_text_style_kwargs(code: str) -> str:
    """仅从 Code() 调用的顶层参数中移除 Text 样式参数。

    Manim v0.20 的 Code 类不接受 font/font_size/color 等 Text 样式参数
    （字号、字体由全局样式控制，大小用 code.scale() 调整），LLM 常把
    Text 的习惯带过来。此前只剥离 font_size，LLM 又幻觉出 font ——
    现在整体剥离 Text 样式参数集合。
    只处理真正的 Code( 调用：先跳过字符串字面量定位调用，再按括号深度
    取调用区间；区间内只在深度 1（Code 的直接参数）移除——嵌套配置
    （paragraph_config/background_config 字典）与 code_string 内容不受影响，
    Text(...) / Table(...) 等合法使用不受影响。
    """

    def _find_call_end(text: str, open_idx: int) -> int:
        """从 '(' 开始括号深度匹配（跳过字符串），返回匹配的 ')' 索引。"""
        depth = 0
        i = open_idx
        n = len(text)
        while i < n:
            if text[i] in ('"', "'"):
                i = _skip_string_literal(text, i)
                continue
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return n - 1  # 括号不闭合，退化为末尾

    def _strip_top_level(text: str) -> str:
        """在 Code( 调用区间内移除深度 1 的黑名单 kwargs（含分隔逗号）。"""
        out: list[str] = []
        i, n = 0, len(text)
        depth = 0
        while i < n:
            c = text[i]
            if c in ('"', "'"):
                end = _skip_string_literal(text, i)
                out.append(text[i:end])
                i = end
                continue
            if c == "(":
                depth += 1
                out.append(c)
                i += 1
                continue
            if c == ")":
                depth -= 1
                out.append(c)
                i += 1
                continue
            if depth == 1 and (c.isalpha() or c == "_"):
                m = re.match(r"[A-Za-z_]\w*", text[i:])
                if m and m.group(0) in _CODE_TEXT_STYLE_KWARGS:
                    name = m.group(0)
                    j = i + len(name)
                    while j < n and text[j] in " \t\n\r":
                        j += 1
                    if j < n and text[j] == "=":
                        # 消费 name=value 直到深度 1 的分隔逗号或闭合括号
                        # （()/[]/{} 都计深度，值内容器的逗号不是参数分隔）
                        k = j + 1
                        d = depth
                        while k < n:
                            ch = text[k]
                            if ch in ('"', "'"):
                                k = _skip_string_literal(text, k)
                                continue
                            if ch in "([{":
                                d += 1
                            elif ch in ")]}":
                                if d == 1:
                                    break
                                d -= 1
                            elif ch == "," and d == 1:
                                k += 1  # 吃掉分隔逗号
                                while k < n and text[k] in " \t\n\r":
                                    k += 1  # 以及逗号后的空白
                                break
                            k += 1
                        # 移除该 kwarg 前的前导空白（避免残留空行）
                        while out and out[-1] in " \t\n\r":
                            out.pop()
                        # 若前面是逗号且后面还有参数，补一个分隔空格
                        if out and out[-1] == "," and k < n and text[k] != ")":
                            out.append(" ")
                        i = k
                        continue
            out.append(c)
            i += 1
        return "".join(out)

    result: list[str] = []
    pos = 0
    i = 0
    n = len(code)
    while i < n:
        if code[i] in ('"', "'"):
            i = _skip_string_literal(code, i)
            continue
        if (
            code.startswith("Code", i)
            and (i == 0 or not (code[i - 1].isalnum() or code[i - 1] == "_"))
        ):
            k = i + 4
            while k < n and code[k] in " \t\n\r":
                k += 1
            if k < n and code[k] == "(":
                end = _find_call_end(code, k)
                result.append(code[pos:i])
                result.append(_strip_top_level(code[i:end + 1]))
                pos = end + 1
                i = pos
                continue
        i += 1
    result.append(code[pos:])
    return "".join(result)


def _rewrite_outside_strings(text: str, pattern: re.Pattern, repl: str) -> str:
    """在字符串字面量之外做正则替换（code_string 等内容原样保留）。

    与 _strip_font_size_from_code 同一机制：跳过字符串字面量（含三引号退化），
    只对字符串之间的代码区做替换。
    """
    out: list[str] = []
    last = 0
    i = 0
    n = len(text)
    while i < n:
        if text[i] in ('"', "'"):
            end = _skip_string_literal(text, i)
            out.append(pattern.sub(repl, text[last:i]))
            out.append(text[i:end])
            last = end
            i = end
            continue
        i += 1
    out.append(pattern.sub(repl, text[last:]))
    return "".join(out)


def _fix_code_object_access(code: str) -> str:
    """修复 LLM 幻觉的 Code 属性访问 — Manim Code 是 VGroup，没有 .code / .code_block。

    manim 0.20.1 真实 API：code.code_lines（行 Paragraph，逐行可着色）/
    code.background（背景矩形）/ code.line_numbers（行号）。
    LLM 常顺着 DSL 里的 visual_object type "code_block" 发明 code.code_block 属性
    （渲染期 AttributeError）。修复顺序：复合索引 [1][N] → 单层索引 → 裸属性。
    全部在字符串字面量之外执行，避免破坏 code_string 展示内容。
    """
    # code.code_block[1][N] -> code.code_lines[N]（旧错误教学里的 [1] 层直接消除）
    code = _rewrite_outside_strings(
        code, re.compile(r"(\w+)\.code_block\[1\]\[([^\]]+)\]"), r"\1.code_lines[\2]"
    )
    # code.code_block[0] -> code.background（旧错误教学：[0]=背景矩形）
    code = _rewrite_outside_strings(
        code, re.compile(r"(\w+)\.code_block\[0\]"), r"\1.background"
    )
    # code.code_block[1]（无后续索引）-> code.code_lines（旧教学：[1]=所有行）
    code = _rewrite_outside_strings(
        code, re.compile(r"(\w+)\.code_block\[1\](?!\[)"), r"\1.code_lines"
    )
    # code.code_block[N] (N>=1) -> code.code_lines[N-1]（按旧教学语义视为第 N 行）
    code = _rewrite_outside_strings(
        code, re.compile(r"(\w+)\.code_block\[(\d+)\]"), r"\1.code_lines[\2 - 1]"
    )
    # code.code_block（裸属性，如 len(code.code_block)）-> code.code_lines
    code = _rewrite_outside_strings(
        code, re.compile(r"(\w+)\.code_block\b"), r"\1.code_lines"
    )
    # code_block.code.set_color(X) -> for _cl in code_block: _cl.set_color(X)
    code = _rewrite_outside_strings(
        code,
        re.compile(r'(\b\w+)\.code\.set_color\('),
        r'for _cl in \1: _cl.set_color(',
    )
    # len(xxx.code) -> len(xxx)
    code = _rewrite_outside_strings(code, re.compile(r'len\((\w+)\.code\)'), r'len(\1)')
    # xxx.code[  ->  xxx[
    code = _rewrite_outside_strings(code, re.compile(r'(\w+)\.code\['), r'\1[')
    return code


def _fix_set_stroke_args(code: str) -> str:
    """移除 set_stroke() 中不存在的 fill_color/fill_opacity 参数。"""
    # set_stroke(..., fill_color=XXX, ...) -> 移除 fill_color=XXX
    code = re.sub(r',?\s*fill_color\s*=\s*"[^"]*"', '', code)
    # set_stroke(..., fill_opacity=0.3, ...) -> 移除 fill_opacity=N
    code = re.sub(r',?\s*fill_opacity\s*=\s*[\d.]+', '', code)
    return code


def _fix_camera_animate(code: str) -> str:
    """删除 self.camera.animate.* 调用 — Manim Camera 没有 .animate 属性。"""
    return re.sub(r'^\s*self\.play\(\s*self\.camera\.animate\.[^)]+\),?\s*run_time=[^)]*\)\s*$', '', code, flags=re.MULTILINE)


def _fix_empty_fadeout(code: str) -> str:
    """为 FadeOut(*self.mobjects) 添加空值保护，防止第一帧空场景崩溃。"""
    return re.sub(
        r'^(\s+)(self\.play\(FadeOut\(\*self\.mobjects,\s*run_time=[\d.]+\)\))',
        r'\1if self.mobjects:\n\1    \2',
        code,
        flags=re.MULTILINE,
    )


_SCENE_METHOD_FIXES: dict[str, str] = {
    # LLM 幻觉的 Scene 方法名 → 语义一致的真实 API
    # 例：clear_current()（「清空当前帧画面」）在 Manim 中不存在，正确 API 是 clear()
    "clear_current": "clear",
}


def _fix_scene_methods(code: str) -> str:
    """修复 LLM 幻觉的 Scene 方法名 — 直接映射到语义一致的真实 API。

    其余同类幻觉（如 reset_scene）由 validator 的 unknown-scene-method 规则
    拦截并触发 LLM 反馈重试，这里只放语义明确可无损替换的映射。
    """
    for bad, good in _SCENE_METHOD_FIXES.items():
        code = re.sub(rf"self\.{bad}\s*\(", f"self.{good}(", code)
    return code


def _fix_code_indexing(code: str) -> str:
    """修复 LLM 对 Code 对象的直接索引幻觉。

    Manim Code 是 VGroup，没有 code_block 属性；第 N 行必须通过
    code.code_lines[N-1] 访问（[0] 是背景矩形）。变量命名为
    code_block/code_obj/code_display 且被整数字面量直接索引时，
    视为 LLM 想取行 → 改写为 .code_lines[N-1]。
    """
    # 先处理旧教学形态 code_block[1][N]（[1] 层消除，与属性版同语义）
    code = _rewrite_outside_strings(
        code,
        re.compile(r'\b(code_block|code_obj|code_display)\[1\]\[(\d+)\]'),
        r'\1.code_lines[\2]',
    )

    def _replace(m):
        var = m.group(1)
        n = int(m.group(2))
        if n == 0:
            return f"{var}.background"
        return f"{var}.code_lines[{n - 1}]"

    return _rewrite_outside_strings(
        code, re.compile(r'\b(code_block|code_obj|code_display)\[(\d+)\]'), _replace
    )


class ManimCodeValidationError(RuntimeError):
    """LLM 生成的 Manim 代码校验未通过（重试后仍失败）。

    携带失败脚本与校验问题列表，供调用方落盘复现调试。
    """

    def __init__(self, message: str, script: str, issues: list[dict[str, Any]]):
        super().__init__(message)
        self.script = script
        self.issues = issues


# undefined-name 自动修复白名单：LLM 常把参数名当魔法变量使用（如 font_size）。
# 这些名字是 manim 的参数名而非导出名/内置名（已核实 manim 0.20.1），
# 模块级注入默认值即可消除 NameError。新增名字前需确认不在 dir(manim)/builtins。
_UNDEFINED_NAME_DEFAULTS: dict[str, int | float] = {
    "font_size": 24,
    "stroke_width": 2,
    "fill_opacity": 0.5,
    "buff": 0.3,
    "corner_radius": 0.15,
    "tab_width": 4,
    "line_spacing": 0.5,
    "run_time": 1.0,
}


def _inject_undefined_constants(code: str, issues: list[dict[str, Any]]) -> str:
    """校验器报 undefined-name 且命中白名单 → 模块级注入默认常量。

    只注入校验器明确报告、且在白名单中的名字（不猜测拼写错误，如 font_sise
    这类真 typo 留给 LLM 重试修复）。注入点选在最后一条顶层 import 之后，
    模块级可见。调用方注入后需重新校验确认。
    """
    names = sorted({
        i["name"]
        for i in issues
        if i["rule"] == "undefined-name" and i.get("name") in _UNDEFINED_NAME_DEFAULTS
    })
    if not names:
        return code

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    inject_at = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            inject_at = node.end_lineno

    lines = code.splitlines()
    header = "# ── 自动修复：注入校验器报告的未定义样式常量默认值 ──"
    const_lines = [f"{name} = {_UNDEFINED_NAME_DEFAULTS[name]}" for name in names]
    lines[inject_at:inject_at] = [header, *const_lines]
    return "\n".join(lines)


def _format_issues_with_context(issues: list[dict[str, Any]], script: str) -> str:
    """把校验错误格式化为带行号与代码上下文的文本（供 LLM 反馈 / 抛错）。"""
    lines = script.splitlines()
    parts = []
    for i in issues:
        if i["severity"] != "error":
            continue
        line_no = i.get("line")
        ctx = ""
        if line_no is not None and 0 < line_no <= len(lines):
            start = max(0, line_no - 3)
            end = min(len(lines), line_no + 2)
            snippet = "\n".join(
                f"{j + 1:4d} | {lines[j]}" for j in range(start, end)
            )
            ctx = f"，第 {line_no} 行附近：\n{snippet}"
        parts.append(f"[{i['rule']}] {i['detail']}{ctx}")
    return "\n\n".join(parts)


def _build_user_message(dsl: dict[str, Any], teaching_plan: dict[str, Any] | None) -> str:
    """构建发送给 LLM 的上下文消息。"""
    compact_frames = []
    for f in dsl.get("frames", []):
        cf: dict[str, Any] = {
            "frame_id": f.get("frame_id", ""),
            "title": f.get("title", ""),
            "narration": f.get("narration", ""),
        }
        # 包含 state_snapshot（算法状态数据，对可视化至关重要）
        snap = f.get("state_snapshot", {})
        if snap:
            cf["state_snapshot"] = snap

        # 精简 visual_objects：保留全部 14 种 VisualObject 的结构字段（对齐 schema/dsl.py:175-275），
        # LLM 自主决定如何使用。白名单而非黑名单，避免 style.extras 等自由 JSON 噪声泄漏。
        vos = []
        for vo in f.get("visual_objects", []):
            vos.append({
                k: v for k, v in vo.items()
                if k in ("id", "type", "label", "position", "style",
                         # node
                         "node_type",
                         # edge（图结构数据：边/权重，缺了 LLM 无法还原图）
                         "source", "target", "directed", "weight",
                         # array / linked_list / tree / graph / table / memory_block / timeline / mindmap
                         "cells", "nodes", "root_id", "edges", "graph_edges",
                         "headers", "rows", "blocks", "events",
                         "root", "children",
                         # code_block / formula / card
                         "code", "language", "highlight_lines", "latex",
                         "title", "content", "category",
                         # process
                         "pid", "state", "attributes",
                         # 兼容历史字段
                         "values")
            })
        cf["visual_objects"] = vos

        # 精简 animations
        anis = []
        for a in f.get("animations", []):
            anis.append({
                k: v for k, v in a.items()
                if k in ("type", "target", "target_2", "duration_ms",
                         "from_value", "to_value")
            })
        cf["animations"] = anis
        compact_frames.append(cf)

    input_data: dict[str, Any] = {
        "topic": dsl.get("topic", ""),
        "total_frames": len(compact_frames),
        "frames": compact_frames,
    }
    if teaching_plan:
        input_data["teaching_plan"] = {
            "objectives": teaching_plan.get("objectives", []),
            "approach": teaching_plan.get("teaching_approach", ""),
            "outline": teaching_plan.get("outline", []),
            "audience": teaching_plan.get("target_audience_level", "undergraduate"),
        }

    return json.dumps(input_data, ensure_ascii=False, indent=2)


async def convert_dsl_to_manim_llm(
    dsl: dict[str, Any],
    teaching_plan: dict[str, Any] | None = None,
) -> dict[str, str]:
    """用 LLM 将 DSL 转化为 Manim 工程文件。

     LLM 拥有完全创作自由：
     - 根据教学语义设计可视化（数组/树/链表/状态表等）
     - 自主选择配色、布局、动画节奏
     - DSL 中的 visual_objects type 仅作参考

    Returns:
        {"main.py": str, "render_config.json": str, "subtitles.srt": str}

    Raises:
        ManimCodeValidationError: LLM 调用或校验失败（携带失败脚本供调试）
    """
    from adapters.manim_validator import validate_script, has_errors

    user_message = _build_user_message(dsl, teaching_plan)

    from agents.llm_client import call_llm

    last_empty_reason = ""
    for attempt in range(2):
        response = await call_llm(
            system_prompt=MANIM_CODER_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.3,
            max_tokens=16384,
            routing_key="manim",
            # DeepSeek 新版默认 thinking 模式：flash 模型在长代码生成上会耗尽
            # token 预算，返回空 content 或超时；关闭后生成快且确定
            disable_thinking=True,
        )

        raw = response.get("content") or ""
        if not raw:
            # 空内容：占用一次重试机会，并记录 finish_reason/refusal 诊断
            finish_reason = response.get("finish_reason") or "unknown"
            refusal = (response.get("refusal") or "").strip()
            last_empty_reason = f"finish_reason={finish_reason}"
            if refusal:
                last_empty_reason += f", refusal={refusal[:200]}"
            logger.warning(
                "LLM 返回空内容 (attempt %d): %s", attempt + 1, last_empty_reason
            )
            continue

        main_py = _extract_python_code(raw)
        main_py = "\n".join(line.rstrip() for line in main_py.split("\n"))

        # ── 自动修正 ──
        main_py = re.sub(r"\bCode\(\s*code\s*=\s*", "Code(code_string=", main_py)
        main_py = _strip_code_text_style_kwargs(main_py)
        main_py = _fix_code_object_access(main_py)
        main_py = _fix_set_stroke_args(main_py)
        main_py = _fix_code_indexing(main_py)
        main_py = _fix_camera_animate(main_py)
        main_py = _fix_empty_fadeout(main_py)
        main_py = _fix_scene_methods(main_py)
        for bad in ("pseudocode", "plaintext", "csharp", "typescript", "go", "rust"):
            main_py = main_py.replace(f"language='{bad}'", "language='text'")
            main_py = main_py.replace(f'language="{bad}"', 'language="text"')

        # ── 校验 ──
        issues = validate_script(main_py)
        if has_errors(issues):
            # 自动修复：undefined-name 命中白名单 → 模块级注入默认常量后复检
            patched = _inject_undefined_constants(main_py, issues)
            if patched != main_py:
                main_py = patched
                issues = validate_script(main_py)
        if not has_errors(issues):
            if issues:
                for i in issues:
                    logger.info("LLM 代码 warn: [%s] %s", i["rule"], i["detail"])
            break  # 通过

        if attempt == 0:
            # 将错误反馈给 LLM 重试一次（带行号与代码上下文，便于定位修复）
            error_detail = _format_issues_with_context(issues, main_py)
            logger.warning("LLM 代码校验失败，重试:\n%s", error_detail)
            user_message = (
                f"你上一次生成的代码未通过语法校验，错误如下：\n{error_detail}\n\n"
                f"（行号对应代码修复后的脚本；请按代码片段定位并修复。"
                f"注意：模块级辅助函数必须自包含，不能引用 construct 内部的"
                f"局部变量，样式常量应定义在模块级。）\n\n"
                f"请仔细检查并修复这些错误，重新生成完整的 Manim 代码。\n\n"
                f"原始任务：\n{user_message}"
            )
        else:
            detail = _format_issues_with_context(issues, main_py)
            raise ManimCodeValidationError(
                f"LLM 生成的代码校验未通过（重试后仍失败）:\n{detail}",
                main_py,
                issues,
            )
    else:
        # 两次调用均无内容（正常成功/校验失败路径已 break/raise，走不到这里）
        raise RuntimeError(
            f"LLM 返回空内容，无法生成 Manim 代码（{last_empty_reason or '两次调用均无输出'}）"
        )

    config = generate_render_config(dsl)
    subtitles = generate_subtitles_srt(dsl)

    logger.info("LLM 生成 Manim 代码: %d 字符", len(main_py))

    return {
        "main.py": main_py,
        "render_config.json": json.dumps(config, ensure_ascii=False, indent=2),
        "subtitles.srt": subtitles,
    }
