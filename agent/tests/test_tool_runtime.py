from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, ConfigDict, Field

from services.tool_runtime import (
    ToolExecutionContext,
    ToolRegistry,
    ToolSpec,
    execute_tool_call,
    run_tool_calling_loop,
)


class EchoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=20)


async def _echo(args: BaseModel, context: ToolExecutionContext) -> dict:
    assert isinstance(args, EchoArgs)
    return {"value": args.value, "project_id": str(context.project_id)}


def _registry(handler=_echo) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "1.0", "echo", EchoArgs, handler))
    return registry


@pytest.mark.asyncio
async def test_registered_tool_executes_with_server_project_context():
    project_id = uuid.uuid4()
    result = await execute_tool_call(
        {"id": "call-1", "name": "echo", "arguments": {"value": "ok"}},
        ToolExecutionContext(project_id),
        registry=_registry(),
    )
    assert result["status"] == "ok"
    assert result["data"]["project_id"] == str(project_id)


@pytest.mark.asyncio
async def test_unknown_tool_is_denied_without_execution():
    result = await execute_tool_call(
        {"id": "call-2", "name": "shell_exec", "arguments": {"cmd": "whoami"}},
        ToolExecutionContext(uuid.uuid4()),
        registry=_registry(),
    )
    assert result["status"] == "denied"
    assert result["error_code"] == "TOOL_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_invalid_arguments_are_rejected():
    result = await execute_tool_call(
        {
            "id": "call-3",
            "name": "echo",
            "arguments": {"value": "ok", "project_id": "foreign"},
        },
        ToolExecutionContext(uuid.uuid4()),
        registry=_registry(),
    )
    assert result["status"] == "invalid_arguments"


@pytest.mark.asyncio
async def test_timeout_returns_structured_error():
    async def slow(args: BaseModel, context: ToolExecutionContext) -> dict:
        await asyncio.sleep(0.05)
        return {}

    settings = type(
        "Settings", (), {"tool_timeout_seconds": 0.001, "tool_result_max_chars": 1000}
    )()
    with patch("services.tool_runtime.get_settings", return_value=settings):
        result = await execute_tool_call(
            {"id": "call-4", "name": "echo", "arguments": {"value": "ok"}},
            ToolExecutionContext(uuid.uuid4()),
            registry=_registry(slow),
        )
    assert result["status"] == "timeout"


@pytest.mark.asyncio
async def test_multiround_loop_feeds_tool_result_back_to_model():
    first = {
        "content": None,
        "usage": {"input": 120, "output": 20},
        "tool_calls": [
            {"id": "call-5", "name": "echo", "arguments": {"value": "evidence"}}
        ],
        "assistant_message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-5",
                    "type": "function",
                    "function": {"name": "echo", "arguments": '{"value":"evidence"}'},
                }
            ],
        },
    }
    second = {
        "content": "done",
        "usage": {"input": 80, "output": 10},
        "tool_calls": [],
        "assistant_message": {"role": "assistant", "content": "done", "tool_calls": []},
    }
    mocked = AsyncMock(side_effect=[first, second])
    with patch("agents.llm_client.call_llm", mocked):
        result = await run_tool_calling_loop(
            system_prompt="system",
            user_message="user",
            project_id=str(uuid.uuid4()),
            registry=_registry(),
        )
    assert result["content"] == "done"
    assert result["calls"][0]["status"] == "ok"
    assert result["usage"] == {"input": 200, "output": 30}
    second_conversation = mocked.call_args_list[1].kwargs["conversation"]
    assert any(message.get("role") == "tool" for message in second_conversation)


@pytest.mark.asyncio
async def test_tool_concurrency_limit_is_shared_across_workflows():
    in_flight = 0
    max_in_flight = 0

    async def bounded_echo(args: BaseModel, context: ToolExecutionContext) -> dict:
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return {"value": args.value}

    async def model_call(_system, _message, *, conversation, **_kwargs):
        if any(message.get("role") == "tool" for message in conversation):
            return {
                "content": "done",
                "tool_calls": [],
                "assistant_message": {
                    "role": "assistant",
                    "content": "done",
                    "tool_calls": [],
                },
            }
        call_id = f"call-{len(conversation)}-{id(conversation)}"
        return {
            "content": None,
            "tool_calls": [
                {"id": call_id, "name": "echo", "arguments": {"value": "ok"}}
            ],
            "assistant_message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": "echo",
                            "arguments": '{"value":"ok"}',
                        },
                    }
                ],
            },
        }

    settings = type(
        "Settings",
        (),
        {
            "tool_max_concurrency": 2,
            "tool_max_rounds": 2,
            "tool_max_calls": 4,
            "tool_timeout_seconds": 1,
            "tool_result_max_chars": 1000,
            "agent_timeout_ms": 5000,
        },
    )()
    with (
        patch("services.tool_runtime.get_settings", return_value=settings),
        patch("agents.llm_client.call_llm", new=model_call),
    ):
        results = await asyncio.gather(
            *(
                run_tool_calling_loop(
                    system_prompt="system",
                    user_message=f"workflow-{index}",
                    project_id=str(uuid.uuid4()),
                    registry=_registry(bounded_echo),
                )
                for index in range(6)
            )
        )

    assert all(result["content"] == "done" for result in results)
    assert max_in_flight == 2


def test_default_registry_exposes_only_three_read_only_tools():
    from services.tool_runtime import DEFAULT_TOOL_REGISTRY

    names = {item["function"]["name"] for item in DEFAULT_TOOL_REGISTRY.definitions()}
    assert names == {"knowledge_search", "material_lookup", "get_project_context"}
    schemas = [
        item["function"]["parameters"] for item in DEFAULT_TOOL_REGISTRY.definitions()
    ]
    assert all("project_id" not in schema.get("properties", {}) for schema in schemas)
    assert all("actor_id" not in schema.get("properties", {}) for schema in schemas)
    assert all(DEFAULT_TOOL_REGISTRY.get(name).read_only for name in names)


@pytest.mark.asyncio
async def test_knowledge_node_injects_real_tool_evidence_into_final_generation():
    from agents.nodes import knowledge_node
    from tests.conftest import AgentStateFactory

    tool_result = {
        "content": "evidence ready",
        "calls": [
            {
                "tool_call_id": "call-knowledge",
                "tool": "knowledge_search",
                "version": "1.0",
                "status": "ok",
                "data": {
                    "status": "ok",
                    "sources": [
                        {"source_id": "doc-1", "content": "nonnegative weights"}
                    ],
                },
                "error_code": None,
                "duration_ms": 2.0,
                "truncated": False,
            }
        ],
        "exhausted": False,
        "rounds": 1,
    }
    generated = {
        "concepts": [{"id": "c1", "name": "Dijkstra", "type": "algorithm"}],
        "edges": [],
        "key_terms": ["Dijkstra"],
    }
    state = AgentStateFactory.with_plan()
    state["enable_tools"] = True
    state["enable_retrieval"] = True
    with (
        patch(
            "services.tool_runtime.run_tool_calling_loop",
            new=AsyncMock(return_value=tool_result),
        ),
        patch(
            "agents.nodes.call_llm_structured", new=AsyncMock(return_value=generated)
        ) as final_llm,
    ):
        result = await knowledge_node(state)

    assert result["retrieval"]["sources"][0]["source_id"] == "doc-1"
    assert result["tool_calls"][0]["tool"] == "knowledge_search"
    assert "nonnegative weights" in final_llm.call_args.kwargs["user_message"]
