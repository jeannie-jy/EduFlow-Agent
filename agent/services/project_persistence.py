"""项目产物持久化助手。

统一处理生成/恢复流程中「DSL → project.dsl_snapshot + frames 表」的落库逻辑，
供 generate_service 与 versions/frames API 复用。

设计约定：
- ``frames`` 表是帧级编辑的真源（update/lock 直接改表）。
- ``project.dsl_snapshot`` 保留完整 DSL 供「推演/导出」读取，写操作时与表保持同步。
- 所有对 JSONB 字段的修改都以「整体重赋值」方式进行，确保 SQLAlchemy 检测到变更。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import parse_project_id

logger = logging.getLogger(__name__)


async def persist_frames_to_table(
    project_id: str,
    frames: list[dict[str, Any]],
    session: AsyncSession,
    version: int = 1,
) -> int:
    """将 DSL 中的帧写入 ``frames`` 表（覆盖同 project+version 的旧帧）。

    Returns:
        写入的帧数量。
    """
    from db.models import Frame

    pid = parse_project_id(project_id)

    # 覆盖式写入：先删旧帧，再按顺序插入
    await session.execute(
        delete(Frame).where(Frame.project_id == pid, Frame.version == version)
    )

    for idx, f in enumerate(frames):
        session.add(
            Frame(
                id=uuid.uuid4(),
                project_id=pid,
                version=version,
                frame_id=f.get("frame_id") or f"f_{idx + 1:03d}",
                order_index=idx,
                title=f.get("title"),
                learning_goal=f.get("learning_goal"),
                narration=f.get("narration"),
                visual_objects=f.get("visual_objects") or [],
                state_snapshot=f.get("state_snapshot") or {},
                animations=f.get("animations") or [],
                interaction_hooks=f.get("interaction_hooks") or [],
                checks=f.get("checks") or [],
                quality_status=f.get("quality_status") or "pending",
                is_locked=bool(f.get("is_locked", False)),
            )
        )

    await session.flush()
    logger.info("frames 表已写入: project=%s version=%d count=%d", project_id, version, len(frames))
    return len(frames)


def merge_dsl_snapshot(
    existing: dict[str, Any] | None,
    dsl: dict[str, Any],
    *,
    quality_report: dict[str, Any] | None = None,
    teaching_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """合并生成产物到 dsl_snapshot（返回新字典以触发 JSONB 变更检测）。

    保留 existing 中的用户输入字段（input_content/input_type/constraints/material_ids），
    叠加完整 DSL（frames/parameters/knowledge_graph/teaching_strategy 等），
    并写入 teaching_plan / quality_report 供 getProject 读取。
    """
    snap: dict[str, Any] = dict(existing or {})
    snap.update(dsl)
    if teaching_plan is not None:
        snap["teaching_plan"] = teaching_plan
    if quality_report is not None:
        snap["quality_report"] = quality_report
    return snap
