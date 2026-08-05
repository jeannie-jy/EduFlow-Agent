"""Tool 层：Agent 可调用的工具函数。

- validate_dsl_schema: Pydantic 校验 + frame_id 检查
- check_state_consistency: 帧间状态一致性检查
- generate_asset: 多模态资源生成（card/mindmap/table/code_snippet）
- design_parameters: 参数设计工具（5 种知识类型模板）

注：早期 function-calling 设计的 TOOL_DEF_* 元数据已全部移除
（节点直接以 async 函数调用这些工具，无 function calling 消费方）。
"""

from .validate_dsl import (
    check_state_consistency,
    validate_dsl_schema,
)

from .generate_asset import (
    generate_asset,
)

from .design_parameters import (
    design_parameters,
)

__all__ = [
    # validate_dsl
    "validate_dsl_schema",
    "check_state_consistency",
    # generate_asset
    "generate_asset",
    # design_parameters
    "design_parameters",
]
