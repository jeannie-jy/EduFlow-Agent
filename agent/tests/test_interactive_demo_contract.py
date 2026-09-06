from unittest.mock import AsyncMock, patch

import pytest

from generators.base import _bound_output_to_schema
from generators.interactive_demo_generator import (
    INTERACTIVE_DEMO_OUTPUT_SCHEMA,
    INTERACTIVE_DEMO_SYSTEM_PROMPT,
    InteractiveDemoGenerator,
)


def test_interactive_demo_prompt_requires_shared_workbench_structure():
    required_classes = (
        "eduflow-demo__header",
        "eduflow-demo__stage",
        "eduflow-demo__visual",
        "eduflow-demo__status",
        "eduflow-demo__explanation",
        "eduflow-demo__controls",
        "eduflow-demo__timeline",
        "eduflow-demo__timeline-item",
    )

    for class_name in required_classes:
        assert class_name in INTERACTIVE_DEMO_SYSTEM_PROMPT

    assert "不得依赖 Tailwind CDN" in INTERACTIVE_DEMO_SYSTEM_PROMPT
    assert "360px 到 1600px" in INTERACTIVE_DEMO_SYSTEM_PROMPT
    assert "9000 字符" in INTERACTIVE_DEMO_SYSTEM_PROMPT


def test_syntax_bearing_output_is_never_cut_after_generation():
    source = "const InteractiveDemo = () => { return <div />; };" + (" " * 15000)
    bounded = _bound_output_to_schema(
        {"code": source},
        INTERACTIVE_DEMO_OUTPUT_SCHEMA,
    )
    assert bounded["code"] == source


@pytest.mark.asyncio
async def test_truncated_component_uses_local_fallback_without_second_llm_call():
    generator = InteractiveDemoGenerator()
    truncated = "const InteractiveDemo = () => { return (<div>" + ("x" * 9000)
    with patch(
        "agents.llm_client.call_llm_structured",
        new=AsyncMock(return_value={"code": truncated}),
    ) as llm:
        result = await generator.generate(
            teaching_plan={"objectives": ["理解红黑树"], "outline": [{"title": "插入修复"}]},
            knowledge_graph={"concepts": [{"name": "颜色性质"}]},
            user_input="红黑树",
            constraints={},
            project_id="test-project",
        )

    assert llm.await_count == 1
    assert llm.await_args.kwargs["max_tokens"] == 8192
    assert result["generation_mode"] == "deterministic_fallback"
    assert result["code"].rstrip().endswith("};")
    assert not [
        issue for issue in generator.validate(result)
        if issue.get("severity") == "high"
    ]


@pytest.mark.asyncio
async def test_valid_component_is_preserved():
    generator = InteractiveDemoGenerator()
    source = (
        "const InteractiveDemo = () => { "
        "const [step, setStep] = React.useState(0); "
        "return <button onClick={() => setStep(step + 1)}>下一步 {step}</button>; };"
    )
    with patch(
        "agents.llm_client.call_llm_structured",
        new=AsyncMock(return_value={"code": source}),
    ):
        result = await generator.generate(
            teaching_plan={},
            knowledge_graph={},
            user_input="红黑树",
            constraints={},
            project_id="test-project",
        )

    assert result["generation_mode"] == "llm"
    assert result["code"] == source
