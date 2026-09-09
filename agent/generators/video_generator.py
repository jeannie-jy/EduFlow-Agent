"""Video preparation generator.

The module generation phase prepares a video manifest from the frame script.
Rendering is intentionally started later by the explicit export API after the
user reviews the storyboard and chooses output settings.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseGenerator
from .registry import register_generator

logger = logging.getLogger(__name__)


VIDEO_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string"},
        "source_frames_version": {"type": "string"},
        "job_id": {"type": "string"},
        "status": {"type": "string"},
        "config": {"type": "object"},
        "message": {"type": "string"},
    },
    "required": ["status"],
}


class VideoGenerator(BaseGenerator):
    """Manim 教学视频导出生成器。

    依赖 frames 模块先完成 DSL 帧生成。
    准备视频分镜清单；不在模块生成阶段启动耗时渲染。
    """

    module_id = "video"
    display_name = "教学视频"
    description = "将教学推演导出为 Manim 动画视频（MP4），支持多种画质和字幕"
    icon = "video"
    category = "export"
    priority = 5
    version = "1.0.0"
    requires = ("frames",)

    temperature = 0.3
    max_tokens = 16384

    @property
    def output_schema(self) -> dict[str, Any]:
        return VIDEO_OUTPUT_SCHEMA

    def get_system_prompt(self) -> str:
        """视频导出不需要 LLM 提示词（通过 manim_llm_adapter 间接使用 LLM）。"""
        return ""

    async def generate(
        self,
        teaching_plan: dict[str, Any],
        knowledge_graph: dict[str, Any],
        user_input: str,
        constraints: dict[str, Any],
        project_id: str,
        existing_outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Prepare a render-ready manifest without creating an export job."""

        # 1. 从已生成的模块产出中获取 frames（内存优先于 DB）
        dsl = None
        if existing_outputs and "frames" in existing_outputs:
            frames_output = existing_outputs["frames"]
            # frames_generator 产出完整 DSL 对象 → 直接使用
            if isinstance(frames_output, dict) and frames_output.get("frames"):
                dsl = frames_output

        # 回退到 DB 读取（向后兼容，兼容 frames 在顶层或 module_outputs.frames 两种形态）
        if dsl is None:
            try:
                from db.database import async_session_factory
                from db.models import Project as ProjectModel
                from api.deps import parse_project_id
                from services.project_persistence import load_canonical_project_dsl

                async with async_session_factory() as db_session:
                    project = await db_session.get(ProjectModel, parse_project_id(project_id))
                    dsl = (
                        await load_canonical_project_dsl(project, db_session)
                        if project
                        else None
                    )
            except Exception:
                pass

        if dsl is None:
            return {
                "schema_version": "1.0",
                "status": "skipped",
                "message": "缺少推演脚本（frames），已自动补充。如重复出现请重试",
                "config": {},
            }

        return {
            "schema_version": "1.0",
            "source_frames_version": str(dsl.get("artifact_version", "")),
            "status": "ready",
            "config": {
                "quality": "h",
                "format": "mp4",
                "fps": 30,
                "include_subtitles": True,
                "include_tts": False,
            },
            "message": "视频分镜已就绪，请确认设置后开始制作视频",
        }

    def validate(self, output: dict[str, Any]) -> list[dict[str, Any]]:
        """校验视频导出结果。"""
        issues: list[dict[str, Any]] = super().validate(output)

        status = output.get("status", "")
        if status == "failed":
            issues.append({
                "severity": "high",
                "type": "export_failed",
                "description": output.get("message", "视频导出失败"),
            })
        elif status == "skipped":
            issues.append({
                "severity": "medium",
                "type": "no_frames",
                "description": output.get("message", "跳过视频导出"),
            })

        return issues


# ── 自动注册 ──────────────────────────────────────────────────

register_generator(VideoGenerator())
logger.info("VideoGenerator 已注册 (module_id=video)")
