"""Golden fixture: 数学公式（formula，Unicode 符号，无 LaTeX）。不含 CJK。"""

from manim import *


class FormulaUnicodeScene(Scene):
    def construct(self):
        self.camera.background_color = "#1A1A2E"
        e = Text("E = mc²", font_size=48, color="#F4D03F")
        steps = Text("α + β = γ", font_size=36, color="#E0E0E0")
        steps.next_to(e, DOWN, buff=0.8)
        self.play(Write(e))
        self.play(FadeIn(steps))
        self.wait(0.5)
