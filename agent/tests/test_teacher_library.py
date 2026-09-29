"""Teacher library ownership and project-link regression checks."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.materials import (
    _require_library_owner,
    add_material_to_library,
    attach_library_material,
    list_teacher_library,
)
from services.teacher_library import (
    attach_material_to_project,
    enable_library_material,
    list_project_materials,
    teacher_source_key,
)


def _row_result(row):
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    return result


def test_teacher_library_requires_a_signed_in_teacher():
    with pytest.raises(HTTPException) as missing:
        _require_library_owner(None)
    assert missing.value.status_code == 401
    with pytest.raises(HTTPException) as student:
        _require_library_owner(SimpleNamespace(id=uuid.uuid4(), role="student"))
    assert student.value.status_code == 403


@pytest.mark.asyncio
async def test_enable_library_is_owner_scoped_and_does_not_index_or_embed():
    material_id, owner_id, source_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    session = AsyncMock()
    session.execute.side_effect = [
        _row_result({"id": material_id, "original_filename": "notes.pdf"}),
        MagicMock(),
        _row_result({
            "id": source_id, "scope": "teacher", "owner_id": owner_id,
            "material_id": material_id,
        }),
    ]
    result = await enable_library_material(session, material_id=material_id, owner_id=owner_id)
    assert result == {"material_id": str(material_id), "source_id": str(source_id)}
    update_sql, update_params = session.execute.await_args_list[0].args
    assert "owner_id = :owner_id" in str(update_sql)
    assert "expires_at = NULL" in str(update_sql)
    assert update_params["owner_id"] == owner_id
    insert_sql = str(session.execute.await_args_list[1].args[0])
    assert "'draft'" in insert_sql
    assert "ON CONFLICT (source_key) DO NOTHING" in insert_sql
    assert teacher_source_key(material_id) == f"teacher-{material_id}"


@pytest.mark.asyncio
async def test_enable_library_rejects_other_owner_without_creating_source():
    session = AsyncMock()
    session.execute.return_value = _row_result(None)
    with pytest.raises(LookupError):
        await enable_library_material(
            session, material_id=uuid.uuid4(), owner_id=uuid.uuid4()
        )
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_project_attachment_is_scoped_in_both_database_statements():
    owner_id, project_id, material_id, source_id = (
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    )
    session = AsyncMock()
    session.execute.side_effect = [MagicMock(), _row_result({"source_id": source_id})]
    attached = await attach_material_to_project(
        session, project_id=project_id, material_id=material_id, owner_id=owner_id
    )
    assert attached == source_id
    for call in session.execute.await_args_list:
        statement, params = call.args
        sql = str(statement)
        assert "p.owner_id = :owner_text" in sql
        assert "m.owner_id = :owner_id" in sql
        assert "s.owner_id = :owner_id" in sql
        assert params["owner_text"] == str(owner_id)
        assert params["owner_id"] == owner_id


@pytest.mark.asyncio
async def test_cross_owner_or_nonlibrary_attachment_returns_not_found():
    session = AsyncMock()
    session.execute.side_effect = [MagicMock(), _row_result(None)]
    with pytest.raises(LookupError):
        await attach_material_to_project(
            session, project_id=uuid.uuid4(), material_id=uuid.uuid4(),
            owner_id=uuid.uuid4(),
        )
    assert "m.is_library" in str(session.execute.await_args_list[0].args[0])


@pytest.mark.asyncio
async def test_project_material_listing_hides_foreign_project_before_querying_links():
    session = AsyncMock()
    exists = MagicMock()
    exists.scalar_one_or_none.return_value = None
    session.execute.return_value = exists
    with pytest.raises(LookupError):
        await list_project_materials(
            session, project_id=uuid.uuid4(), owner_id=uuid.uuid4()
        )
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_project_material_listing_filters_owner_in_query():
    session = AsyncMock()
    exists = MagicMock()
    exists.scalar_one_or_none.return_value = 1
    rows = MagicMock()
    rows.mappings.return_value.all.return_value = []
    session.execute.side_effect = [exists, rows]
    owner_id = uuid.uuid4()
    assert await list_project_materials(
        session, project_id=uuid.uuid4(), owner_id=owner_id
    ) == []
    sql, params = session.execute.await_args.args
    assert "p.owner_id = :owner_text" in str(sql)
    assert "m.owner_id = :owner_id" in str(sql)
    assert "s.owner_id = :owner_id" in str(sql)
    assert params["owner_text"] == str(owner_id)


@pytest.mark.asyncio
async def test_library_api_rejects_anonymous_and_uses_owned_service():
    session = AsyncMock()
    with pytest.raises(HTTPException) as missing:
        await add_material_to_library(str(uuid.uuid4()), session, None, None)
    assert missing.value.status_code == 401
    session.execute.assert_not_awaited()
    owner = SimpleNamespace(id=uuid.uuid4(), role="teacher")
    material_id = uuid.uuid4()
    with patch("services.teacher_library.enable_library_material", new_callable=AsyncMock) as enable:
        enable.return_value = {"material_id": str(material_id), "source_id": str(uuid.uuid4())}
        with patch("api.materials.record_audit"):
            result = await add_material_to_library(str(material_id), session, owner, owner)
    assert result["index_status"] == "draft"
    assert enable.await_args.kwargs["owner_id"] == owner.id


@pytest.mark.asyncio
async def test_attach_api_hides_foreign_project_or_material():
    owner = SimpleNamespace(id=uuid.uuid4(), role="teacher")
    with patch("services.teacher_library.attach_material_to_project", new_callable=AsyncMock) as attach:
        attach.side_effect = LookupError("not found")
        with pytest.raises(HTTPException) as hidden:
            await attach_library_material(
                str(uuid.uuid4()), str(uuid.uuid4()), AsyncMock(), owner, owner
            )
    assert hidden.value.status_code == 404


@pytest.mark.asyncio
async def test_library_list_uses_owner_filter():
    owner = SimpleNamespace(id=uuid.uuid4(), role="teacher")
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = []
    session.execute.return_value = result
    assert await list_teacher_library(session, owner) == {"items": []}
    statement, params = session.execute.await_args.args
    assert "m.owner_id = :owner_id" in str(statement)
    assert "s.owner_id = :owner_id" in str(statement)
    assert params["owner_id"] == owner.id
