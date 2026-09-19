"""Manim Adapter — 确定性 DSL → Manim Python 脚本转换器。

不依赖 LLM，纯规则映射。每种 VisualObject 和 Animation 有固定的 Manim 映射。

参考: Manim Community Edition v0.20+
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 运行时环境检测 ──────────────────────────────────────────

_HAS_LATEX = shutil.which("latex") is not None or shutil.which("pdflatex") is not None
if not _HAS_LATEX:
    logger.info("LaTeX 未安装，MathTex 将回退为 Text")

# ============================================================================
# 类型映射表
# ============================================================================

# VisualObject.type → Manim Mobject 类名 + 构造函数参数
MOBJECT_MAP: dict[str, dict[str, Any]] = {
    "node": {
        "class": "Circle",
        "import": "from manim import Circle, Text, VGroup",
        "args": "{size}",
        "needs_label": True,
    },
    "edge": {
        "class": "Arrow",  # 默认为 Arrow，在 _generate_objects_for_frame 中根据 directed 字段决定
        "class_undirected": "Line",
        "import": "from manim import Arrow, Line, Text",
        "args": "",
        "needs_label": True,
    },
    "array": {
        "class": "Rectangle",
        "import": "from manim import Rectangle, Text, VGroup",
        "args": "",
        "needs_label": True,
    },
    "linked_list": {
        "class": "Rectangle",
        "import": "from manim import Rectangle, Arrow, Text, VGroup",
        "args": "",
        "needs_label": True,
    },
    "tree": {
        "class": "Circle",
        "import": "from manim import Circle, Line, Text, VGroup",
        "args": "{size}",
        "needs_label": True,
    },
    "graph": {
        "class": "Graph",
        "import": "from manim import Graph, Text",
        "args": "",
        "needs_label": False,  # Graph 自带标签
    },
    "table": {
        "class": "Table",
        "import": "from manim import Table, Text",
        "args": "",
        "needs_label": False,  # Table 自带内容
    },
    "code_block": {
        "class": "Code",
        "import": "from manim import Code",
        "args": 'code_string="...", language="{language}"',
        "needs_label": False,
    },
    "memory_block": {
        "class": "Rectangle",
        "import": "from manim import Rectangle, Text, VGroup",
        "args": "",
        "needs_label": True,
    },
    "process": {
        "class": "Rectangle",
        "import": "from manim import Rectangle, Text, VGroup",
        "args": "color=BLUE, fill_opacity=0.3",
        "needs_label": True,
    },
    "timeline": {
        "class": "NumberLine",
        "import": "from manim import NumberLine, Text, Dot",
        "args": "",
        "needs_label": False,
    },
    "formula": {
        "class": "MathTex",
        "import": "from manim import MathTex",
        "args": 'r"{latex}"',
        "needs_label": False,
    },
    "card": {
        "class": "RoundedRectangle",
        "import": "from manim import RoundedRectangle, Text, VGroup",
        "args": "corner_radius=0.2",
        "needs_label": True,
    },
    "mindmap": {
        "class": "VGroup",
        "import": "from manim import Circle, Text, VGroup, Line",
        "args": "",
        "needs_label": False,
    },
}

# Animation.type → Manim Animation 类名
ANIMATION_MAP: dict[str, str] = {
    "appear": "FadeIn",
    "disappear": "FadeOut",
    "highlight": "Indicate",  # Indicate 是 Manim 的高亮闪烁动画
    # Transform requires both a source and a destination mobject.  The DSL
    # currently carries only one target for these semantic operations, so use
    # a safe emphasis animation instead of emitting invalid Transform(obj).
    "transform": "Indicate",
    "move": "animate.move_to",
    "update_value": "Transform",  # 值变化用 Transform + 新对象
    # AnimationGroup accepts Animation instances, not a raw Mobject.
    "compare": "Indicate",
    "swap": "CyclicReplace",  # 交换位置
    "relax_edge": "Indicate",  # 边权重变化（无目标值时安全强调）
    "enqueue": "FadeIn",
    "dequeue": "FadeOut",
    "split": "Indicate",
    "merge": "Indicate",
    "schedule": "FadeIn",
    "lock": "FadeIn",  # 锁定图标出现
    "unlock": "FadeOut",  # 锁定图标消失
}

# 动画需要额外导入的类
ANIMATION_IMPORTS: dict[str, str] = {
    "appear": "FadeIn",
    "disappear": "FadeOut",
    "highlight": "Indicate",
    "transform": "Indicate",
    "compare": "Indicate",
    "swap": "CyclicReplace",
}

# The DSL uses a 0..1000-ish canvas while Manim's default camera is 14 x 8.
# Keep these values in one place so the generator and the deterministic layout
# audit agree on what can be visible in the final frame.
MANIM_X_LIMITS = (-7.0, 7.0)
MANIM_Y_LIMITS = (-4.0, 4.0)
MAX_GENERATED_LABEL_CHARS = 20
MAX_GENERATED_NARRATION_CHARS = 200


def _map_dsl_position(position: dict[str, Any]) -> tuple[float, float]:
    """Map a DSL canvas position to the same coordinates used by the generator."""
    raw_x = position.get("x", 0)
    raw_y = position.get("y", 0)
    if not isinstance(raw_x, (int, float)) or not isinstance(raw_y, (int, float)):
        raise ValueError("position x/y must be numbers")
    if not math.isfinite(float(raw_x)) or not math.isfinite(float(raw_y)):
        raise ValueError("position x/y must be finite")
    return float(raw_x) / 100.0 - 3.0, (float(raw_y) / 100.0 - 2.0) * -1


def _estimated_object_bounds(
    visual_object: dict[str, Any],
    center: tuple[float, float],
) -> tuple[float, float, float, float]:
    """Return a conservative Manim bounding box for a generated object.

    This is intentionally an estimate rather than a renderer-dependent pixel
    measurement. It catches layout regressions before a costly render while
    keeping the rule deterministic in CI environments without Manim installed.
    """
    obj_type = str(visual_object.get("type", "node"))
    style = visual_object.get("style") or {}
    size = style.get("size", 30)
    try:
        radius = max(0.25, min(2.5, float(size) / 30.0 * 0.5))
    except (TypeError, ValueError):
        radius = 0.5

    half_width, half_height = radius, radius
    if obj_type == "edge":
        half_width, half_height = 2.2, 0.35
    elif obj_type in {"process", "card", "memory_block"}:
        half_width, half_height = 1.1, 0.55
    elif obj_type in {"table", "array", "linked_list", "timeline"}:
        headers = visual_object.get("headers") or []
        rows = visual_object.get("rows") or visual_object.get("cells") or []
        columns = max([len(headers), *(len(row) for row in rows if isinstance(row, list)), 1])
        half_width = min(5.8, max(1.0, columns * 0.45))
        half_height = min(3.0, max(0.45, (len(rows) + 1) * 0.3))
    elif obj_type == "code_block":
        code = str(visual_object.get("code", ""))
        longest_line = max((len(line) for line in code.splitlines()), default=1)
        half_width = min(6.0, max(1.0, longest_line * 0.045))
        half_height = min(3.2, max(0.45, len(code.splitlines()) * 0.12))
    elif obj_type == "formula":
        formula = str(visual_object.get("latex", ""))
        half_width = min(6.0, max(0.6, len(formula) * 0.045))
        half_height = 0.45

    label = str(visual_object.get("label") or "")
    if label:
        # Labels are emitted below/above the mobject. Include a small text box
        # so an otherwise in-bounds object is still flagged when its label is
        # likely to be clipped.
        half_width = max(half_width, min(4.0, max(0.5, len(label) * 0.055)))
        half_height += 0.35

    x, y = center
    return x - half_width, x + half_width, y - half_height, y + half_height


def validate_render_layout(dsl: dict[str, Any]) -> list[dict[str, Any]]:
    """Audit generated video layout without requiring Manim or a display.

    The result is intentionally structured for persistence in render_config.
    Warnings describe likely visual defects (overlap, clipping, truncation);
    malformed numeric coordinates are errors because their rendering is not
    deterministic.
    """
    issues: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(dsl.get("frames", [])):
        frame_id = str(frame.get("frame_id", f"f_{frame_index:03d}"))
        frame_issues: list[tuple[str, dict[str, Any]]] = []
        boxes: list[tuple[str, tuple[float, float, float, float]]] = []

        narration = str(frame.get("narration") or "")
        if len(narration) > MAX_GENERATED_NARRATION_CHARS:
            frame_issues.append((
                "narration-truncated",
                {
                    "severity": "warn",
                    "detail": (
                        f"narration has {len(narration)} characters; generated subtitle "
                        f"is limited to {MAX_GENERATED_NARRATION_CHARS}"
                    ),
                },
            ))

        for object_index, visual_object in enumerate(frame.get("visual_objects", [])):
            object_id = str(visual_object.get("id", f"object_{object_index}"))
            position = visual_object.get("position") or {}
            try:
                center = _map_dsl_position(position)
            except ValueError as exc:
                frame_issues.append((
                    "invalid-position",
                    {
                        "severity": "error",
                        "object_id": object_id,
                        "detail": str(exc),
                    },
                ))
                continue

            label = str(visual_object.get("label") or "")
            if len(label) > MAX_GENERATED_LABEL_CHARS:
                frame_issues.append((
                    "label-truncated",
                    {
                        "severity": "warn",
                        "object_id": object_id,
                        "detail": (
                            f"label has {len(label)} characters; generated label "
                            f"is limited to {MAX_GENERATED_LABEL_CHARS}"
                        ),
                    },
                ))

            if visual_object.get("type") == "formula":
                formula = str(visual_object.get("latex") or "")
                if len(_strip_latex(formula)) > MAX_GENERATED_NARRATION_CHARS:
                    frame_issues.append((
                        "formula-truncated",
                        {
                            "severity": "warn",
                            "object_id": object_id,
                            "detail": "formula text exceeds the generated 200-character limit",
                        },
                    ))

            box = _estimated_object_bounds(visual_object, center)
            boxes.append((object_id, box))
            if (
                box[0] < MANIM_X_LIMITS[0]
                or box[1] > MANIM_X_LIMITS[1]
                or box[2] < MANIM_Y_LIMITS[0]
                or box[3] > MANIM_Y_LIMITS[1]
            ):
                frame_issues.append((
                    "object-out-of-bounds",
                    {
                        "severity": "warn",
                        "object_id": object_id,
                        "detail": (
                            f"estimated bounds {tuple(round(value, 2) for value in box)} "
                            f"exceed the Manim frame {MANIM_X_LIMITS} x {MANIM_Y_LIMITS}"
                        ),
                    },
                ))

        for left_index, (left_id, left_box) in enumerate(boxes):
            for right_id, right_box in boxes[left_index + 1:]:
                overlap_width = min(left_box[1], right_box[1]) - max(left_box[0], right_box[0])
                overlap_height = min(left_box[3], right_box[3]) - max(left_box[2], right_box[2])
                if overlap_width > 0.05 and overlap_height > 0.05:
                    frame_issues.append((
                        "object-overlap",
                        {
                            "severity": "warn",
                            "object_id": f"{left_id},{right_id}",
                            "detail": "estimated object bounds overlap in the same frame",
                        },
                    ))

        for rule, detail in frame_issues:
            issues.append({"frame_id": frame_id, "rule": rule, **detail})
    return issues


# ============================================================================
# 脚本生成器
# ============================================================================


class ManimScriptGenerator:
    """将 RenderScript DSL 生成完整的 Manim Python 脚本。"""

    def __init__(self, dsl: dict[str, Any]):
        self.dsl = dsl
        self.project_id = dsl.get("project_id", "unknown")
        self.topic = dsl.get("topic", "EduFlow Export")
        self.frames = dsl.get("frames", [])

    def generate(self) -> str:
        """生成完整的 Manim 脚本字符串。"""
        imports = self._collect_imports()
        scene_class = self._generate_scene_class()
        return imports + "\n\n" + scene_class

    def _collect_imports(self) -> str:
        """收集所有需要的 import 语句。"""
        lines = [
            "#!/usr/bin/env python3",
            '"""Auto-generated Manim script by EduFlow-Agent."""',
            f"# Project: {self.project_id}",
            f"# Topic: {self.topic}",
            f"# Generated: {datetime.now(UTC).isoformat()}",
            f"# Frames: {len(self.frames)}",
            "",
            "from manim import *",
            "import json",
            "",
            '# The render image installs this family; selecting it explicitly avoids',
            '# Pango choosing a Latin-only default and rendering CJK as tofu boxes.',
            'EDUFLOW_CJK_FONT = "Noto Sans CJK SC"',
        ]

        # 收集需要的动画类
        anim_classes = set()
        object_imports = set()
        for frame in self.frames:
            for vo in frame.get("visual_objects", []):
                obj_type = vo.get("type", "")
                if obj_type in MOBJECT_MAP:
                    object_imports.add(MOBJECT_MAP[obj_type]["import"])
            for anim in frame.get("animations", []):
                anim_type = anim.get("type", "")
                if anim_type in ANIMATION_IMPORTS:
                    anim_classes.add(ANIMATION_IMPORTS[anim_type])

        # 去重后输出
        seen = set()
        for imp in sorted(object_imports):
            if imp not in seen:
                lines.append(imp)
                seen.add(imp)

        if anim_classes:
            lines.append(f"# Animation classes used: {', '.join(sorted(anim_classes))}")

        return "\n".join(lines)

    def _generate_scene_class(self) -> str:
        """生成 Scene 类定义。"""
        topic_slug = self.topic.replace(" ", "_").replace("/", "_")[:40]
        safe_topic = "".join(c if c.isalnum() or c == "_" else "_" for c in topic_slug)

        lines = [
            "",
            f"class EduFlow_{safe_topic}(Scene):",
            '    """EduFlow deterministic teaching animation."""',
            "",
            "    def construct(self):",
        ]

        if not self.frames:
            lines.append(
                '        self.add(Text("No frames generated", font=EDUFLOW_CJK_FONT))'
            )
            lines.append("        self.wait(1)")
            return "\n".join(lines)

        # 生成帧间动画
        lines.append(f"        # Total frames: {len(self.frames)}")
        lines.append("        self.camera.background_color = '#1a1a2e'")
        lines.append("")

        prev_objects: dict[str, str] = {}

        for i, frame in enumerate(self.frames):
            fid = frame.get("frame_id", f"f_{i:03d}")
            lines.append(f"        # ── {fid}: {frame.get('title', 'Untitled')} ──")
            lines.append(f"        self.next_section(name={fid!r})")

            # 生成 visual objects 创建代码
            obj_vars, obj_code = self._generate_objects_for_frame(frame, prev_objects, i)
            for code_line in obj_code:
                lines.append(code_line)

            # 生成 animations
            self._generate_animations_for_frame(frame, obj_vars, prev_objects, lines)

            # 生成 narration（作为字幕）
            narration = frame.get("narration", "")
            if narration:
                safe_narration = " ".join(str(narration).split())[:MAX_GENERATED_NARRATION_CHARS]
                lines.append(f'        # Narration: "{safe_narration}"')
                lines.append(
                    f"        subtitle = Text({safe_narration!r}, "
                    "font=EDUFLOW_CJK_FONT, font_size=24, color=WHITE)"
                )
                lines.append("        subtitle.to_edge(DOWN)")
                lines.append("        self.play(FadeIn(subtitle), run_time=0.5)")
                lines.append("        self.wait(2)")
                lines.append("        self.play(FadeOut(subtitle), run_time=0.3)")

            # 帧间等待
            wait_time = sum(
                a.get("duration_ms", 500) for a in frame.get("animations", [])
            ) / 1000.0 + 1.0
            lines.append(f"        self.wait({wait_time:.1f})")
            lines.append("")

            prev_objects = {**prev_objects, **obj_vars}

        lines.append("        # End of scene")
        lines.append('        self.play(FadeOut(*self.mobjects), run_time=1)')
        lines.append("        self.wait(0.5)")

        return "\n".join(lines)

    def _generate_objects_for_frame(
        self, frame: dict, prev_objects: dict, frame_idx: int
    ) -> dict[str, str]:
        """为帧生成 Mobject 定义 + 创建代码，返回 {vo_id: variable_name} 映射。"""
        obj_vars: dict[str, str] = {}
        code_lines: list[str] = []

        for vo in frame.get("visual_objects", []):
            vo_id = vo.get("id", "unknown")
            safe_id = "".join(
                char if char.isalnum() or char == "_" else "_"
                for char in str(vo_id)
            ) or "object"
            if safe_id[0].isdigit():
                safe_id = f"object_{safe_id}"
            var_name = f"{safe_id}_{frame_idx}"

            position = vo.get("position", {})
            raw_x, raw_y = _map_dsl_position(position)
            x = max(MANIM_X_LIMITS[0], min(MANIM_X_LIMITS[1], raw_x))
            y = max(MANIM_Y_LIMITS[0], min(MANIM_Y_LIMITS[1], raw_y))

            style = vo.get("style", {})
            color = style.get("color", "#4A90D9")
            size = style.get("size", 30) / 30.0 * 0.5

            label = vo.get("label", "")
            obj_type = vo.get("type", "node")
            mobject_info = MOBJECT_MAP.get(obj_type, MOBJECT_MAP["node"])

            # 根据类型生成创建代码
            if obj_type == "node":
                code_lines.append(
                    f"        {var_name} = Circle(radius={size:.2f}, color='{color}')"
                    f".move_to(np.array([{x:.1f}, {y:.1f}, 0]))"
                )
                if label:
                    code_lines.append(
                        f"        {var_name}_label = Text({label[:MAX_GENERATED_LABEL_CHARS]!r}, "
                        "font=EDUFLOW_CJK_FONT, font_size=20)"
                        f".next_to({var_name}, DOWN, buff=0.1)"
                    )
                    code_lines.append(f"        {var_name}_group = VGroup({var_name}, {var_name}_label)")

            elif obj_type == "edge":
                directed = vo.get("directed", True)
                edge_class = mobject_info.get("class_undirected") if not directed else "Arrow"
                code_lines.append(
                    f"        {var_name} = {edge_class}("
                    f"start=2*LEFT, end=2*RIGHT, color='{color}', stroke_width=3)"
                    f".move_to(np.array([{x:.1f}, {y:.1f}, 0]))"
                )
                if label:
                    code_lines.append(
                        f"        {var_name}_label = Text({label[:MAX_GENERATED_LABEL_CHARS]!r}, "
                        "font=EDUFLOW_CJK_FONT, font_size=16)"
                        f".next_to({var_name}, UP, buff=0.1)"
                    )

            elif obj_type == "table":
                rows_data = vo.get("rows", []) or []
                headers = vo.get("headers", [])
                table_data = _normalize_table_data(headers, rows_data)
                code_lines.append(
                    f"        {var_name} = Table("
                    f"{table_data!r}, element_to_mobject=Text, "
                    "element_to_mobject_config={'font': EDUFLOW_CJK_FONT}"
                    f").scale(0.5).move_to(np.array([{x:.1f}, {y:.1f}, 0]))"
                )

            elif obj_type == "formula":
                latex_raw = vo.get("latex", "x")
                # 生产沙箱不安装 LaTeX，始终编译为 Unicode Text。
                safe = _strip_latex(latex_raw)[:MAX_GENERATED_NARRATION_CHARS]
                code_lines.append(
                    f"        {var_name} = Text({safe!r}, font=EDUFLOW_CJK_FONT, "
                    "font_size=24, color=WHITE)"
                    f".move_to(np.array([{x:.1f}, {y:.1f}, 0]))"
                )

            elif obj_type == "code_block":
                code = repr(vo.get("code", "# code"))
                language = vo.get("language", "python")
                # 非标准语言名降级为 text（避免 Pygments ClassNotFound）
                if language not in ("python", "cpp", "java", "javascript", "bash", "text"):
                    language = "text"
                code_lines.append(
                    f"        {var_name} = Code(code_string={code}, "
                    f"language='{language}', tab_width=4, add_line_numbers=False)"
                    f".scale(0.5).move_to(np.array([{x:.1f}, {y:.1f}, 0]))"
                )

            elif obj_type == "process":
                code_lines.append(
                    f"        {var_name} = Rectangle("
                    f"width=2.0, height=0.6, color=BLUE, fill_opacity=0.3)"
                    f".move_to(np.array([{x:.1f}, {y:.1f}, 0]))"
                )
                if label:
                    code_lines.append(
                        f"        {var_name}_label = Text({label[:MAX_GENERATED_LABEL_CHARS]!r}, "
                        "font=EDUFLOW_CJK_FONT, font_size=16)"
                        f".move_to({var_name}.get_center())"
                    )
                    code_lines.append(f"        {var_name} = VGroup({var_name}, {var_name}_label)")

            else:
                # 通用回退：Circle
                code_lines.append(
                    f"        {var_name} = Circle(radius={size:.2f}, color='{color}')"
                    f".move_to(np.array([{x:.1f}, {y:.1f}, 0]))"
                )
                if label:
                    code_lines.append(
                        f"        {var_name}_label = Text({label[:MAX_GENERATED_LABEL_CHARS]!r}, "
                        "font=EDUFLOW_CJK_FONT, font_size=16)"
                        f".next_to({var_name}, DOWN)"
                    )

            obj_vars[vo_id] = var_name

        return obj_vars, code_lines

    def _generate_animations_for_frame(
        self,
        frame: dict,
        obj_vars: dict[str, str],
        prev_objects: dict[str, str],
        lines: list[str],
    ) -> None:
        """为帧的每个动画生成 Manim play 语句。"""
        for anim in frame.get("animations", []):
            anim_type = anim.get("type", "appear")
            target_id = anim.get("target", "")
            duration = anim.get("duration_ms", 500) / 1000.0
            var_name = obj_vars.get(target_id) or prev_objects.get(target_id)
            if not var_name:
                lines.append(f"        # Skip animation with unknown target: {target_id!r}")
                continue

            if anim_type == "appear":
                lines.append(f"        self.play(FadeIn({var_name}), run_time={duration:.1f})")
            elif anim_type == "disappear":
                lines.append(f"        self.play(FadeOut({var_name}), run_time={duration:.1f})")
            elif anim_type == "highlight":
                lines.append(f"        self.play(Indicate({var_name}, color=YELLOW), run_time={duration:.1f})")
            elif anim_type == "move":
                lines.append(f"        self.play({var_name}.animate.shift(RIGHT), run_time={duration:.1f})")
            elif anim_type == "update_value":
                from_val = anim.get("params", {}).get("from", anim.get("from_value", "?"))
                to_val = anim.get("params", {}).get("to", anim.get("to_value", "?"))
                lines.append(f"        # Update value: {from_val} → {to_val}")
                lines.append(f"        self.play(Indicate({var_name}, color=GREEN), run_time={duration:.1f})")
            elif anim_type == "swap":
                target_2 = anim.get("target_2", "")
                var_name_2 = obj_vars.get(target_2) or prev_objects.get(target_2)
                if not var_name_2:
                    lines.append(f"        # Skip swap with unknown target: {target_2!r}")
                    continue
                lines.append(f"        self.play(CyclicReplace({var_name}, {var_name_2}), run_time={duration:.1f})")
            else:
                anim_class = ANIMATION_MAP.get(anim_type, "FadeIn")
                lines.append(f"        self.play({anim_class}({var_name}), run_time={duration:.1f})")


# ============================================================================
# 导出配置生成
# ============================================================================


def generate_render_config(
    dsl: dict[str, Any],
    quality: str = "h",
    fps: int = 30,
    include_subtitles: bool = True,
) -> dict[str, Any]:
    """生成 Manim 渲染配置。"""
    frames = dsl.get("frames", [])
    total_duration_ms = sum(
        a.get("duration_ms", 500) for f in frames for a in f.get("animations", [])
    )
    # 估算：每帧额外 1s narration + 0.5s wait
    estimated_seconds = (total_duration_ms / 1000) + len(frames) * 2.5

    quality_map = {
        "l": {"pixel_height": 480, "pixel_width": 854},
        "m": {"pixel_height": 720, "pixel_width": 1280},
        "h": {"pixel_height": 1080, "pixel_width": 1920},
        "k": {"pixel_height": 2160, "pixel_width": 3840},
    }

    q = quality_map.get(quality, quality_map["h"])
    layout_issues = validate_render_layout(dsl)

    return {
        "project_id": dsl.get("project_id", ""),
        "topic": dsl.get("topic", ""),
        "frame_count": len(frames),
        "estimated_duration_seconds": round(estimated_seconds, 1),
        "quality": quality,
        "fps": fps,
        "output_format": "mp4",
        "pixel_height": q["pixel_height"],
        "pixel_width": q["pixel_width"],
        "include_subtitles": include_subtitles,
        "layout_valid": not any(i["severity"] == "error" for i in layout_issues),
        "layout_issues": layout_issues,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def generate_subtitles_srt(dsl: dict[str, Any]) -> str:
    """从 DSL 的 narration 字段生成 SRT 字幕文件。"""
    frames = dsl.get("frames", [])
    if not frames:
        return ""

    srt_lines = []
    time_cursor_ms = 0

    for i, frame in enumerate(frames):
        narration = frame.get("narration", "")
        if not narration:
            continue

        # 估算：动画时长 + 阅读时间
        anim_ms = sum(a.get("duration_ms", 500) for a in frame.get("animations", []))
        frame_duration_ms = max(anim_ms, len(narration) * 60)  # 中文约 60ms/字
        frame_duration_ms = max(frame_duration_ms, 2000)  # 最少 2 秒

        start_ms = time_cursor_ms
        end_ms = start_ms + frame_duration_ms

        srt_lines.append(str(i + 1))
        srt_lines.append(f"{_ms_to_srt_time(start_ms)} --> {_ms_to_srt_time(end_ms)}")
        srt_lines.append(narration.strip())
        srt_lines.append("")

        time_cursor_ms = end_ms

    return "\n".join(srt_lines)


def _ms_to_srt_time(ms: int) -> str:
    """毫秒转 SRT 时间格式 HH:MM:SS,mmm。"""
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    millis = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


# ============================================================================
# 顶层转换入口
# ============================================================================


def convert_dsl_to_manim(dsl: dict[str, Any]) -> dict[str, str]:
    """将 DSL 转换为完整的 Manim 工程文件集合。

    Returns:
        {
            "main.py": str,       # Manim 脚本
            "render_config.json": str,  # 渲染配置
            "subtitles.srt": str, # 字幕文件
        }
    """
    generator = ManimScriptGenerator(dsl)
    main_py = generator.generate()

    config = generate_render_config(dsl)
    subtitles = generate_subtitles_srt(dsl)

    return {
        "main.py": main_py,
        "render_config.json": json.dumps(config, ensure_ascii=False, indent=2),
        "subtitles.srt": subtitles,
    }


# ── Helpers ─────────────────────────────────────────────────


def _find_ffmpeg() -> str:
    """查找 FFmpeg 可执行文件所在目录。

    优先级：settings.ffmpeg_path > PATH 中的 ffmpeg > 空字符串（回退到 PATH）。
    """
    ffmpeg_dir = ""
    try:
        from config import get_settings
        settings = get_settings()
        if settings.ffmpeg_path and os.path.isdir(os.path.expandvars(settings.ffmpeg_path)):
            ffmpeg_dir = os.path.expandvars(settings.ffmpeg_path)
    except Exception:
        pass
    if not ffmpeg_dir:
        found = shutil.which("ffmpeg")
        if found:
            ffmpeg_dir = str(Path(found).parent)
    return ffmpeg_dir


def _has_cjk(s: str) -> bool:
    """检查字符串是否包含中日韩字符。"""
    for ch in s:
        cp = ord(ch)
        if (
            0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or 0x3000 <= cp <= 0x303F
            or 0xFF00 <= cp <= 0xFFEF
            or 0x3040 <= cp <= 0x30FF
            or 0xAC00 <= cp <= 0xD7AF
        ):
            return True
    return False


def _stringify_table_row(row: Any) -> list[str]:
    """Convert a DSL table row to values accepted by Manim ``Text``.

    Manim's ``Table`` forwards every cell to ``element_to_mobject``.  The
    generated exporter uses ``Text`` there, whose constructor expects a
    string and calls ``.find`` on it.  Algorithm DSLs commonly provide
    numeric distances/weights (and ``None`` for infinity), so passing the
    raw values makes the render fail with ``AttributeError: 'int' object has
    no attribute 'find'``.  Normalising at generation time keeps the
    generated script self-contained and preserves readable infinity cells.
    """
    if isinstance(row, (list, tuple)):
        values = row
    else:
        values = [row]
    return ["—" if value is None else str(value) for value in values]


def _normalize_table_data(headers: Any, rows: Any) -> list[list[str]]:
    """Build a rectangular, non-empty table for Manim's ``Table`` mobject."""
    normalized_headers = _stringify_table_row(headers) if headers else []
    if not isinstance(rows, (list, tuple)):
        rows = [rows] if rows is not None else []
    normalized_rows = [_stringify_table_row(row) for row in rows]
    table_data = ([normalized_headers] if normalized_headers else []) + normalized_rows
    if not table_data:
        return [[""]]
    width = max(len(row) for row in table_data)
    return [row + [""] * (width - len(row)) for row in table_data]


