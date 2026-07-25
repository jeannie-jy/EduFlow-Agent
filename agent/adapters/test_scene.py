"""极简 Manim 测试场景 — 用于验证渲染管线，5 秒内可渲染完成。"""

from manim import *


class TestPreview(Scene):
    def construct(self):
        title = Text("EduFlow 视频预览", font_size=48, color=BLUE)
        subtitle = Text("渲染管线已就绪", font_size=28, color=WHITE)
        subtitle.next_to(title, DOWN, buff=0.5)

        self.play(Write(title), run_time=1)
        self.play(FadeIn(subtitle), run_time=0.8)
        self.wait(1)
        self.play(FadeOut(title), FadeOut(subtitle), run_time=0.5)
