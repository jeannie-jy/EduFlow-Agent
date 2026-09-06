"""参数 API 路由。

GET    /api/projects/{id}/parameters      参数列表
POST   /api/projects/{id}/recompute       参数变更触发重算
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from copy import deepcopy
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_readonly_session, get_session
from db.models import User
from schema.project import RecomputeRequest
from services.audit import record_audit
from services.parameter_dependencies import (
    analyze_parameter_impact,
    expand_module_impact,
)
from services.parameter_validation import validate_parameter_changes

from .auth import get_current_user
from .deps import parse_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["parameters"])


@router.get("/{project_id}/parameters")
async def list_parameters(
    project_id: str,
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    """获取项目的参数列表。"""
    # 优先从 DSL snapshot 获取
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project and project.dsl_snapshot:
        params = deepcopy(project.dsl_snapshot.get("parameters", []))
        if params:
            for p in params:
                if "id" not in p:
                    p["id"] = str(uuid.uuid4())
            return {"parameters": params}

    # 从 DB 查询
    from sqlalchemy import select

    from db.models import ParameterModel

    query = select(ParameterModel).where(
        ParameterModel.project_id == parse_project_id(project_id)
    )
    result = await session.execute(query)
    params = result.scalars().all()

    return {
        "parameters": [
            {
                "id": str(p.id),
                "key": p.key,
                "label": p.label,
                "param_type": p.param_type,
                "default_value": p.default_value,
                "current_value": p.current_value,
                "constraints": p.constraints or {},
                "recompute_scope": p.recompute_scope,
                "affects_frame_ids": [],
            }
            for p in params
        ],
    }


async def _load_definitions(
    project, project_id: str, session: AsyncSession
) -> list[dict]:
    from sqlalchemy import select

    from db.models import ParameterModel

    snapshot_parameters = deepcopy((project.dsl_snapshot or {}).get("parameters", []))
    if snapshot_parameters:
        return snapshot_parameters
    result = await session.execute(
        select(ParameterModel).where(
            ParameterModel.project_id == parse_project_id(project_id)
        )
    )
    return [
        {
            "key": parameter.key,
            "param_type": parameter.param_type,
            "constraints": parameter.constraints or {},
            "recompute_scope": parameter.recompute_scope,
        }
        for parameter in result.scalars().all()
    ]


def _impact_or_422(project, definitions: list[dict], changed_params: dict) -> dict:
    try:
        validation_mode = validate_parameter_changes(definitions, changed_params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    snapshot = project.dsl_snapshot or {}
    impact = analyze_parameter_impact(
        definitions,
        snapshot.get("frames", []),
        list(changed_params),
        validation_mode,
    )
    selected_raw = snapshot.get("selected_modules", [])
    if not isinstance(selected_raw, list):
        selected_raw = []
    selected_modules = [
        str(module_id) for module_id in selected_raw
        if module_id
    ]
    module_outputs = snapshot.get("module_outputs") or {}
    if not isinstance(module_outputs, dict):
        module_outputs = {}
    module_ids = list(dict.fromkeys([*selected_modules, *module_outputs.keys()]))
    raw_dependency_map = snapshot.get("module_dependencies") or {}
    if not isinstance(raw_dependency_map, dict):
        raw_dependency_map = {}
    dependency_map = {
        str(module_id): [str(dependency) for dependency in dependencies]
        for module_id, dependencies in raw_dependency_map.items()
        if isinstance(dependencies, list)
    }
    if not dependency_map:
        # Backfill dependency metadata for projects generated before this field
        # was persisted. Registry metadata is declarative; it never executes a module.
        from generators.registry import get_generator

        for module_id in module_ids:
            generator = get_generator(module_id)
            if generator is not None:
                dependency_map[module_id] = list(getattr(generator, "requires", ()))
    module_impact = expand_module_impact(
        module_ids,
        dependency_map,
        [] if validation_mode == "local" else ["frames"],
    )
    impact.update(module_impact)
    token_payload = {
        "artifact_version": snapshot.get("artifact_version"),
        "definitions": definitions,
        "frames": snapshot.get("frames", []),
        "changed_params": changed_params,
        "impact": impact,
    }
    impact["impact_token"] = hashlib.sha256(
        json.dumps(
            token_payload, ensure_ascii=False, sort_keys=True, default=str
        ).encode("utf-8")
    ).hexdigest()
    return impact


@router.post("/{project_id}/recompute/preview")
async def preview_recompute_project(
    project_id: str,
    body: RecomputeRequest,
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    """Validate changes and preview their deterministic frame impact without writes."""
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    definitions = await _load_definitions(project, project_id, session)
    return _impact_or_422(project, definitions, body.changed_params)


@router.post("/{project_id}/recompute", status_code=202)
async def recompute_project(
    project_id: str,
    body: RecomputeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
) -> dict:
    """参数变更触发状态重算。"""
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    changed_params = body.changed_params

    logger.info(
        "重算: project=%s | changed_keys=%s", project_id, list(changed_params.keys())
    )

    # 更新参数值 —— 双真源同步：
    # list_parameters 优先读 dsl_snapshot.parameters，因此表与 snapshot 必须一起更新，
    # 否则前端参数面板读到的永远是旧值（此前只更新表 → snapshot 永不生效）。
    from sqlalchemy import update

    from db.models import ParameterModel

    definitions = await _load_definitions(project, project_id, session)
    impact = _impact_or_422(project, definitions, changed_params)
    if (
        body.expected_impact_token
        and body.expected_impact_token != impact["impact_token"]
    ):
        raise HTTPException(
            status_code=409,
            detail="Project state changed after preview; preview the impact again",
        )
    recompute_mode = impact["mode"]

    for key, value in changed_params.items():
        await session.execute(
            update(ParameterModel)
            .where(
                ParameterModel.project_id == parse_project_id(project_id),
                ParameterModel.key == key,
            )
            .values(current_value=value)
        )

    if project.dsl_snapshot:
        snap = dict(project.dsl_snapshot)
        snap_params = deepcopy(snap.get("parameters", []))
        for p in snap_params:
            if isinstance(p, dict) and p.get("key") in changed_params:
                p["current_value"] = changed_params[p["key"]]
        snap["parameters"] = snap_params
        downstream_modules = [
            module_id
            for module_id in impact["affected_module_ids"]
            if module_id != "frames"
        ]
        if downstream_modules:
            existing_stale = snap.get("stale_module_ids", [])
            if not isinstance(existing_stale, list):
                existing_stale = []
            snap["stale_module_ids"] = list(dict.fromkeys([
                *existing_stale,
                *downstream_modules,
            ]))
        project.dsl_snapshot = snap
        project.current_version_id = None

    record_audit(
        session,
        action="parameters.recompute",
        resource_type="project",
        resource_id=project_id,
        actor_id=current_user.id if current_user is not None else None,
        details={
            "changed_keys": sorted(changed_params),
            "mode": recompute_mode,
            "affected_module_ids": impact["affected_module_ids"],
        },
    )

    if recompute_mode == "local":
        from api.versions import save_version

        await save_version(
            project_id,
            project.dsl_snapshot or {},
            "本地参数变更",
            session,
        )
        return {**impact, "stream_url": None}

    scope = impact["scope"]
    stream_id = str(uuid.uuid4())
    return {
        **impact,
        "stream_url": (
            f"/api/projects/{project_id}/generate/regenerate/stream?"
            + urlencode(
                {
                    "scope": json.dumps(scope, separators=(",", ":")),
                    "stream_id": stream_id,
                }
            )
        ),
    }
