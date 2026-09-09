"""Golden fixture: 图结构/流程图（graph）。不含 LaTeX 与 CJK。"""

from manim import *


class GraphFlowScene(Scene):
    def construct(self):
        self.camera.background_color = "#1A1A2E"
        nodes = VGroup()
        positions = [LEFT * 3, ORIGIN, RIGHT * 3]
        labels = ["A", "B", "C"]
        for label, pos in zip(labels, positions):
            c = Circle(radius=0.4, color="#5DADE2", fill_opacity=0.2)
            t = Text(label, font_size=24, color=WHITE).move_to(c)
            nodes.add(VGroup(c, t).move_to(pos))
        edge1 = Arrow(nodes[0].get_right(), nodes[1].get_left(), color="#AED6F1", stroke_width=3)
        edge2 = Arrow(nodes[1].get_right(), nodes[2].get_left(), color="#AED6F1", stroke_width=3)
        self.play(FadeIn(nodes), FadeIn(edge1), FadeIn(edge2))
        self.wait(0.5)
