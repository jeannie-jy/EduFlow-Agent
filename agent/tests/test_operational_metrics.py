"""Cross-process metric aggregation and exposition tests."""

from services.operational_metrics import _p95, prometheus_text


def test_operational_percentile_is_deterministic():
    assert _p95([]) == 0
    assert _p95([1, 2, 3, 100]) == 100


def test_prometheus_text_exposes_low_cardinality_operational_metrics():
    snapshot = {
        "workflows": {
            "status": {"succeeded": 3},
            "success_rate": 0.75,
            "duration_ms_p95": 1200,
        },
        "queue": {"depth": 2, "oldest_wait_seconds": 4.5},
        "nodes": {"coder": {"runs": 4, "errors": 1}},
        "tools": {"knowledge_search": {"calls": 5, "errors": 0, "duration_ms_p95": 42}},
        "export_jobs": {
            "status": {"completed": 3, "failed": 1},
            "success_rate": 0.75,
            "duration_ms_p95": 9000,
        },
        "sse": {"status": {"active": 1}},
    }

    rendered = prometheus_text(snapshot)

    assert 'eduflow_workflows_total{status="succeeded"} 3' in rendered
    assert 'eduflow_node_errors_total{node="coder"} 1' in rendered
    assert 'eduflow_tool_calls_total{tool="knowledge_search"} 5' in rendered
    assert 'eduflow_tool_duration_p95_ms{tool="knowledge_search"} 42' in rendered
    assert "eduflow_export_success_ratio 0.75" in rendered
    assert "eduflow_export_duration_p95_ms 9000" in rendered
    assert "eduflow_queue_depth 2" in rendered
    assert "project_id" not in rendered
