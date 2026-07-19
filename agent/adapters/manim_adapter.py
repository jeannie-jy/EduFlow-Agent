"""Manim Adapter — 确定性 DSL → Manim Python 脚本转换器。

不依赖 LLM，纯规则映射。每种 VisualObject 和 Animation 有固定的 Manim 映射。

参考: Manim Community Edition v0.18+
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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
        "args": 'code=code_content, language="{language}"',
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
    "transform": "Transform",
    "move": "animate.move_to",
    "update_value": "Transform",  # 值变化用 Transform + 新对象
    "compare": "AnimationGroup",  # 组合动画
    "swap": "CyclicReplace",  # 交换位置
    "relax_edge": "Transform",  # 边权重变化
    "enqueue": "FadeIn",
    "dequeue": "FadeOut",
    "split": "Transform",
    "merge": "Transform",
    "schedule": "FadeIn",
    "lock": "FadeIn",  # 锁定图标出现
    "unlock": "FadeOut",  # 锁定图标消失
}

# 动画需要额外导入的类
ANIMATION_IMPORTS: dict[str, str] = {
    "appear": "FadeIn",
    "disappear": "FadeOut",
    "highlight": "Indicate",
    "transform": "Transform",
    "compare": "AnimationGroup",
    "swap": "CyclicReplace",
}


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
            f"# Generated: {datetime.now(timezone.utc).isoformat()}",
            f"# Frames: {len(self.frames)}",
            "",
            "from manim import *",
            "import json",
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
            f'    """教学推演: {self.topic}"""',
            "",
            "    def construct(self):",
        ]

        if not self.frames:
            lines.append('        self.add(Text("No frames generated"))')
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
            lines.append(f"        self.next_section(name='{fid}')")

            # 生成 visual objects（创建代码注入到临时列表）
            obj_vars = self._generate_objects_for_frame(frame, prev_objects, i)

            # 注入对象创建代码
            obj_code = frame.get("_object_creation_code", [])
            for code_line in obj_code:
                lines.append(code_line)

            # 生成 animations
            self._generate_animations_for_frame(frame, obj_vars, prev_objects, lines)

            # 生成 narration（作为字幕）
            narration = frame.get("narration", "")
            if narration:
                safe_narration = narration.replace('"', "'")[:200]
                lines.append(f'        # Narration: "{safe_narration}"')
                lines.append(f'        subtitle = Text(r"{safe_narration}", font_size=24, color=WHITE)')
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
            var_name = f"{vo_id}_{frame_idx}"

            position = vo.get("position", {})
            x = max(-7.0, min(7.0, position.get("x", 0) / 100.0 - 3.0))
            y = max(-4.0, min(4.0, (position.get("y", 0) / 100.0 - 2.0) * -1))

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
                        f"        {var_name}_label = Text(r'{label[:20]}', font_size=20)"
                        f".next_to({var_name}, DOWN, buff=0.1)"
                    )
                    code_lines.append(f"        {var_name}_group = VGroup({var_name}, {var_name}_label)")

            elif obj_type == "edge":
                directed = vo.get("directed", True)
                edge_class = mobject_info.get("class_undirected") if not directed else "Arrow"
                code_lines.append(
                    f"        {var_name} = {edge_class}("
                    f"start=LEFT, end=RIGHT, color='{color}')"
                )

            elif obj_type == "table":
                rows_data = vo.get("rows", [])
                headers = vo.get("headers", [])
                code_lines.append(
                    f"        {var_name} = Table("
                    f"[{json.dumps(headers)}] + {json.dumps(rows_data)}"
                    f").scale(0.5).move_to(np.array([{x:.1f}, {y:.1f}, 0]))"
                )

            elif obj_type == "formula":
                latex = vo.get("latex", "x")
                code_lines.append(
                    f"        {var_name} = MathTex(r'{latex}')"
                    f".move_to(np.array([{x:.1f}, {y:.1f}, 0]))"
                )

            elif obj_type == "code_block":
                code = vo.get("code", "# code")
                language = vo.get("language", "python")
                code_lines.append(
                    f"        {var_name} = Code(code='''{code}''', "
                    f"language='{language}', font_size=18)"
                    f".move_to(np.array([{x:.1f}, {y:.1f}, 0]))"
                )

            elif obj_type == "process":
                code_lines.append(
                    f"        {var_name} = Rectangle("
                    f"width=2.0, height=0.6, color=BLUE, fill_opacity=0.3)"
                    f".move_to(np.array([{x:.1f}, {y:.1f}, 0]))"
                )
                if label:
                    code_lines.append(
                        f"        {var_name}_label = Text(r'{label[:20]}', font_size=16)"
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
                        f"        {var_name}_label = Text(r'{label[:20]}', font_size=16)"
                        f".next_to({var_name}, DOWN)"
                    )

            obj_vars[vo_id] = var_name

        # 将创建代码注入到 _generate_scene_class 的结果（通过追加到调用方传入的 lines）
        frame["_object_creation_code"] = code_lines
        return obj_vars

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
            var_name = obj_vars.get(target_id, target_id)

            if anim_type == "appear":
                lines.append(f"        {var_name} = Circle(radius=0.5, color=BLUE)")
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
                var_name_2 = obj_vars.get(target_2, target_2)
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
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
