"""Golden fixture: 状态表/变量跟踪（table）。不含 LaTeX 与 CJK。"""

from manim import *


class TableStateScene(Scene):
    def construct(self):
        self.camera.background_color = "#1A1A2E"
        headers = [Text("Step", font_size=22), Text("Value", font_size=22)]
        table = Table(
            [["1", "5"], ["2", "3"], ["3", "8"]],
            col_labels=headers,
            include_outer_lines=True,
        )
        table.scale(0.8)
        self.play(FadeIn(table))
        self.wait(0.5)
