"""Manim 脚本校验器 — 未定义变量检测测试。

覆盖 v0.8.1 新增的 undefined-name 检查（运行时 NameError 的静态前置检查）：
- 能抓住 LLM 生成代码中的未定义变量（如 font_size）
- 不误报合法脚本（闭包、局部变量、manim import *、numpy 别名等）
"""

from __future__ import annotations

import pytest

from adapters.manim_validator import validate_script


class TestInvalidKwargCheck:
    """invalid-kwarg 检查：LLM 把某类参数误用到另一类（如 Text 传 markdown）。"""

    def test_text_markdown_misuse_caught(self):
        script = """
from manim import *

class C(Scene):
    def construct(self):
        t = Text("hello", color="#AAAAAA", markdown=False).to_edge(DOWN)
        self.add(t)
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert any(
            i["rule"] == "invalid-kwarg" and "markdown" in i["detail"] for i in errs
        )

    def test_valid_text_and_code_markdown_ok(self):
        # Text 正常参数 + Code 的 markdown=True 是合法的
        script = """
from manim import *

class C(Scene):
    def construct(self):
        t = Text("hello", color=WHITE, font_size=24)
        c = Code(code_string="print(1)", markdown=True)
        self.add(t, c)
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert not any(i["rule"] == "invalid-kwarg" for i in errs)

    def test_code_font_size_misuse_caught(self):
        """回归：Code(font_size=...) 渲染期 TypeError（LLM 把 Text 习惯带给 Code）。"""
        script = """
from manim import *

class C(Scene):
    def construct(self):
        c = Code(code_string="print(1)", font_size=24)
        self.add(c)
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert any(
            i["rule"] == "invalid-kwarg"
            and "font_size" in i["detail"]
            and "Code" in i["detail"]
            for i in errs
        )

    def test_valid_code_call_not_flagged(self):
        # Code 只使用签名内的合法参数
        script = """
from manim import *

class C(Scene):
    def construct(self):
        c = Code(code_string="print(1)", language="python", tab_width=4,
                 add_line_numbers=False, background="window")
        self.add(c)
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert not any(i["rule"] == "invalid-kwarg" for i in errs)

    def test_code_font_misuse_caught(self):
        """回归：Code(font=...) 渲染期 TypeError（LLM 顺着旧提示发明 font 参数）。"""
        script = """
from manim import *

class C(Scene):
    def construct(self):
        c = Code(code_string="print(1)", font="Monospace")
        self.add(c)
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert any(
            i["rule"] == "invalid-kwarg" and "font" in i["detail"] for i in errs
        )

    @pytest.mark.parametrize("bad_kwarg", [
        "font", "font_size", "color", "fill_opacity", "stroke_width",
        "line_spacing", "weight", "slant",
    ])
    def test_code_text_style_kwargs_all_caught(self, bad_kwarg):
        """Code 不接受任何 Text 样式参数——黑名单内全部拦截。"""
        script = f"""
from manim import *

class C(Scene):
    def construct(self):
        c = Code(code_string="print(1)", {bad_kwarg}=1)
        self.add(c)
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert any(
            i["rule"] == "invalid-kwarg" and bad_kwarg in i["detail"] for i in errs
        )


class TestCodeBlockAttrCheck:
    """code-block-attr 检查：Code 对象没有 .code_block 属性（渲染期 AttributeError）。"""

    def test_code_block_attr_caught(self):
        script = """
from manim import *

class C(Scene):
    def construct(self):
        c = Code(code_string="print(1)")
        line = c.code_block[1][0]
        line.set_color(YELLOW)
        self.add(c)
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert any(
            i["rule"] == "code-block-attr" and "code_lines" in i["detail"] for i in errs
        )

    def test_subscript_base_caught(self):
        """fixer 覆盖不到的形态（code[0].code_block）也能拦截。"""
        script = """
from manim import *

class C(Scene):
    def construct(self):
        c = Code(code_string="print(1)")
        x = c[0].code_block
        self.add(x)
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert any(i["rule"] == "code-block-attr" for i in errs)

    def test_code_lines_ok(self):
        """真实 API code.code_lines 不应误报。"""
        script = """
from manim import *

class C(Scene):
    def construct(self):
        c = Code(code_string="print(1)")
        for line in c.code_lines:
            line.set_color(YELLOW)
        c.background.set_color(BLUE)
        self.add(c)
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert not any(i["rule"] == "code-block-attr" for i in errs)

    def test_string_content_not_flagged(self):
        """code_string 内容里出现 .code_block 文本不应误报。"""
        script = '''
from manim import *

class C(Scene):
    def construct(self):
        c = Code(code_string="print(code.code_block)")  # 字符串内的文本
        self.add(c)
'''
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert not any(i["rule"] == "code-block-attr" for i in errs)


class TestUndefinedNameCheck:
    """undefined-name 检查的正反用例。"""

    def test_catches_undefined_name(self):
        script = """
from manim import *

