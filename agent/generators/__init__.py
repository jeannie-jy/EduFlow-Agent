"""EduFlow-Agent 模块生成器系统。

每个模块（思维导图、知识卡片、Quiz、帧、视频等）都是一个独立的生成器，
通过注册表统一管理，用户可按需选择想要的产出形式。

模块生成器在应用启动时通过 register_generator() 注册。
"""

from .protocol import ModuleGenerator
from .registry import (
    clear_registry,
    get_generator,
    get_generators_by_category,
    has_generator,
    list_generators,
    register_generator,
)

__all__ = [
    "ModuleGenerator",
    "clear_registry",
    "get_generator",
    "get_generators_by_category",
    "has_generator",
    "list_generators",
    "register_generator",
]
