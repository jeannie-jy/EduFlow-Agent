"""validate_dsl_schema & check_state_consistency Tools。

DSL 校验工具：确定性检查，不依赖 LLM。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def validate_dsl_schema(dsl: dict[str, Any]) -> dict[str, Any]:
    """使用 Pydantic 校验 DSL 结构完整性。"""
    from schema.dsl import RenderScript

    errors: list[str] = []
    warnings: list[str] = []

    try:
        RenderScript.model_validate(dsl)
        valid = True
    except Exception as exc:
        valid = False
        errors.append(str(exc))

    # 额外检查：帧必须有 frame_id
    frames = dsl.get("frames", [])
    for i, frame in enumerate(frames):
        if not frame.get("frame_id"):
            errors.append(f"Frame at index {i} missing frame_id")
            valid = False

    # 检查：帧间 order 连续性
    if frames:
        frame_ids = [f.get("frame_id", f"unknown_{i}") for i, f in enumerate(frames)]
        if len(frame_ids) != len(set(frame_ids)):
            warnings.append("Duplicate frame_id detected")

    return {
        "valid": valid and len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


async def check_state_consistency(frames: list[dict[str, Any]]) -> dict[str, Any]:
    """检查帧间状态一致性。

    对于同一 state_snapshot 中的 key，检查帧间值的变化是否有序。
    """
    issues: list[dict[str, Any]] = []

    for i in range(len(frames) - 1):
        current = frames[i].get("state_snapshot", {})
        next_frame = frames[i + 1].get("state_snapshot", {})

        fid_current = frames[i].get("frame_id", f"f_{i}")
        fid_next = frames[i + 1].get("frame_id", f"f_{i + 1}")

        # 对于 distance_table 这类嵌套对象，检查非 ∞ 的值不应被意外重置
        for key in set(current.keys()) & set(next_frame.keys()):
            if isinstance(current[key], dict) and isinstance(next_frame[key], dict):
                for sub_key in current[key]:
                    cv = current[key].get(sub_key)
                    nv = next_frame[key].get(sub_key)
                    # 如果当前值已经是有效有限值，下一帧不应突然变回 ∞（除非显式重置）
                    if (
                        isinstance(cv, (int, float))
                        and isinstance(nv, (int, float))
                        and cv != float("inf")
                        and cv < 1_000_000
                    ):
                        if nv == float("inf") or nv > 1_000_000:
                            issues.append({
                                "frame_pair": [fid_current, fid_next],
                                "key": f"{key}.{sub_key}",
                                "current_value": cv,
                                "next_value": nv,
                                "description": f"有效值 {cv} 在下一帧变为 {nv}，可能是状态不一致",
                            })

    return {
        "consistent": len(issues) == 0,
        "issues": issues,
    }
