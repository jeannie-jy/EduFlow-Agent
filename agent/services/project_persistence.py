"""项目产物持久化助手。

统一处理生成/恢复流程中「DSL → project.dsl_snapshot + frames 表」的落库逻辑，
供 generate_service 与 versions/frames API 复用。

设计约定：
- ``frames`` 表是帧级编辑的真源（update/lock 直接改表）。
- ``project.dsl_snapshot.frames`` 保留自包含帧产物供「推演/导出」读取；
  ``module_outputs.frames`` 仅保存指向不可变 ProjectVersion 的引用，活动读取时再水合。
- 所有对 JSONB 字段的修改都以「整体重赋值」方式进行，确保 SQLAlchemy 检测到变更。
"""

from __future__ import annotations

import logging
import uuid
from copy import deepcopy
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
    dsl: dict[str, Any] | None = None,
    *,
    quality_report: dict[str, Any] | None = None,
    teaching_plan: dict[str, Any] | None = None,
    module_outputs: dict[str, Any] | None = None,
    module_errors: dict[str, Any] | None = None,
    knowledge_graph: dict[str, Any] | None = None,
    selected_modules: list[str] | None = None,
    module_dependencies: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """合并生成产物到 dsl_snapshot（返回新字典以触发 JSONB 变更检测）。

    保留 existing 中的用户输入字段（input_content/input_type/constraints/material_ids），
    叠加完整 DSL（frames/parameters/knowledge_graph/teaching_strategy 等），
    并写入 teaching_plan / quality_report / module_outputs / module_errors 供 getProject 读取。
    """
    snap: dict[str, Any] = dict(existing or {})
    if dsl is not None:
        snap.update(dsl)
    if teaching_plan is not None:
        snap["teaching_plan"] = teaching_plan
    if quality_report is not None:
        snap["quality_report"] = quality_report
    if knowledge_graph is not None:
        snap["knowledge_graph"] = knowledge_graph
    if selected_modules is not None:
        snap["selected_modules"] = list(dict.fromkeys(selected_modules))
    if module_dependencies is not None:
        snap["module_dependencies"] = {
            module_id: list(dict.fromkeys(dependencies))
            for module_id, dependencies in module_dependencies.items()
        }
    if module_outputs is not None:
        # 合并而非覆盖：保留已有模块产出，只更新本次生成的模块
        existing_mods = dict(snap.get("module_outputs", {}))
        existing_mods.update(module_outputs)
        snap["module_outputs"] = existing_mods
        current_stale = snap.get("stale_module_ids", [])
        if not isinstance(current_stale, list):
            current_stale = []
        stale_modules = [
            module_id
            for module_id in current_stale
            if module_id not in module_outputs
        ]
        if stale_modules:
            snap["stale_module_ids"] = stale_modules
        else:
            snap.pop("stale_module_ids", None)
    if module_errors is not None:
        existing_errs = dict(snap.get("module_errors", {}))
        existing_errs.update(module_errors)
        # A successful retry supersedes a historical error for that module.
        for module_id in (module_outputs or {}):
            existing_errs.pop(module_id, None)
        snap["module_errors"] = existing_errs
    return snap


def compact_frames_artifact_reference(
    snapshot: dict[str, Any],
    version_id: uuid.UUID,
) -> dict[str, Any]:
    """Replace the duplicated module Frames payload with an immutable reference.

    Top-level ``frames`` remains the version's self-contained artifact. Active
    reads hydrate the module projection from the Frames table, so callers keep
    receiving the legacy response shape without storing the array twice.
    """
    compacted = deepcopy(snapshot)
    if not isinstance(compacted.get("frames"), list):
        return compacted
    module_outputs = compacted.get("module_outputs")
    if not isinstance(module_outputs, dict):
        return compacted
    frames_output = module_outputs.get("frames")
    if not isinstance(frames_output, dict):
        return compacted
    existing_ref = frames_output.get("artifact_ref")
    has_owned_frames = isinstance(frames_output.get("frames"), list)
    has_version_ref = (
        isinstance(existing_ref, dict)
        and existing_ref.get("type") == "project_version_frames"
    )
    if not has_owned_frames and not has_version_ref:
        return compacted

    frames_reference = {
        key: deepcopy(value)
        for key, value in frames_output.items()
        if key != "frames"
    }
    frames_reference["artifact_ref"] = {
        "type": "project_version_frames",
        "version_id": str(version_id),
    }
    module_outputs = deepcopy(module_outputs)
    module_outputs["frames"] = frames_reference
    compacted["module_outputs"] = module_outputs
    return compacted


def resolve_export_dsl(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """解析导出（视频/推演）所用的完整 DSL（含 frames）。

    兼容两种快照形态：
    - 全量生成流：frames 直接位于 dsl_snapshot 顶层；
    - 模块流（v0.8 早期落库形态）：frames 只存在于 module_outputs.frames。
      模块流的 frames 产出本身是完整 DSL 对象，以快照为底、帧产出为顶合并补齐。

    Returns:
        含非空 frames 的完整 DSL；两者都没有 frames 时返回 None。
    """
    snap = snapshot or {}
    if snap.get("frames"):
        return snap
    frames_dsl = (snap.get("module_outputs") or {}).get("frames")
    if isinstance(frames_dsl, dict) and frames_dsl.get("frames"):
        return {**snap, **frames_dsl}
    return None


def frame_row_to_dsl(frame) -> dict[str, Any]:
    """Serialize the editable frame row without leaking database-only fields."""
    return {
        "frame_id": frame.frame_id,
        "title": frame.title or "",
        "learning_goal": frame.learning_goal or "",
        "narration": frame.narration or "",
        "visual_objects": deepcopy(frame.visual_objects or []),
        "state_snapshot": deepcopy(frame.state_snapshot or {}),
        "animations": deepcopy(frame.animations or []),
        "interaction_hooks": deepcopy(frame.interaction_hooks or []),
        "checks": deepcopy(frame.checks or []),
        "quality_status": frame.quality_status,
        "is_locked": bool(frame.is_locked),
    }


async def load_canonical_project_dsl(project, session: AsyncSession) -> dict[str, Any] | None:
    """Materialize an active DSL with the editable ``frames`` table as truth.

    ``dsl_snapshot.frames`` is the self-contained version payload. The compact
    ``module_outputs.frames`` projection is hydrated for compatibility, and
    every active read is overlaid from frame rows.
    """
    from sqlalchemy import select

    from db.models import Frame

    snapshot = deepcopy(project.dsl_snapshot or {})
    result = await session.execute(
        select(Frame)
        .where(Frame.project_id == project.id, Frame.version == 1)
        .order_by(Frame.order_index)
    )
    rows = list(result.scalars().all())
    if rows:
        canonical_frames = [frame_row_to_dsl(frame) for frame in rows]
        snapshot["frames"] = canonical_frames
        module_outputs = deepcopy(snapshot.get("module_outputs") or {})
        frames_output = module_outputs.get("frames")
        if isinstance(frames_output, dict):
            frames_output = deepcopy(frames_output)
            frames_output["frames"] = deepcopy(canonical_frames)
            module_outputs["frames"] = frames_output
            snapshot["module_outputs"] = module_outputs
        return snapshot
    return resolve_export_dsl(snapshot)
