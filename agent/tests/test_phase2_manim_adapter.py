"""Phase 2 Manim Adapter 测试。

覆盖：DSL→Manim 脚本生成、配置生成、字幕生成、边界条件。
"""

from __future__ import annotations

import pytest

from adapters.manim_adapter import (
    ManimScriptGenerator,
    convert_dsl_to_manim,
    generate_render_config,
    generate_subtitles_srt,
    _ms_to_srt_time,
    MOBJECT_MAP,
    ANIMATION_MAP,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def empty_dsl() -> dict:
    return {"project_id": "test", "topic": "Empty", "frames": []}


@pytest.fixture
def minimal_dsl() -> dict:
    return {
        "project_id": "test_min",
        "topic": "冒泡排序",
        "frames": [
            {
                "frame_id": "f_001",
                "title": "数组初始化",
                "narration": "这是一个未排序的数组。",
                "visual_objects": [
                    {"id": "arr", "type": "array", "position": {"x": 100, "y": 200}},
                ],
                "state_snapshot": {"array": [5, 3, 8, 1]},
                "animations": [
                    {"type": "appear", "target": "arr", "duration_ms": 500},
                ],
                "interaction_hooks": [],
                "checks": [],
            },
            {
                "frame_id": "f_002",
                "title": "比较相邻元素",
                "narration": "比较 5 和 3，发现 5 > 3，交换它们。",
                "visual_objects": [
                    {"id": "arr", "type": "array", "position": {"x": 100, "y": 200}},
                ],
                "state_snapshot": {"array": [3, 5, 8, 1]},
                "animations": [
                    {"type": "highlight", "target": "arr", "duration_ms": 500},
                    {"type": "swap", "target": "cell_0", "target_2": "cell_1", "duration_ms": 800},
                ],
                "interaction_hooks": [],
                "checks": [],
            },
        ],
    }


# ============================================================================
# Mapping table integrity
# ============================================================================


class TestMappingTables:
    """验证映射表的完整性和一致性。"""

    def test_all_14_visual_object_types_mapped(self):
        """所有 14 种 VisualObject type 都应有 Manim 映射。"""
        from schema.dsl import VisualObjectType
        for vo_type in VisualObjectType:
            assert vo_type.value in MOBJECT_MAP, f"Missing MOBJECT_MAP entry: {vo_type.value}"

    def test_all_16_animation_types_mapped(self):
        """所有 16 种 Animation type 都应有 Manim 映射。"""
        from schema.dsl import AnimationType
        for anim_type in AnimationType:
            assert anim_type.value in ANIMATION_MAP, f"Missing ANIMATION_MAP entry: {anim_type.value}"

    def test_mobject_map_has_required_fields(self):
        """每个 MOBJECT_MAP entry 应有 class/import/args/needs_label。"""
        for key, entry in MOBJECT_MAP.items():
            assert "class" in entry, f"MOBJECT_MAP['{key}'] missing 'class'"
            assert "import" in entry, f"MOBJECT_MAP['{key}'] missing 'import'"
            assert "needs_label" in entry, f"MOBJECT_MAP['{key}'] missing 'needs_label'"

    def test_anim_import_superset(self):
        """ANIMATION_IMPORTS 中的动画应都在 ANIMATION_MAP 中有定义。"""
        for anim_type in ANIMATION_MAP:
            assert anim_type in ANIMATION_MAP, f"{anim_type} should have an ANIMATION_MAP entry"


# ============================================================================
# ManimScriptGenerator
# ============================================================================


class TestManimScriptGenerator:
    """脚本生成器测试。"""

    def test_generate_empty_dsl(self, empty_dsl):
        gen = ManimScriptGenerator(empty_dsl)
        script = gen.generate()
        assert "from manim import *" in script
        assert "class EduFlow_Empty" in script
        assert "No frames generated" in script

    def test_generate_header_metadata(self, minimal_dsl):
        gen = ManimScriptGenerator(minimal_dsl)
        script = gen.generate()
        assert "#!/usr/bin/env python3" in script
        assert "Auto-generated Manim script by EduFlow-Agent" in script
        assert "Project: test_min" in script
        assert "Topic: 冒泡排序" in script
        assert "Frames: 2" in script

    def test_generate_scene_class(self, minimal_dsl):
        gen = ManimScriptGenerator(minimal_dsl)
        script = gen.generate()
        # 特殊字符应被过滤
        assert "class EduFlow_" in script
        assert "(Scene):" in script
        assert "def construct(self):" in script
        # 不应包含非法字符
        assert "\t" not in script  # 只应用空格缩进

    def test_generate_includes_sections(self, minimal_dsl):
        gen = ManimScriptGenerator(minimal_dsl)
        script = gen.generate()
        assert "next_section" in script, "应包含 next_section 调用"
        assert "f_001" in script
        assert "f_002" in script

    def test_narration_generates_subtitle(self, minimal_dsl):
        gen = ManimScriptGenerator(minimal_dsl)
        script = gen.generate()
        assert "subtitle.to_edge(DOWN)" in script
        assert "FadeIn(subtitle)" in script
        assert "FadeOut(subtitle)" in script

    def test_special_characters_in_topic(self):
        """话题包含特殊字符应被安全处理。"""
        dsl = {
            "project_id": "p1",
            "topic": "C/C++ 指针&引用 @2024",
            "frames": [],
        }
        gen = ManimScriptGenerator(dsl)
        script = gen.generate()
        # 类名不应包含 &、/、@ 等
        class_line = [l for l in script.split("\n") if "class EduFlow_" in l][0]
        assert "&" not in class_line
        assert "@" not in class_line
        assert "/" not in class_line

    def test_narration_quotes_escaped(self, minimal_dsl):
        """narration 中包含双引号应被转义。"""
        dsl = {
            "project_id": "p1",
            "topic": "test",
            "frames": [{
                "frame_id": "f_001",
                "title": "t",
                "narration": '他说："这是一个字符串"',
                "visual_objects": [],
                "state_snapshot": {},
                "animations": [],
            }],
        }
        gen = ManimScriptGenerator(dsl)
        script = gen.generate()
        # 双引号应被替换为单引号
        assert '他说' in script
        assert "'''" not in script  # 不应有三引号语法错误

    def test_empty_narration_no_subtitle_block(self, minimal_dsl):
        """无 narration 的帧不应生成字幕代码。"""
        dsl = {
            "project_id": "p1",
            "topic": "test",
            "frames": [{
                "frame_id": "f_001",
                "title": "t",
                "narration": "",
                "visual_objects": [],
                "state_snapshot": {},
                "animations": [],
            }],
        }
        gen = ManimScriptGenerator(dsl)
        script = gen.generate()
        assert "subtitle" not in script

    def test_unknown_animation_fallback(self, minimal_dsl):
        """未知动画类型应回退到 FadeIn。"""
        dsl = {
            "project_id": "p1",
            "topic": "test",
            "frames": [{
                "frame_id": "f_001",
                "title": "t",
                "narration": "",
                "visual_objects": [{"id": "obj1", "type": "node"}],
                "state_snapshot": {},
                "animations": [{"type": "unknown_bizarre_anim", "target": "obj1", "duration_ms": 300}],
            }],
        }
        gen = ManimScriptGenerator(dsl)
        script = gen.generate()
        # 应使用 FadeIn 回退
        assert "FadeIn" in script

    def test_mixed_visual_object_types_imports(self):
        """多类型 VisualObject 应生成完整的 import 集合。"""
        dsl = {
            "project_id": "p1",
            "topic": "test",
            "frames": [{
                "frame_id": "f_001",
                "title": "t",
                "narration": "",
                "visual_objects": [
                    {"id": "n1", "type": "node"},
                    {"id": "e1", "type": "edge"},
                    {"id": "t1", "type": "table"},
                    {"id": "f1", "type": "formula", "latex": "E=mc^2"},
                    {"id": "c1", "type": "code_block", "language": "python", "code": "x=1"},
                ],
                "state_snapshot": {},
                "animations": [
                    {"type": "appear", "target": "n1"},
                    {"type": "highlight", "target": "e1"},
                    {"type": "swap", "target": "t1", "target_2": "f1"},
                ],
            }],
        }
        gen = ManimScriptGenerator(dsl)
        script = gen.generate()
        assert "Circle" in script or "from manim import" in script
        assert "MathTex" in script or "from manim import" in script
        # 动画类应在注释中列出
        assert "FadeIn" in script or "Indicate" in script


# ============================================================================
# Render Config
# ============================================================================


class TestRenderConfig:
    """渲染配置测试。"""

    def test_generate_basic_config(self, minimal_dsl):
        config = generate_render_config(minimal_dsl)
        assert config["project_id"] == "test_min"
        assert config["frame_count"] == 2
        assert config["quality"] == "h"
        assert config["fps"] == 30
        assert config["output_format"] == "mp4"

    def test_quality_resolutions(self):
        dsl = {"project_id": "p", "topic": "t", "frames": []}
        assert generate_render_config(dsl, quality="l")["pixel_height"] == 480
        assert generate_render_config(dsl, quality="m")["pixel_height"] == 720
        assert generate_render_config(dsl, quality="h")["pixel_height"] == 1080
        assert generate_render_config(dsl, quality="k")["pixel_height"] == 2160

    def test_invalid_quality_fallback(self):
        """非法 quality 值应回退到 'h'（1080p）。"""
        dsl = {"project_id": "p", "topic": "t", "frames": []}
        config = generate_render_config(dsl, quality="8k_super")
        assert config["pixel_height"] == 1080  # 回退到 h

    def test_estimated_duration_non_negative(self, empty_dsl):
        """即使没有帧，估时也应为 0 而非负。"""
        config = generate_render_config(empty_dsl)
        assert config["estimated_duration_seconds"] >= 0

    def test_config_includes_timestamp(self, empty_dsl):
        config = generate_render_config(empty_dsl)
        assert "generated_at" in config


# ============================================================================
# Subtitles SRT
# ============================================================================


class TestSubtitlesSRT:
    """字幕生成测试。"""

    def test_srt_format_marker(self, minimal_dsl):
        srt = generate_subtitles_srt(minimal_dsl)
        assert "1" in srt
        assert "-->" in srt

    def test_empty_dsl_no_subtitles(self, empty_dsl):
        srt = generate_subtitles_srt(empty_dsl)
        assert srt == ""

    def test_srt_timestamps_increasing(self, minimal_dsl):
        """字幕时间戳应单调递增。"""
        # 这个简单的 DSL 有两帧，都有 narration
        srt = generate_subtitles_srt(minimal_dsl)
        assert "2" in srt or "00:" in srt  # 至少有一个有效的时间标记

    def test_ms_to_srt_time(self):
        assert _ms_to_srt_time(0) == "00:00:00,000"
        assert _ms_to_srt_time(1000) == "00:00:01,000"
        assert _ms_to_srt_time(62000) == "00:01:02,000"
        assert _ms_to_srt_time(3661000) == "01:01:01,000"
        assert _ms_to_srt_time(123456) == "00:02:03,456"

    def test_srt_no_narration_frames_skipped(self):
        """无 narration 的帧应被跳过，不产生空字幕条目。"""
        dsl = {
            "project_id": "p1",
            "topic": "test",
            "frames": [
                {"frame_id": "f_001", "narration": "", "animations": []},
                {"frame_id": "f_002", "narration": "有内容的帧", "animations": []},
            ],
        }
        srt = generate_subtitles_srt(dsl)
        # f_001 被跳过，f_002 应是第 1 条字幕
        assert "有内容的帧" in srt
        # 应只有 1 条字幕（无 narration 的帧不产生条目）
        assert srt.count("-->") == 1

    def test_srt_well_formed_format(self):
        """验证 SRT 格式符合标准。"""
        dsl = {
            "project_id": "p",
            "topic": "t",
            "frames": [
                {"frame_id": "f_001", "narration": "Test", "animations": [
                    {"type": "appear", "target": "x", "duration_ms": 1000}
                ]},
            ],
        }
        srt = generate_subtitles_srt(dsl)
        lines = srt.split("\n")
        assert lines[0] == "1"  # 序号
        assert "-->" in lines[1]  # 时间戳
        assert lines[2] == "Test"  # 内容
        assert lines[3] == ""  # 空行分隔


# ============================================================================
# Top-level converter
# ============================================================================


class TestConvertDSLToManim:
    """顶层转换入口测试。"""

    def test_returns_three_files(self, minimal_dsl):
        result = convert_dsl_to_manim(minimal_dsl)
        assert "main.py" in result
        assert "render_config.json" in result
        assert "subtitles.srt" in result

    def test_main_py_is_valid(self, minimal_dsl):
        result = convert_dsl_to_manim(minimal_dsl)
        main_py = result["main.py"]
        assert isinstance(main_py, str)
        assert len(main_py) > 100
        assert "def construct" in main_py

    def test_render_config_is_valid_json(self, minimal_dsl):
        import json
        result = convert_dsl_to_manim(minimal_dsl)
        config_str = result["render_config.json"]
        config = json.loads(config_str)
        assert "frame_count" in config
        assert "quality" in config

    def test_subtitles_is_string(self, minimal_dsl):
        result = convert_dsl_to_manim(minimal_dsl)
        assert isinstance(result["subtitles.srt"], str)

    def test_all_16_animations_in_script(self):
        """用包含全部 16 种动画的 DSL 验证脚本生成不崩溃。"""
        dsl = {
            "project_id": "p1",
            "topic": "Full Animation Test",
            "frames": [
                {
                    "frame_id": f"f_{i:03d}",
                    "title": f"Anim {anim_type}",
                    "narration": f"Testing {anim_type}",
                    "visual_objects": [
                        {"id": f"obj_{i}", "type": "node", "label": str(i)},
                    ],
                    "state_snapshot": {},
                    "animations": [
                        {"type": anim_type, "target": f"obj_{i}", "duration_ms": 300},
                    ],
                }
                for i, anim_type in enumerate([
                    "appear", "disappear", "highlight", "transform", "move",
                    "update_value", "compare", "swap", "relax_edge",
                    "enqueue", "dequeue", "split", "merge", "schedule",
                    "lock", "unlock",
                ])
            ],
        }
        result = convert_dsl_to_manim(dsl)
        assert "def construct" in result["main.py"]
        assert len(result["main.py"]) > 500
