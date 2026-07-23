"""Tool 层：Agent 可调用的工具函数。

- validate_dsl: DSL 确定性校验（Schema + 一致性）
- validate_dsl_schema: Pydantic 校验 + frame_id 检查
- check_state_consistency: 帧间状态一致性检查
- generate_asset: 多模态资源生成（card/mindmap/table/code_snippet）
- design_parameters: 参数设计工具（5 种知识类型模板）
"""

from .validate_dsl import (
    TOOL_DEF_CONSISTENCY,
    TOOL_DEF_VALIDATE,
    check_state_consistency,
    validate_dsl_schema,
)

from .generate_asset import (
    TOOL_DEF_GENERATE_ASSET,
    generate_asset,
)

from .design_parameters import (
    TOOL_DEF_DESIGN_PARAMETERS,
    design_parameters,
)

__all__ = [
    # validate_dsl
    "validate_dsl_schema",
    "check_state_consistency",
    "TOOL_DEF_VALIDATE",
    "TOOL_DEF_CONSISTENCY",
    # generate_asset
    "generate_asset",
    "TOOL_DEF_GENERATE_ASSET",
    # design_parameters
    "design_parameters",
    "TOOL_DEF_DESIGN_PARAMETERS",
]
