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

from .algorithm_trace_compiler import compile_algorithm_trace
from .design_parameters import (
    design_parameters,
)
from .generate_asset import (
    generate_asset,
)
from .normalize_dsl import normalize_dsl
from .sorting_trace_compiler import compile_sorting_trace
from .validate_dsl import (
    check_algorithm_invariants,
    check_state_consistency,
    stabilize_algorithm_trace,
    validate_dsl_schema,
)

__all__ = [
    "check_algorithm_invariants",
    "check_state_consistency",
    "compile_algorithm_trace",
    "compile_sorting_trace",
    # design_parameters
    "design_parameters",
    # generate_asset
    "generate_asset",
    # normalize_dsl
    "normalize_dsl",
    "stabilize_algorithm_trace",
    # validate_dsl
    "validate_dsl_schema",
]
