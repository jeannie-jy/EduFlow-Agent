"""DomainPlugin 协议 — 领域插件接口。

新学科接入时实现此协议。
对齐：设计文档 v1.0 Section 8.2。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DomainPlugin(Protocol):
    """领域插件协议。

    每个学科（CS、数学、物理等）实现此协议以注册：
    - 知识点模板
    - 可视化对象类型
    - 参数生成规则
    - 教学策略模板
    - 质量检查规则
    """

    # ── 元信息 ──────────────────────────────────────────────

    domain_name: str
    """领域标识: computer_science / mathematics / physics / ..."""

    version: str
    """插件版本号"""

    display_name: str
    """用户可读的名称: 计算机科学 / 数学 / 物理学 / ..."""

    # ── 方法 ────────────────────────────────────────────────

    def get_knowledge_templates(self) -> list[dict[str, Any]]:
        """该领域的预置知识点模板。

        Returns:
            每个模板包含 concept、content、subject、difficulty、
            object_types、animation_types 等字段。
        """
        ...

    def get_visual_objects(self) -> dict[str, dict[str, Any]]:
        """该领域特有的可视化对象类型及渲染规格。

        Returns:
            {"object_type": {"description": ..., "default_style": ...}}
        """
        ...

    def get_parameter_rules(self, knowledge_type: str) -> list[dict[str, Any]]:
        """该领域知识点的参数生成规则。

        Args:
            knowledge_type: 知识点类型（如 algorithm / data_structure）

        Returns:
            参数定义列表
        """
        ...

    def get_teaching_strategies(self) -> list[dict[str, Any]]:
        """该领域推荐的教学策略模板。

        Returns:
            每个策略包含 name、approach、适用场景等
        """
        ...

    def get_quality_rules(self) -> list[dict[str, Any]]:
        """该领域特有的质量检查规则。

        Returns:
            规则列表，每项包含 type、rule、severity、description
        """
        ...


# ── 插件注册表 ────────────────────────────────────────────────


_plugins: dict[str, DomainPlugin] = {}


def register_plugin(plugin: DomainPlugin) -> None:
    """注册领域插件。"""
    _plugins[plugin.domain_name] = plugin


def get_plugin(domain: str) -> DomainPlugin | None:
    """获取已注册的领域插件。"""
    return _plugins.get(domain)


def list_plugins() -> list[DomainPlugin]:
    """列出所有已注册的插件。"""
    return list(_plugins.values())
