"""Manim LLM Adapter 确定性测试（mock call_llm，不调用真实 LLM）。

覆盖 convert_dsl_to_manim_llm 的完整管线：
- auto-fix 正则（font_size 剥离范围、Code API 等）
- undefined-name 白名单常量自动注入
- 重试循环与带行号/上下文的错误反馈
- 校验失败时的 ManimCodeValidationError（携带脚本与 issues，供落盘调试）

运行环境无需 manim（CI 使用静态名称回退表，行为与本地一致）。
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from adapters.manim_llm_adapter import (
    ManimCodeValidationError,
    _CODE_TEXT_STYLE_KWARGS,
    _fix_code_indexing,
    _fix_code_object_access,
    _format_issues_with_context,
    _inject_undefined_constants,
    _strip_code_text_style_kwargs,
    convert_dsl_to_manim_llm,
)
from adapters.manim_validator import has_errors, validate_script

# ── 测试脚本 ────────────────────────────────────────────────

GOOD_SCRIPT = """from manim import *

FONT_SIZE = 24

class DemoScene(Scene):
    def construct(self):
        t = Text("hello", font_size=FONT_SIZE, color=WHITE)
        self.play(FadeIn(t))
        self.wait(0.5)
"""

# 真实失败模式的复刻：模块级辅助函数引用未定义的 font_size
FONT_SIZE_BUG_SCRIPT = """from manim import *

def make_table(headers):
    labels = [Text(h, font_size=font_size) for h in headers]
    return VGroup(*labels)

def make_info(label):
    return Text(label, font_size=font_size)

class DemoScene(Scene):
    def construct(self):
        self.add(make_table(["A", "B"]))
        self.add(make_info("info"))
"""

# 真实失败模式的另一种形态：font_size 定义在 construct 内部，
# 模块级函数引用（作用域不可见，同样 NameError）
FONT_SIZE_LOCAL_IN_CONSTRUCT = """from manim import *

def make_table(headers):
    return Text(str(headers), font_size=font_size)

class DemoScene(Scene):
    def construct(self):
        font_size = 30
        self.add(make_table(["A"]))
"""

# 真实失败模式的复刻：Code() 传了 font_size=font_size（font_size 是函数参数，
# 名字有绑定不触发 undefined-name，但 Code 不接受该参数 → 渲染期 TypeError）
CODE_FONT_SIZE_PARAM_SCRIPT = """from manim import *

FONT_SIZE = 24

def make_code_block(code_string, font_size=FONT_SIZE - 4):
    code = Code(
        code_string=code_string,
        language="python",
        tab_width=4,
        font_size=font_size,
    )
    return code

class DemoScene(Scene):
    def construct(self):
        self.add(make_code_block("for i in range(3):\\n    print(i)"))
"""

# 真实失败模式的复刻：LLM 幻觉 code.code_block 属性（manim 0.20 Code 没有该属性，
# 真实 API 是 code.code_lines / code.background），渲染期 AttributeError
CODE_BLOCK_ATTR_SCRIPT = """from manim import *

HIGHLIGHT_COLOR = "#F4D03F"

def make_code_block(code_string, highlight_lines=None):
    highlight_lines = highlight_lines or []
    code = Code(
        code_string=code_string,
        language="python",
        tab_width=4,
        add_line_numbers=False,
        background="window",
    )
    code.scale(0.8)
    for line_num in highlight_lines:
        if 1 <= line_num <= len(code.code_block[1]):
            line = code.code_block[1][line_num - 1]
            line.set_color(HIGHLIGHT_COLOR)
    return code

class DemoScene(Scene):
    def construct(self):
        self.add(make_code_block("for i in range(3):\\n    print(i)", highlight_lines=[1]))
"""

# 真实失败模式的复刻：LLM 顺着「字号由 font 控制」的旧提示给 Code 传 font=
# （manim 0.20 Code.__init__ 没有 font 参数 → 渲染期 TypeError）
CODE_FONT_PARAM_SCRIPT = """from manim import *

CODE_FONT = "Monospace"

def make_code_block(code_str):
    code = Code(
        code_string=code_str,
        language="python",
        tab_width=4,
        add_line_numbers=False,
        background="window",
        font=CODE_FONT,
    )
    return code

class DemoScene(Scene):
    def construct(self):
        self.add(make_code_block("for i in range(3):\\n    print(i)"))
