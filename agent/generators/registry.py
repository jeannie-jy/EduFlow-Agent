"""ModuleGenerator 注册表。

所有模块生成器通过 register_generator() 注册，通过 get_generator() 查询。
复用 DomainPlugin 注册表模式（agent/plugins/domain_plugin.py:85-100）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .protocol import ModuleGenerator

# ── 注册表 ──────────────────────────────────────────────────────

_registry: dict[str, "ModuleGenerator"] = {}


def register_generator(gen: "ModuleGenerator") -> None:
    """注册模块生成器。重复注册同一 module_id 会覆盖旧值。

    Args:
        gen: 实现 ModuleGenerator 协议的对象
    """
    _registry[gen.module_id] = gen


def get_generator(module_id: str) -> "ModuleGenerator | None":
    """获取已注册的模块生成器。

    Args:
        module_id: 模块唯一标识

    Returns:
        ModuleGenerator 或 None
    """
    return _registry.get(module_id)


def list_generators() -> list["ModuleGenerator"]:
    """列出所有已注册的模块生成器。"""
    return list(_registry.values())


def get_generators_by_category(category: str) -> list["ModuleGenerator"]:
    """按分类获取模块生成器。

    Args:
        category: visual | interactive | export

    Returns:
        匹配的生成器列表
    """
    return [g for g in _registry.values() if g.category == category]


def has_generator(module_id: str) -> bool:
    """检查模块生成器是否已注册。"""
    return module_id in _registry


def clear_registry() -> None:
    """清空注册表（仅测试用）。"""
    _registry.clear()
