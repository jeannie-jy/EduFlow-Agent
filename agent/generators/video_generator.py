"""Manim Video Generator — 教学视频导出生成器。

封装现有的 manim_llm_adapter 导出流程为 ModuleGenerator。
依赖 frames 模块（必须先有 DSL 帧才能生成视频）。
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
    创建 Manim 渲染任务并返回 job_id 供前端轮询。
    """

    module_id = "video"
    display_name = "教学视频"
    description = "将教学推演导出为 Manim 动画视频（MP4），支持多种画质和字幕"
    icon = "video"
    category = "export"
    priority = 5
    version = "1.0.0"

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
        """创建 Manim 导出任务。

        从 existing_outputs["frames"] 读取帧数据（内存获取，避免 DB 时序问题）。
        创建 job 记录并返回 job_id。
        """
        import asyncio
        import uuid

        # 1. 从已生成的模块产出中获取 frames（内存优先于 DB）
        dsl = None
        if existing_outputs and "frames" in existing_outputs:
            frames_output = existing_outputs["frames"]
            # frames_generator 产出完整 DSL 对象 → 直接使用
            if isinstance(frames_output, dict) and frames_output.get("frames"):
                dsl = frames_output

        # 回退到 DB 读取（向后兼容）
        if dsl is None:
            try:
                from db.database import async_session_factory
                from db.models import Project as ProjectModel
                from api.deps import parse_project_id

                async with async_session_factory() as db_session:
                    project = await db_session.get(ProjectModel, parse_project_id(project_id))
                    if project and project.dsl_snapshot and project.dsl_snapshot.get("frames"):
                        dsl = project.dsl_snapshot
            except Exception:
                pass

        if dsl is None:
            return {
                "status": "skipped",
                "message": "缺少推演脚本（frames），已自动补充。如重复出现请重试",
                "config": {},
            }

        # 2. 创建导出任务
        try:
            from db.database import async_session_factory
            from db.models import Project as ProjectModel, ExportJobModel
            from api.deps import parse_project_id

            async with async_session_factory() as db_session:
                # 2. 创建导出任务
                job_id = uuid.uuid4()
                config = {
                    "quality": "h",
                    "format": "mp4",
                    "fps": 30,
                    "include_subtitles": True,
                }

                export_job = ExportJobModel(
                    id=job_id,
                    project_id=parse_project_id(project_id),
                    target="manim_video",
                    status="queued",
                    config=config,
                )
                db_session.add(export_job)
                await db_session.flush()
                await db_session.commit()

                # 单轨导出：无独立 Worker，直接启动进程内后台渲染任务
                from api.export import _fallback_export
                asyncio.create_task(_fallback_export(str(job_id), dsl, config))

                return {
                    "job_id": str(job_id),
                    "status": "queued",
                    "config": config,
                    "message": "视频导出任务已创建，正在渲染中...",
                }

        except Exception as exc:
            logger.exception("VideoGenerator 失败")
            return {
                "status": "failed",
                "message": f"视频导出失败: {exc}",
                "config": {},
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
