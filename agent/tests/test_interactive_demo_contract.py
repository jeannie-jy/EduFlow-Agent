from generators.interactive_demo_generator import INTERACTIVE_DEMO_SYSTEM_PROMPT


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