def _strip_latex(s: str) -> str:
    """移除常见的 LaTeX 命令，保留纯文本，用于 Text 回退显示。

    覆盖 \\text{}, \\mathrm{}, \\textbf{}, \\textit{} 等包装命令，
    以及 \\quad, \\qquad, \\frac, \\cdot, \\times 等数学命令。
    """
    import re

    # 1) 包装命令：保留内部文字
    s = re.sub(r"\\text\{(.*?)\}", r"\1", s)
    s = re.sub(r"\\mathrm\{(.*?)\}", r"\1", s)
    s = re.sub(r"\\textbf\{(.*?)\}", r"\1", s)
    s = re.sub(r"\\textit\{(.*?)\}", r"\1", s)
    s = re.sub(r"\\mathbf\{(.*?)\}", r"\1", s)
    s = re.sub(r"\\mathtt\{(.*?)\}", r"\1", s)

    # 2) \\frac{a}{b} → (a)/(b)
    s = re.sub(r"\\frac\{(.*?)\}\{(.*?)\}", r"(\1)/(\2)", s)

    # 3) 空格命令 → 普通空格
    s = s.replace("\\quad", "  ")
    s = s.replace("\\qquad", "    ")
    s = s.replace("\\,", " ")

    # 4) LaTeX 函数名 → 纯文本
    functions = [
        "log", "lg", "ln", "lim", "max", "min", "sin", "cos", "tan",
        "cot", "sec", "csc", "arcsin", "arccos", "arctan",
        "sinh", "cosh", "tanh", "exp", "det", "gcd", "lcm",
        "sup", "inf", "dim", "ker", "deg", "hom",
    ]
    for fn in functions:
        s = s.replace(f"\\{fn}", fn)

    # 5) 希腊字母 → Unicode
    greek = {
        "\\alpha": "α", "\\beta": "β", "\\gamma": "γ", "\\delta": "δ",
        "\\epsilon": "ε", "\\zeta": "ζ", "\\eta": "η", "\\theta": "θ",
        "\\iota": "ι", "\\kappa": "κ", "\\lambda": "λ", "\\mu": "μ",
        "\\nu": "ν", "\\xi": "ξ", "\\pi": "π", "\\rho": "ρ",
        "\\sigma": "σ", "\\tau": "τ", "\\upsilon": "υ", "\\phi": "φ",
        "\\chi": "χ", "\\psi": "ψ", "\\omega": "ω",
        "\\Gamma": "Γ", "\\Delta": "Δ", "\\Theta": "Θ",
        "\\Lambda": "Λ", "\\Xi": "Ξ", "\\Pi": "Π",
        "\\Sigma": "Σ", "\\Upsilon": "Υ", "\\Phi": "Φ",
        "\\Psi": "Ψ", "\\Omega": "Ω",
    }
    for cmd, uc in greek.items():
        s = s.replace(cmd, uc)

    # 6) 常见数学符号 → Unicode
    symbols = {
        "\\cdot": "·", "\\times": "×", "\\pm": "±", "\\mp": "∓",
        "\\div": "÷", "\\ast": "*", "\\star": "⋆",
        "\\approx": "≈", "\\equiv": "≡", "\\neq": "≠",
        "\\leq": "≤", "\\geq": "≥", "\\ll": "≪", "\\gg": "≫",
        "\\infty": "∞", "\\partial": "∂", "\\nabla": "∇",
        "\\int": "∫", "\\sum": "∑", "\\prod": "∏",
        "\\to": "→", "\\rightarrow": "→", "\\Rightarrow": "⇒",
        "\\leftarrow": "←", "\\Leftarrow": "⇐",
        "\\leftrightarrow": "↔", "\\mapsto": "↦",
        "\\land": "∧", "\\lor": "∨", "\\neg": "¬",
        "\\forall": "∀", "\\exists": "∃", "\\in": "∈", "\\notin": "∉",
        "\\subset": "⊂", "\\supset": "⊃", "\\subseteq": "⊆",
        "\\cup": "∪", "\\cap": "∩", "\\emptyset": "∅",
        "\\angle": "∠", "\\triangle": "△",
        "\\ldots": "…", "\\cdots": "⋯", "\\vdots": "⋮", "\\ddots": "⋱",
    }
    for cmd, uc in symbols.items():
        s = s.replace(cmd, uc)

    return s


def _looks_like_math(s: str) -> bool:
    """检查字符串是否像数学公式（含有 LaTeX 命令或数学符号）。"""
    return any(
        ch in s
        for ch in ("^", "_", "{", "\\", "=", "+", "-", "*", "/", "∑", "∫", "∂")
    )
