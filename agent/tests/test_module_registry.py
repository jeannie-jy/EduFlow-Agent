"""ModuleGenerator 注册表单元测试。

测试 register/get/list/get_by_category/has/clear 全部功能。
"""

from __future__ import annotations

from typing import Any

import pytest

from generators.protocol import ModuleGenerator
from generators.registry import (
    clear_registry,
    get_generator,
    get_generators_by_category,
    has_generator,
    list_generators,
    register_generator,
)


# ============================================================================
# Mock Generator
# ============================================================================


class _MockGenerator:
    """最小 ModuleGenerator 实现，用于测试注册表。"""

    module_id = "mock_test"
    display_name = "Mock Test"
    description = "A mock generator for testing"
    icon = "test"
    category = "visual"
    priority = 5
    version = "0.1.0"

    async def generate(self, **kwargs: Any) -> dict[str, Any]:
        return {"mock": True}

    def validate(self, output: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def get_output_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"mock": {"type": "boolean"}}}

    def get_system_prompt(self) -> str:
        return "You are a mock generator."


class _MockGeneratorB:
    """第二个 mock 生成器，不同分类。"""

    module_id = "mock_export"
    display_name = "Mock Export"
    description = "Export mock"
    icon = "export"
    category = "export"
    priority = 3
    version = "1.0.0"

    async def generate(self, **kwargs: Any) -> dict[str, Any]:
        return {"exported": True}

    def validate(self, output: dict[str, Any]) -> list[dict[str, Any]]:
        if not output.get("exported"):
            return [{"severity": "high", "type": "missing", "description": "Missing exported"}]
        return []

    def get_output_schema(self) -> dict[str, Any]:
        return {"type": "object"}

    def get_system_prompt(self) -> str:
        return "Export mock."


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _clean_registry():
    """每个测试前后清空注册表。"""
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def mock_gen() -> _MockGenerator:
    return _MockGenerator()


@pytest.fixture
def mock_gen_b() -> _MockGeneratorB:
    return _MockGeneratorB()


# ============================================================================
# Protocol Compliance
# ============================================================================


class TestProtocolCompliance:
    """验证 mock 对象满足 ModuleGenerator 协议。"""

    def test_mock_gen_is_module_generator(self, mock_gen):
        assert isinstance(mock_gen, ModuleGenerator)

    def test_mock_gen_has_module_id(self, mock_gen):
        assert mock_gen.module_id == "mock_test"

    def test_mock_gen_generate_is_callable(self, mock_gen):
        assert callable(mock_gen.generate)

    def test_mock_gen_validate_is_callable(self, mock_gen):
        assert callable(mock_gen.validate)


# ============================================================================
# Register
# ============================================================================


class TestRegister:
    """测试 register_generator。"""

    def test_register_adds_to_registry(self, mock_gen):
        register_generator(mock_gen)
        assert has_generator("mock_test")

    def test_register_same_id_overwrites(self, mock_gen):
        register_generator(mock_gen)

        class V2:
            module_id = "mock_test"
            display_name = "Mock v2"
            description = "v2"
            icon = "test"
            category = "visual"
            priority = 1
            version = "2.0.0"

            async def generate(self, **kw: Any) -> dict[str, Any]:
                return {"v2": True}

            def validate(self, o: dict[str, Any]) -> list[dict[str, Any]]:
                return []

            def get_output_schema(self) -> dict[str, Any]:
                return {"type": "object"}

            def get_system_prompt(self) -> str:
                return "v2"

        register_generator(V2())
        gen = get_generator("mock_test")
        assert gen is not None
        assert gen.display_name == "Mock v2"

    def test_register_multiple_generators(self, mock_gen, mock_gen_b):
        register_generator(mock_gen)
        register_generator(mock_gen_b)
        assert len(list_generators()) == 2


# ============================================================================
# Get
# ============================================================================


class TestGet:
    """测试 get_generator。"""

    def test_get_existing_generator(self, mock_gen):
        register_generator(mock_gen)
        result = get_generator("mock_test")
        assert result is mock_gen

    def test_get_non_existent_returns_none(self):
        assert get_generator("nonexistent") is None

    def test_get_case_sensitive(self, mock_gen):
        register_generator(mock_gen)
        assert get_generator("MOCK_TEST") is None


# ============================================================================
# List
# ============================================================================


class TestList:
    """测试 list_generators。"""

    def test_list_empty_registry(self):
        assert list_generators() == []

    def test_list_returns_all_registered(self, mock_gen, mock_gen_b):
        register_generator(mock_gen)
        register_generator(mock_gen_b)
        result = list_generators()
        assert len(result) == 2
        ids = {g.module_id for g in result}
        assert ids == {"mock_test", "mock_export"}

    def test_list_returns_actual_instances(self, mock_gen):
        register_generator(mock_gen)
        result = list_generators()
        assert result[0] is mock_gen


# ============================================================================
# Get by Category
# ============================================================================


class TestGetByCategory:
    """测试 get_generators_by_category。"""

    def test_filter_by_category(self, mock_gen, mock_gen_b):
        register_generator(mock_gen)
        register_generator(mock_gen_b)

        visual = get_generators_by_category("visual")
        assert len(visual) == 1
        assert visual[0].module_id == "mock_test"

        export = get_generators_by_category("export")
        assert len(export) == 1
        assert export[0].module_id == "mock_export"

    def test_filter_by_category_empty(self, mock_gen):
        register_generator(mock_gen)
        assert get_generators_by_category("interactive") == []

    def test_filter_by_category_empty_registry(self):
        assert get_generators_by_category("visual") == []


# ============================================================================
# Has
# ============================================================================


class TestHas:
    """测试 has_generator。"""

    def test_has_existing(self, mock_gen):
        register_generator(mock_gen)
        assert has_generator("mock_test") is True

    def test_has_missing(self):
        assert has_generator("nonexistent") is False

    def test_has_after_clear(self, mock_gen):
        register_generator(mock_gen)
        clear_registry()
        assert has_generator("mock_test") is False


# ============================================================================
# Clear
# ============================================================================


class TestClear:
    """测试 clear_registry。"""

    def test_clear_empties_registry(self, mock_gen, mock_gen_b):
        register_generator(mock_gen)
        register_generator(mock_gen_b)
        clear_registry()
        assert list_generators() == []

    def test_clear_idempotent(self):
        clear_registry()
        clear_registry()
        assert list_generators() == []

    def test_clear_then_register(self, mock_gen):
        register_generator(mock_gen)
        clear_registry()
        register_generator(mock_gen)
        assert len(list_generators()) == 1
