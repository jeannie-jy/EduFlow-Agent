from adapters.manim_validator import has_errors, validate_teaching_contract


def _rules(script: str, **kwargs) -> set[str]:
    return {
        issue["rule"]
        for issue in validate_teaching_contract(script, **kwargs)
    }


def test_contract_accepts_clean_sections_and_bounded_subtitle():
    script = """
from manim import *
class Demo(Scene):
    def construct(self):
        self.next_section(name="one")
        subtitle_text = Text("one")
        subtitle_text.scale_to_fit_width(11.8)
        subtitle = VGroup(BackgroundRectangle(subtitle_text), subtitle_text)
        self.play(FadeOut(*self.mobjects))
        self.next_section(name="two")
        self.add(Text("two"))
"""

    issues = validate_teaching_contract(
        script,
        expected_frames=2,
        include_subtitles=True,
        has_narration=True,
    )

    assert not has_errors(issues)


def test_contract_rejects_missing_sections_cleanup_and_subtitle_bounds():
    script = """
from manim import *
class Demo(Scene):
    def construct(self):
        self.next_section(name="one")
        self.add(Text("one"))
        self.next_section(name="two")
        subtitle = Text("unbounded")
"""

    rules = _rules(
        script,
        expected_frames=3,
        include_subtitles=True,
        has_narration=True,
    )

    assert {
        "missing-frame-sections",
        "missing-frame-cleanup",
        "subtitle-background-missing",
        "subtitle-width-unbounded",
    } <= rules


def test_contract_rejects_literal_positions_outside_safe_frame():
    script = """
from manim import *
import numpy as np
class Demo(Scene):
    def construct(self):
        self.next_section(name="one")
        obj = Text("outside").move_to(np.array([7.2, -4.0, 0]))
"""

    rules = _rules(
        script,
        expected_frames=1,
        include_subtitles=False,
        has_narration=False,
    )

    assert "literal-position-out-of-bounds" in rules


def test_contract_rejects_subtitle_objects_when_disabled():
    script = """
from manim import *
class Demo(Scene):
    def construct(self):
        self.next_section(name="one")
        subtitle_text = Text("should not render")
"""

    rules = _rules(
        script,
        expected_frames=1,
        include_subtitles=False,
        has_narration=True,
    )

    assert "subtitles-disabled" in rules


def test_contract_rejects_height_fit_that_can_re_enlarge_subtitles():
    script = """
from manim import *
class Demo(Scene):
    def construct(self):
        self.next_section(name="one")
        subtitle_text = Text("already width-bounded")
        subtitle_text.scale_to_fit_width(11.4)
        subtitle_text.scale_to_fit_height(1.05)
        subtitle = VGroup(BackgroundRectangle(subtitle_text), subtitle_text)
"""

    rules = _rules(
        script,
        expected_frames=1,
        include_subtitles=True,
        has_narration=True,
    )

    assert "subtitle-upscale-risk" in rules
