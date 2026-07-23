"""LLM 客户端单元测试。

覆盖 call_llm、call_llm_structured、generate_embedding、客户端单例。
所有测试使用 mock，不依赖真实 API。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import AsyncOpenAI

from agents.llm_client import (
    _get_llm_client,
    _get_embedding_client,
    call_llm,
    call_llm_structured,
    generate_embedding,
    create_llm_client,
    create_embedding_client,
)


# ============================================================================
# 客户端单例
# ============================================================================


class TestClientSingleton:
    """单例模式测试。"""

    def test_get_llm_client_returns_same_instance(self):
        """多次调用 _get_llm_client 应返回同一实例。"""
        # 重置全局状态
        import agents.llm_client as llm_mod
        llm_mod._llm_client = None

        c1 = _get_llm_client()
        c2 = _get_llm_client()
        assert c1 is c2

    def test_get_embedding_client_returns_same_instance(self):
        """多次调用 _get_embedding_client 应返回同一实例。"""
        import agents.llm_client as llm_mod
        llm_mod._embedding_client = None

        c1 = _get_embedding_client()
        c2 = _get_embedding_client()
        assert c1 is c2

    def test_create_llm_client_is_alias(self):
        """create_llm_client 是 _get_llm_client 的别名。"""
        import agents.llm_client as llm_mod
        llm_mod._llm_client = None

        c = create_llm_client()
        assert isinstance(c, AsyncOpenAI)

    def test_create_embedding_client_is_alias(self):
        """create_embedding_client 是 _get_embedding_client 的别名。"""
        import agents.llm_client as llm_mod
        llm_mod._embedding_client = None

        c = create_embedding_client()
        assert isinstance(c, AsyncOpenAI)

    def test_llm_client_uses_config_endpoint(self):
        """LLM 客户端应使用配置中的 endpoint。"""
        import agents.llm_client as llm_mod
        llm_mod._llm_client = None

        from config import get_settings
        settings = get_settings()
        c = _get_llm_client()
        assert settings.llm_endpoint in str(c.base_url)

    def test_embedding_client_uses_config_endpoint(self):
        """Embedding 客户端应使用配置中的 endpoint。"""
        import agents.llm_client as llm_mod
        llm_mod._embedding_client = None

        from config import get_settings
        settings = get_settings()
        c = _get_embedding_client()
        assert settings.embedding_endpoint in str(c.base_url)


# ============================================================================
# call_llm
# ============================================================================


class TestCallLLM:
    """call_llm 函数测试。"""

    @pytest.mark.asyncio
    async def test_normal_text_response(self, mock_llm_client):
        """正常文本响应应返回 content。"""
        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = "这是一段 LLM 回复"
        message.tool_calls = None
        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150

        mock_llm_client.chat.completions.create.return_value = mock_response

        result = await call_llm(
            system_prompt="你是助手",
            user_message="你好",
            temperature=0.3,
        )

        assert result["content"] == "这是一段 LLM 回复"
        assert result["tool_calls"] == []
        assert result["usage"]["input"] == 100
        assert result["usage"]["output"] == 50

    @pytest.mark.asyncio
    async def test_tool_call_response(self, mock_llm_client):
        """function calling 响应应正确解析 tool_calls。"""
        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = None

        tc = MagicMock()
        tc.id = "call_001"
        tc.function.name = "output_structured_result"
        tc.function.arguments = json.dumps({"key": "value", "number": 42})
        message.tool_calls = [tc]

        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 200
        mock_response.usage.completion_tokens = 100
        mock_response.usage.total_tokens = 300

        mock_llm_client.chat.completions.create.return_value = mock_response

        result = await call_llm(
            system_prompt="你是助手",
            user_message="输出 JSON",
            tools=[{"type": "function", "function": {"name": "test", "parameters": {}}}],
        )

        assert result["content"] is None
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "output_structured_result"
        assert result["tool_calls"][0]["arguments"] == {"key": "value", "number": 42}

    @pytest.mark.asyncio
    async def test_empty_choices_returns_empty(self, mock_llm_client):
        """LLM 返回空 choices 时应安全降级。"""
        mock_response = MagicMock()
        mock_response.choices = []
        mock_llm_client.chat.completions.create.return_value = mock_response

        result = await call_llm(
            system_prompt="助手",
            user_message="测试",
        )

        assert result["content"] is None
        assert result["tool_calls"] == []
        assert result["usage"]["input"] == 0

    @pytest.mark.asyncio
    async def test_json_parse_error_in_tool_calls(self, mock_llm_client):
        """tool_calls 中 JSON 解析失败时应回退为 raw。"""
        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = None

        tc = MagicMock()
        tc.id = "call_001"
        tc.function.name = "test_tool"
        tc.function.arguments = "not valid json {{{"
        message.tool_calls = [tc]

        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_llm_client.chat.completions.create.return_value = mock_response

        result = await call_llm(
            system_prompt="助手",
            user_message="测试",
            tools=[{"type": "function", "function": {"name": "test", "parameters": {}}}],
        )

        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["arguments"] == {"raw": "not valid json {{{"}

    @pytest.mark.asyncio
    async def test_custom_model_override(self, mock_llm_client):
        """自定义 model 参数应传递给 API。"""
        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = "ok"
        message.tool_calls = None
        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.usage.total_tokens = 2

        mock_llm_client.chat.completions.create.return_value = mock_response

        await call_llm(
            system_prompt="助手",
            user_message="测试",
            model="custom-model-name",
        )

        call_kwargs = mock_llm_client.chat.completions.create.call_args
        assert call_kwargs is not None
        # 验证 model 参数被传递
        called_model = call_kwargs[1].get("model") if call_kwargs[1] else None
        assert called_model == "custom-model-name"

    @pytest.mark.asyncio
    async def test_no_tools_passed(self, mock_llm_client):
        """不传 tools 时，请求应不含 tool_choice。"""
        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = "ok"
        message.tool_calls = None
        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.usage.total_tokens = 2

        mock_llm_client.chat.completions.create.return_value = mock_response

        await call_llm(system_prompt="助手", user_message="测试")

        call_kwargs = mock_llm_client.chat.completions.create.call_args
        # 不应包含 tools 参数
        if call_kwargs and call_kwargs[1]:
            assert "tools" not in call_kwargs[1]

    @pytest.mark.asyncio
    async def test_max_tokens_default(self, mock_llm_client):
        """默认 max_tokens 应为 4096。"""
        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = "ok"
        message.tool_calls = None
        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.usage.total_tokens = 2

        mock_llm_client.chat.completions.create.return_value = mock_response

        await call_llm(system_prompt="助手", user_message="测试")

        call_kwargs = mock_llm_client.chat.completions.create.call_args
        if call_kwargs and call_kwargs[1]:
            assert call_kwargs[1].get("max_tokens") == 4096


# ============================================================================
# call_llm_structured
# ============================================================================


class TestCallLLMStructured:
    """call_llm_structured 函数测试。"""

    @pytest.mark.asyncio
    async def test_normal_structured_output(self, mock_llm_client):
        """正常结构化输出应正确解析。"""
        expected = {
            "name": "test",
            "items": [{"id": 1, "value": "hello"}],
            "count": 42,
        }

        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = None
        tc = MagicMock()
        tc.id = "call_001"
        tc.function.name = "output_structured_result"
        tc.function.arguments = json.dumps(expected)
        message.tool_calls = [tc]
        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150

        mock_llm_client.chat.completions.create.return_value = mock_response

        result = await call_llm_structured(
            system_prompt="你是助手",
            user_message="输出结构化数据",
            output_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "items": {"type": "array"},
                    "count": {"type": "integer"},
                },
            },
        )

        assert result == expected
        assert result["name"] == "test"
        assert result["count"] == 42

    @pytest.mark.asyncio
    async def test_uses_tool_choice_forced(self, mock_llm_client):
        """应使用 tool_choice 强制 function calling。"""
        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = None
        tc = MagicMock()
        tc.id = "call_001"
        tc.function.name = "output_structured_result"
        tc.function.arguments = json.dumps({"ok": True})
        message.tool_calls = [tc]
        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.usage.total_tokens = 2

        mock_llm_client.chat.completions.create.return_value = mock_response

        await call_llm_structured(
            system_prompt="助手",
            user_message="测试",
            output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        )

        call_kwargs = mock_llm_client.chat.completions.create.call_args
        if call_kwargs and call_kwargs[1]:
            tool_choice = call_kwargs[1].get("tool_choice")
            assert tool_choice is not None
            assert tool_choice["type"] == "function"
            assert tool_choice["function"]["name"] == "output_structured_result"

    @pytest.mark.asyncio
    async def test_empty_choices_raises(self, mock_llm_client):
        """空 choices 应抛出 RuntimeError。"""
        mock_response = MagicMock()
        mock_response.choices = []
        mock_llm_client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="empty response"):
            await call_llm_structured(
                system_prompt="助手",
                user_message="测试",
                output_schema={"type": "object", "properties": {}},
            )

    @pytest.mark.asyncio
    async def test_no_tool_calls_raises(self, mock_llm_client):
        """无 tool_calls 应抛出 RuntimeError（content filter 或 API 错误）。"""
        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = "I cannot do that"
        message.tool_calls = None
        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.usage.total_tokens = 2

        mock_llm_client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="no tool_calls"):
            await call_llm_structured(
                system_prompt="助手",
                user_message="测试",
                output_schema={"type": "object", "properties": {}},
            )

    @pytest.mark.asyncio
    async def test_json_parse_failure_raises(self, mock_llm_client):
        """tool_calls 中的 JSON 解析失败应抛出 RuntimeError。"""
        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = None
        tc = MagicMock()
        tc.id = "call_001"
        tc.function.name = "output_structured_result"
        tc.function.arguments = "not json {{{"  # 无效 JSON
        message.tool_calls = [tc]
        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.usage.total_tokens = 2

        mock_llm_client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="Failed to parse"):
            await call_llm_structured(
                system_prompt="助手",
                user_message="测试",
                output_schema={"type": "object", "properties": {}},
            )

    @pytest.mark.asyncio
    async def test_default_max_tokens(self, mock_llm_client):
        """默认 max_tokens 应为 8192。"""
        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = None
        tc = MagicMock()
        tc.id = "call_001"
        tc.function.name = "output_structured_result"
        tc.function.arguments = json.dumps({"ok": True})
        message.tool_calls = [tc]
        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.usage.total_tokens = 2

        mock_llm_client.chat.completions.create.return_value = mock_response

        await call_llm_structured(
            system_prompt="助手",
            user_message="测试",
            output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        )

        call_kwargs = mock_llm_client.chat.completions.create.call_args
        if call_kwargs and call_kwargs[1]:
            assert call_kwargs[1].get("max_tokens") == 8192

    @pytest.mark.asyncio
    async def test_temperature_default(self, mock_llm_client):
        """默认 temperature 应为 0.2。"""
        mock_response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = None
        tc = MagicMock()
        tc.id = "call_001"
        tc.function.name = "output_structured_result"
        tc.function.arguments = json.dumps({"x": 1})
        message.tool_calls = [tc]
        choice.message = message
        mock_response.choices = [choice]
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.usage.total_tokens = 2

        mock_llm_client.chat.completions.create.return_value = mock_response

        await call_llm_structured(
            system_prompt="助手",
            user_message="测试",
            output_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
        )

        call_kwargs = mock_llm_client.chat.completions.create.call_args
        if call_kwargs and call_kwargs[1]:
            assert call_kwargs[1].get("temperature") == 0.2


# ============================================================================
# generate_embedding
# ============================================================================


class TestGenerateEmbedding:
    """generate_embedding 函数测试。"""

    @pytest.mark.asyncio
    async def test_normal_embedding(self, mock_embedding_client):
        """正常 embedding 返回 float 列表。"""
        dim = 1536
        mock_response = MagicMock()
        embedding_data = MagicMock()
        embedding_data.embedding = [0.1] * dim
        mock_response.data = [embedding_data]
        mock_embedding_client.embeddings.create.return_value = mock_response

        result = await generate_embedding("测试文本")

        assert len(result) == dim
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.asyncio
    async def test_empty_data_raises(self, mock_embedding_client):
        """空 data 应抛出 RuntimeError。"""
        mock_response = MagicMock()
        mock_response.data = []
        mock_embedding_client.embeddings.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="empty"):
            await generate_embedding("测试")

    @pytest.mark.asyncio
    async def test_uses_configured_model(self, mock_embedding_client):
        """应使用配置中的 embedding_model。"""
        mock_response = MagicMock()
        embedding_data = MagicMock()
        embedding_data.embedding = [0.0] * 1536
        mock_response.data = [embedding_data]
        mock_embedding_client.embeddings.create.return_value = mock_response

        await generate_embedding("test")

        call_kwargs = mock_embedding_client.embeddings.create.call_args
        if call_kwargs and call_kwargs[1]:
            assert "model" in call_kwargs[1]
            assert call_kwargs[1]["input"] == "test"