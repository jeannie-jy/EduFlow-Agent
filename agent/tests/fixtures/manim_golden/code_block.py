"""Golden fixture: 代码块可视化（code_block）。不含 LaTeX 与 CJK。

覆盖真实失败模式：Code 行高亮必须用 code.code_lines[N-1].set_color()
（manim 0.20.1 真实 API；code.code_block 属性不存在 → AttributeError）。
"""

from manim import *

HIGHLIGHT_COLOR = "#F4D03F"


class CodeBlockScene(Scene):
    def construct(self):
        self.camera.background_color = "#1A1A2E"
        code = Code(
            code_string="for i in range(3):\n    print(i)",
            language="python",
            tab_width=4,
            add_line_numbers=False,
            background="window",
        )
        code.scale(0.9)
        # 高亮第 2 行（真实 API：code_lines 是逐行的 Paragraph）
        if 1 <= 2 <= len(code.code_lines):
            line = code.code_lines[1]
            line.set_color(HIGHLIGHT_COLOR)
        self.play(FadeIn(code))
        self.wait(0.5)
