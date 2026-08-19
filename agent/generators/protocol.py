"""ModuleGenerator Protocol — 模块生成器接口协议。

每个教学产出模块（思维导图、知识卡片、Quiz、帧、视频等）实现此协议。
复用 DomainPlugin 的设计模式（agent/plugins/domain_plugin.py）。
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Protocol, runtime_checkable


@runtime_checkable
class ModuleGenerator(Protocol):
    """模块生成器协议。

    每个模块生成器是一个独立的教学产出单元，拥有自己的 LLM 提示词、
    输出 schema 和校验逻辑。通过注册表统一管理，用户可按需选择。
    """

    # ── 元信息（类属性） ──────────────────────────────────────

    module_id: str
    """模块唯一标识: mindmap / cards / quiz / frames / video / comparison / ..."""

    display_name: str
    """用户可读名称: 思维导图 / 知识卡片 / 小练习 / ..."""

    description: str
    """一句话功能描述，展示在模块选择器中"""

    icon: str
    """前端图标标识: mindmap / cards / quiz / play / video / ..."""

    category: str
    """模块分类: visual | interactive | export"""

    priority: int
    """默认推荐优先级 1-10，数值越小越优先展示"""

    version: str
    """模块版本号"""

    # ── 核心方法 ──────────────────────────────────────────────

    async def generate(
        self,
        teaching_plan: dict[str, Any],
        knowledge_graph: dict[str, Any],
        user_input: str,
        constraints: dict[str, Any],
        project_id: str,
    ) -> dict[str, Any]:
        """执行生成，返回模块特有产出。

        Args:
            teaching_plan: Planner 产出的教学计划
            knowledge_graph: Knowledge Agent 产出的知识图谱
            user_input: 用户原始输入
            constraints: 教师约束
            project_id: 项目 ID

        Returns:
            模块特有的产出字典，格式由各模块定义。
        """
        ...

    def validate(self, output: dict[str, Any]) -> list[dict[str, Any]]:
        """校验模块产出，返回问题列表。

        Args:
            output: generate() 的返回值

        Returns:
            问题列表，每项包含 severity, type, description。空列表 = 通过。
        """
        ...

    def get_output_schema(self) -> dict[str, Any]:
        """返回该模块产出的 JSON Schema，供 LLM structured output 使用。"""
        ...

    def get_system_prompt(self) -> str:
        """返回该模块的 LLM 系统提示词。"""
        ...
