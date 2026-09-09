"""Golden fixture: 数组/排序可视化（array）。不含 LaTeX 与 CJK。"""

from manim import *

FONT_SIZE = 24


class ArraySortScene(Scene):
    def construct(self):
        self.camera.background_color = "#1A1A2E"
        values = [5, 3, 8, 1]
        boxes = VGroup()
        for v in values:
            box = Square(side_length=0.7, color="#5DADE2", fill_opacity=0.3)
            lbl = Text(str(v), font_size=FONT_SIZE, color=WHITE).move_to(box)
            boxes.add(VGroup(box, lbl))
        boxes.arrange(RIGHT, buff=0.15)
        boxes.move_to(ORIGIN)

        self.play(FadeIn(boxes))
        self.play(boxes[0][0].animate.set_color("#F4D03F"))
        self.play(
            boxes[0].animate.shift(RIGHT * 0.9),
            boxes[1].animate.shift(LEFT * 0.9),
        )
        self.wait(0.5)
