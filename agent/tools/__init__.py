"""Tool 层：Agent 可调用的工具函数。

- validate_dsl_schema: Pydantic 校验 + frame_id 检查
- check_state_consistency: 帧间状态一致性检查
- check_algorithm_invariants: 图算法状态不变量检查
- stabilize_algorithm_trace: 生成边界的确定性算法状态 Guardrail
- generate_asset: 多模态资源生成（card/mindmap/table/code_snippet）
- design_parameters: 参数设计工具（5 种知识类型模板）
- normalize_dsl: 生成边界的 RenderScript 兼容归一化

Agent-facing Function Calling definitions and execution live in
``services.tool_runtime``; this package retains deterministic internal tools.
"""

from .validate_dsl import (
    check_algorithm_invariants,
    check_state_consistency,
    stabilize_algorithm_trace,
    validate_dsl_schema,
)

from .generate_asset import (
    generate_asset,
)

from .design_parameters import (
    design_parameters,
)
from .normalize_dsl import normalize_dsl

__all__ = [
    # validate_dsl
    "validate_dsl_schema",
    "check_state_consistency",
    "check_algorithm_invariants",
    "stabilize_algorithm_trace",
    # generate_asset
    "generate_asset",
    # design_parameters
    "design_parameters",
    # normalize_dsl
    "normalize_dsl",
]