class DemoScene(Scene):
    def construct(self):
        def make_array(values):
            boxes = VGroup()
            for v in values:
                box = Square(side_length=0.7)
                txt = Text(str(v), font_size=font_size)  # font_size 未定义
                boxes.add(VGroup(box, txt))
            return boxes
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert any(i["rule"] == "undefined-name" and "font_size" in i["detail"] for i in errs)

    def test_no_false_positive_on_valid_script(self):
        script = """
from manim import *
import numpy as np

class DemoScene(Scene):
    def construct(self):
        width = 2
        def make_array(values, side=0.7):
            boxes = VGroup()
            font = 24
            for v in values:
                box = Square(side_length=side, color=BLUE)
                txt = Text(str(v), font_size=font, color=WHITE)
                boxes.add(VGroup(box, txt))
            return boxes

        arr = make_array([1, 2, 3])
        arr.move_to(ORIGIN)
        self.add(arr)
        for i in range(len(arr)):
            self.play(arr[i].animate.set_color(YELLOW))
        np.zeros(2)
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert not any(i["rule"] == "undefined-name" for i in errs)

    def test_comprehension_and_lambda_no_false_positive(self):
        """推导式循环变量与 lambda 参数是绑定，不应误报（回归：v in [f(v) for v in xs]）。"""
        script = """
from manim import *

class Demo(Scene):
    def construct(self):
        def create_array(values):
            def make_cell(v):
                return Square(side_length=v)
            return VGroup(*[make_cell(v) for v in values])
        f = lambda x: x * 2
        g = {k: k + 1 for k in [1, 2]}
        h = (y for y in [3, 4])
        self.add(create_array([1, 2, 3]))
        self.add(Text(str(f(3) + sum(g.values()) + sum(h))))
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert not any(i["rule"] == "undefined-name" for i in errs)

    def test_closure_reference_no_false_positive(self):
        script = """
from manim import *

class C(Scene):
    def construct(self):
        width = 2
        def helper():
            return width * 2
        self.add(Square(side_length=helper()))
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert not any(i["rule"] == "undefined-name" for i in errs)

    def test_method_self_and_class_level_names(self):
        script = """
from manim import *

class C(Scene):
    colors = [BLUE, YELLOW]
    def construct(self):
        for c in self.colors:
            self.add(Square(color=c))
        self.play(FadeOut(self.mobjects))
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert not any(i["rule"] == "undefined-name" for i in errs)

    def test_real_failed_script_detected(self):
        """回归用例：用户导出失败的真实脚本（NameError: font_size is not defined）。"""
        script = """
from manim import *

class BubbleSortScene(Scene):
    def construct(self):
        def make_array(values, side=0.7):
            boxes = VGroup()
            for v in values:
                box = Square(side_length=side, color="#5DADE2")
                txt = Text(str(v), font_size=font_size, color="#E0E0E0")
                boxes.add(VGroup(box, txt))
            return boxes

        arr = make_array([5, 3, 8, 1])
        self.add(arr)
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert any(i["rule"] == "undefined-name" and "font_size" in i["detail"] for i in errs)

    @pytest.mark.parametrize("builtin_name", [
        "len", "range", "str", "int", "min", "max", "sum", "abs", "print",
    ])
    def test_builtins_not_reported(self, builtin_name):
        script = f"""
from manim import *

class C(Scene):
    def construct(self):
        x = {builtin_name}([1, 2, 3]) if {builtin_name} else None
        self.add(Text(str(x)))
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert not any(i["rule"] == "undefined-name" for i in errs)


class TestUnknownSceneMethodCheck:
    """unknown-scene-method 检查：LLM 幻觉的 Scene 方法名（如 clear_current）。"""

    def test_clear_current_caught(self):
        script = """
from manim import *

class DemoScene(Scene):
    def construct(self):
        t = Text("hello")
        self.clear_current()
        self.play(FadeIn(t))
"""
        issues = validate_script(script)
        errs = [i for i in issues if i["severity"] == "error"]
        assert any(
            i["rule"] == "unknown-scene-method" and "clear_current" in i["detail"]
            for i in errs
        )

    def test_valid_scene_methods_ok(self):
        script = """
from manim import *

class DemoScene(Scene):
    def construct(self):
        t = Text("hello")
        self.play(FadeIn(t))
        self.wait(1)
        self.clear()
"""
        issues = validate_script(script)
        assert not any(i["rule"] == "unknown-scene-method" for i in issues)

    def test_class_defined_method_ok(self):
        script = """
from manim import *

class DemoScene(Scene):
    def make_header(self, text):
        return Text(text).to_edge(UP)

    def construct(self):
        self.add(self.make_header("title"))
"""
        issues = validate_script(script)
        assert not any(i["rule"] == "unknown-scene-method" for i in issues)

    def test_non_scene_class_ignored(self):
        script = """
from manim import *

class Helper:
    def work(self):
        self.internal_call()

class DemoScene(Scene):
    def construct(self):
        Helper().work()
"""
        issues = validate_script(script)
        assert not any(i["rule"] == "unknown-scene-method" for i in issues)