"""

# 拼写错误（font_sise 不在自动修复白名单）→ 必须走 LLM 重试
TYPO_SCRIPT = """from manim import *

class DemoScene(Scene):
    def construct(self):
        t = Text("hello", font_size=font_sise)
        self.add(t)
"""

SYNTAX_ERROR_SCRIPT = """from manim import *

class DemoScene(Scene):
    def construct(self):
        self.add(Text("x")
"""


def _minimal_dsl() -> dict:
    return {"topic": "Test Topic", "frames": []}


def _mock_call_llm(mocker, responses: list[dict]):
    """mock agents.llm_client.call_llm 按序返回 responses。"""
    mock = AsyncMock(side_effect=responses)
    return mocker.patch("agents.llm_client.call_llm", mock)


# ── 成功路径 ────────────────────────────────────────────────


class TestSuccessPath:
    async def test_valid_script_returns_artifacts(self, mocker):
        _mock_call_llm(mocker, [{"content": f"```python\n{GOOD_SCRIPT}\n```"}])
        files = await convert_dsl_to_manim_llm(_minimal_dsl())

        assert set(files) == {"main.py", "render_config.json", "subtitles.srt"}
        assert not has_errors(validate_script(files["main.py"]))

    async def test_auto_injects_undefined_font_size(self, mocker):
        """白名单命中：font_size 自动注入模块级常量，无需 LLM 重试。"""
        mock = _mock_call_llm(mocker, [{"content": FONT_SIZE_BUG_SCRIPT}])
        files = await convert_dsl_to_manim_llm(_minimal_dsl())

        assert mock.await_count == 1, "自动修复应一次通过，不需要重试"
        main_py = files["main.py"]
        assert "font_size = 24" in main_py
        assert not has_errors(validate_script(main_py))

    async def test_auto_inject_resolves_construct_local_shadow(self, mocker):
        """construct 内部定义了 font_size、模块级函数引用 → 注入后一致可用。"""
        _mock_call_llm(mocker, [{"content": FONT_SIZE_LOCAL_IN_CONSTRUCT}])
        files = await convert_dsl_to_manim_llm(_minimal_dsl())
        assert not has_errors(validate_script(files["main.py"]))
        assert "font_size = 24" in files["main.py"]

    async def test_retry_recovers_with_good_second_attempt(self, mocker):
        """第一次语法错误 → 反馈重试 → 第二次成功。"""
        mock = _mock_call_llm(mocker, [
            {"content": SYNTAX_ERROR_SCRIPT},
            {"content": GOOD_SCRIPT},
        ])
        files = await convert_dsl_to_manim_llm(_minimal_dsl())
        assert mock.await_count == 2
        assert not has_errors(validate_script(files["main.py"]))

    async def test_code_font_size_param_auto_fixed(self, mocker):
        """回归：Code(font_size=函数参数) 渲染期 TypeError → strip 自动移除。"""
        mock = _mock_call_llm(mocker, [{"content": CODE_FONT_SIZE_PARAM_SCRIPT}])
        files = await convert_dsl_to_manim_llm(_minimal_dsl())

        assert mock.await_count == 1, "自动修复应一次通过"
        main_py = files["main.py"]
        assert "font_size=font_size" not in main_py, "Code 的 font_size kwarg 应被剥离"
        assert not has_errors(validate_script(main_py))

    async def test_code_block_attr_hallucination_auto_fixed(self, mocker):
        """回归：code.code_block 属性幻觉（渲染期 AttributeError）→ 自动重写为 code_lines。"""
        mock = _mock_call_llm(mocker, [{"content": CODE_BLOCK_ATTR_SCRIPT}])
        files = await convert_dsl_to_manim_llm(_minimal_dsl())

        assert mock.await_count == 1, "自动修复应一次通过"
        main_py = files["main.py"]
        assert ".code_block" not in main_py, "code_block 属性访问应被重写"
        assert "code.code_lines[line_num - 1]" in main_py
        assert not has_errors(validate_script(main_py))

    async def test_code_font_param_auto_fixed(self, mocker):
        """回归：Code(font=CODE_FONT) 渲染期 TypeError → 整体剥离 Text 样式参数。"""
        mock = _mock_call_llm(mocker, [{"content": CODE_FONT_PARAM_SCRIPT}])
        files = await convert_dsl_to_manim_llm(_minimal_dsl())

        assert mock.await_count == 1, "自动修复应一次通过"
        main_py = files["main.py"]
        assert "font=CODE_FONT" not in main_py, "Code 的 font kwarg 应被剥离"
        assert not has_errors(validate_script(main_py))


# ── 失败路径 ────────────────────────────────────────────────


class TestFailurePath:
    async def test_unfixable_typo_raises_with_script_and_context(self, mocker):
        """拼写错误不在白名单：重试后仍失败，异常携带脚本 + 行号上下文。"""
        mock = _mock_call_llm(mocker, [
            {"content": TYPO_SCRIPT},
            {"content": TYPO_SCRIPT},
        ])
        with pytest.raises(ManimCodeValidationError) as exc_info:
            await convert_dsl_to_manim_llm(_minimal_dsl())

        exc = exc_info.value
        assert mock.await_count == 2, "应恰好重试一次"
        assert "font_sise" in str(exc)
        assert "第 5 行" in str(exc), "错误消息应包含行号"
        # 管线会对原始响应做 strip/规范化，内容应与原始脚本一致
        assert exc.script == TYPO_SCRIPT.strip(), "异常应携带失败脚本（供落盘调试）"
        assert exc.issues, "异常应携带校验问题列表"

    async def test_retry_feedback_includes_line_and_context(self, mocker):
        """第二次调用的 user_message 必须带行号与代码片段。"""
        mock = _mock_call_llm(mocker, [
            {"content": TYPO_SCRIPT},
            {"content": TYPO_SCRIPT},
        ])
        with pytest.raises(ManimCodeValidationError):
            await convert_dsl_to_manim_llm(_minimal_dsl())

        feedback = mock.await_args_list[1].kwargs["user_message"]
        assert "font_sise" in feedback
        assert "第 5 行" in feedback
        assert "font_size=font_sise" in feedback, "反馈应包含出错行代码片段"

    async def test_empty_response_retries_then_raises_with_diagnostics(self, mocker):
        """空内容占用重试机会，最终报错带 finish_reason 诊断。"""
        mock = _mock_call_llm(mocker, [
            {"content": "", "finish_reason": "length"},
            {"content": None, "finish_reason": "content_filter", "refusal": "policy"},
        ])
        with pytest.raises(RuntimeError, match="LLM 返回空内容") as exc_info:
            await convert_dsl_to_manim_llm(_minimal_dsl())

        assert mock.await_count == 2, "空内容应先重试再失败"
        assert "finish_reason=content_filter" in str(exc_info.value)
        assert "refusal=policy" in str(exc_info.value)

    async def test_empty_first_then_good_recovers(self, mocker):
        """第一次空内容、第二次成功 → 恢复正常。"""
        mock = _mock_call_llm(mocker, [
            {"content": "", "finish_reason": "length"},
            {"content": GOOD_SCRIPT},
        ])
        files = await convert_dsl_to_manim_llm(_minimal_dsl())
        assert mock.await_count == 2
        assert not has_errors(validate_script(files["main.py"]))

    async def test_manim_call_disables_thinking(self, mocker):
        """长代码生成必须关闭 thinking 模式（否则 flash 模型耗尽预算返回空）。"""
        mock = _mock_call_llm(mocker, [{"content": GOOD_SCRIPT}])
        await convert_dsl_to_manim_llm(_minimal_dsl())
        assert mock.await_args.kwargs.get("disable_thinking") is True


# ── D: font_size 剥离作用域 ─────────────────────────────────


class TestStripCodeTextStyleKwargs:
    """_strip_code_text_style_kwargs：Code() 顶层 Text 样式参数整体剥离。"""

    def test_text_font_size_preserved(self):
        src = 'Text("x", font_size=24)'
        assert _strip_code_text_style_kwargs(src) == src

    def test_code_kwarg_stripped(self):
        src = 'Code(code_string="a", font_size=24, language="python")'
        out = _strip_code_text_style_kwargs(src)
        assert "font_size" not in out
        assert 'Code(code_string="a", language="python")' == out

    def test_code_variable_rhs_stripped(self):
        """变量 RHS（真实失败模式 font_size=font_size）同样剥离。"""
        src = 'Code(code_string="a", font_size=font_size, language="python")'
        out = _strip_code_text_style_kwargs(src)
        assert "font_size" not in out
        assert 'Code(code_string="a", language="python")' == out

    def test_code_first_position_expression_rhs(self):
        """首位参数 + 表达式 RHS（font_size=FONT_SIZE - 4）也能干净移除。"""
        src = 'Code(font_size=FONT_SIZE - 4, language="python")'
        out = _strip_code_text_style_kwargs(src)
        assert "font_size" not in out
        assert 'Code(language="python")' == out

    def test_code_multiline_real_pattern(self):
        """真实导出脚本的多行 Code 调用（font_size 为最后一个参数）。"""
        src = (
            "code = Code(\n"
            '    code_string=code_string,\n'
            '    language="python",\n'
            "    tab_width=4,\n"
            "    add_line_numbers=False,\n"
            '    background="window",\n'
            "    font_size=font_size,\n"
            ")\n"
        )
        out = _strip_code_text_style_kwargs(src)
        assert "font_size" not in out

    def test_code_string_content_preserved(self):
        """code_string 内同名文本（如 print(font_size=24)）不能被破坏。"""
        src = 'Code(code_string="for i in range(3):\\n    print(font_size=24)", font_size=24, language="python")'
        out = _strip_code_text_style_kwargs(src)
        assert "print(font_size=24)" in out, "code_string 内容应原样保留"
        assert "font_size=24, language" not in out, "Code 的 kwarg 应被剥离"

    def test_multiline_code_call_and_spaces(self):
        src = (
            'Text("t", font_size=18)\n'
            'Code(\n'
            '    code_string="x",\n'
            '    font_size = 30,\n'
            '    language="python",\n'
            ')\n'
            'Table([[1]], col_labels=[Text("h", font_size=20)])'
        )
        out = _strip_code_text_style_kwargs(src)
        assert 'Text("t", font_size=18)' in out
        assert 'Table([[1]], col_labels=[Text("h", font_size=20)])' in out
        assert "font_size = 30" not in out, "Code 多行调用的 font_size 应被剥离"

    def test_font_kwarg_stripped(self):
        """回归：LLM 顺着旧提示发明 font=（真实失败模式 font=CODE_FONT）。"""
        src = (
            "    code = Code(\n"
            '        code_string=code_str,\n'
            '        language="python",\n'
            "        tab_width=4,\n"
            "        add_line_numbers=False,\n"
            '        background="window",\n'
            "        font=CODE_FONT,\n"
            "    )\n"
        )
        out = _strip_code_text_style_kwargs(src)
        assert "font=CODE_FONT" not in out
        assert "CODE_FONT" not in out, "font 参数及其值应整体移除"
        assert 'language="python"' in out

    def test_all_text_style_params_stripped(self):
        """黑名单内的样式参数全部剥离（不再逐个撞墙）。"""
        src = (
            "Code(code_string='x', font=FONT, font_size=24, color=RED, "
            "fill_color=BLUE, fill_opacity=0.5, stroke_width=2, "
            "stroke_color=WHITE, background_color=BLACK, line_spacing=1.5, "
            "slant=ITALIC, weight=BOLD, language='python')"
        )
        out = _strip_code_text_style_kwargs(src)
        assert all(f"{name}=" not in out for name in _CODE_TEXT_STYLE_KWARGS)
        assert "language='python'" in out
        assert out.startswith("Code(code_string='x',")

    def test_nested_config_preserved(self):
        """嵌套配置（paragraph_config/background_config 字典）不被破坏。"""
        src = (
            "Code(code_string='x', language='python', "
            'paragraph_config={"font_size": 18, "line_spacing": 0.8}, '
            'background_config={"stroke_color": "#333333"})'
        )
        out = _strip_code_text_style_kwargs(src)
        assert 'paragraph_config={"font_size": 18, "line_spacing": 0.8}' in out
        assert 'background_config={"stroke_color": "#333333"}' in out

    def test_text_font_preserved(self):
        """Text 的 font 参数合法，不得剥离。"""
        src = 'Text("x", font="Monospace")'
        assert _strip_code_text_style_kwargs(src) == src


# ── C: 常量注入单元测试 ─────────────────────────────────────


class TestInjectUndefinedConstants:
    def _issues(self, *names):
        return [
            {"rule": "undefined-name", "severity": "error",
             "line": 4, "name": n, "detail": f"未定义变量 '{n}'"}
            for n in names
        ]

    def test_injects_whitelisted_after_imports(self):
        script = "from manim import *\n\nclass S(Scene):\n    def construct(self):\n        pass\n"
        out = _inject_undefined_constants(script, self._issues("font_size"))
        assert "font_size = 24" in out
        assert out.index("font_size = 24") < out.index("class S"), "常量应在 class 之前"
        assert out.startswith("from manim import *\n"), "import 保留在顶部"

    def test_typo_not_injected(self):
        script = "from manim import *\n\nclass S(Scene):\n    def construct(self):\n        pass\n"
        out = _inject_undefined_constants(script, self._issues("font_sise"))
        assert out == script

    def test_dedup_same_name(self):
        script = "from manim import *\n\nclass S(Scene):\n    pass\n"
        out = _inject_undefined_constants(script, self._issues("font_size", "font_size"))
        assert out.count("font_size = 24") == 1

    def test_no_issues_no_change(self):
        script = "from manim import *\n"
        assert _inject_undefined_constants(script, []) == script


# ── B: 错误消息格式化 ───────────────────────────────────────


class TestFormatIssuesWithContext:
    def test_includes_line_and_snippet(self):
        script = "from manim import *\n\nclass S(Scene):\n    def construct(self):\n        x = font_size\n"
        issues = [{"rule": "undefined-name", "severity": "error", "line": 5,
                   "name": "font_size", "detail": "未定义变量 'font_size'"}]
        text = _format_issues_with_context(issues, script)
        assert "第 5 行附近" in text
        assert "x = font_size" in text

    def test_no_line_ok(self):
        issues = [{"rule": "x", "severity": "error", "line": None, "detail": "d"}]
        assert "[x] d" in _format_issues_with_context(issues, "abc")

    def test_warnings_excluded(self):
        issues = [
            {"rule": "w", "severity": "warn", "line": 1, "detail": "warn-msg"},
            {"rule": "e", "severity": "error", "line": 1, "detail": "err-msg"},
        ]
        text = _format_issues_with_context(issues, "a\nb")
        assert "warn-msg" not in text
        assert "err-msg" in text


# ── 连环修复：Code 属性访问幻觉（.code_block → 真实 API）───────


class TestFixCodeObjectAccess:
    """_fix_code_object_access：code.code_block 属性 → code.code_lines / background。"""

    def test_composite_index_real_pattern(self):
        """真实失败脚本形态：code.code_block[1][line_num - 1] → code.code_lines[...]。"""
        src = "line = code.code_block[1][line_num - 1]"
        out = _fix_code_object_access(src)
        assert out == "line = code.code_lines[line_num - 1]"

    def test_background_index(self):
        assert _fix_code_object_access("code.code_block[0]") == "code.background"

    def test_single_bracket_is_paragraph(self):
        """code.code_block[1]（无后续索引）→ code.code_lines。"""
        assert _fix_code_object_access("c = code.code_block[1]") == "c = code.code_lines"

    def test_single_bracket_line(self):
        """code.code_block[N]（N>=2）→ code.code_lines[N - 1]（视为第 N 行）。"""
        assert _fix_code_object_access("code.code_block[2]") == "code.code_lines[2 - 1]"

    def test_bare_attribute(self):
        """len(code.code_block) → len(code.code_lines)。"""
        assert _fix_code_object_access("len(code.code_block)") == "len(code.code_lines)"

    def test_dot_code_patterns_preserved(self):
        """原有 .code 修复不回归。"""
        src = "code_block.code.set_color(YELLOW)"
        assert "for _cl in code_block: _cl.set_color(" in _fix_code_object_access(src)
        assert _fix_code_object_access("len(x.code)") == "len(x)"
        assert _fix_code_object_access("x.code[1]") == "x[1]"

    def test_string_content_not_touched(self):
        """code_string 内的 .code_block 文本不能被改写。"""
        src = 'Code(code_string="a.code_block", code_string2="x")'
        assert _fix_code_object_access(src) == src


class TestFixCodeIndexing:
    """_fix_code_indexing：变量直接索引（code_block[2]）→ .code_lines[N-1]。"""

    def test_line_index(self):
        assert _fix_code_indexing("code_block[3]") == "code_block.code_lines[2]"

    def test_background_index(self):
        assert _fix_code_indexing("code_obj[0]") == "code_obj.background"

    def test_composite_legacy_pattern(self):
        """旧教学形态 code_block[1][N] → code_block.code_lines[N]。"""
        assert _fix_code_indexing("code_block[1][2]") == "code_block.code_lines[2]"

    def test_unrelated_names_untouched(self):
        assert _fix_code_indexing("arr[2]") == "arr[2]"
