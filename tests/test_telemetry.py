"""Tests for span-based orchestration telemetry."""
from fiducia.telemetry import Tracer, Span


def test_span_lifecycle():
    tracer = Tracer("test-trace-001")
    span = tracer.start_span("agent", "analyst", outcome="PASS")
    assert span.status == "running"
    tracer.end_span(span, "ok")
    assert span.status == "ok"
    assert span.duration_ms is not None
    assert len(tracer.spans) == 1


def test_handoff_records_envelope():
    tracer = Tracer("test-trace-002")
    envelope = tracer.record_handoff(
        "analyst", "data_repair", "REPAIR_REQUEST",
        "sharpe_ratio missing", {"missing": ["sharpe_ratio"]},
        "sharpe_ratio missing after analyst, retry 1/2"
    )
    assert envelope["from"] == "analyst"
    assert envelope["to"] == "data_repair"
    assert "payload_sha256" in envelope
    assert len(tracer.handoffs) == 1


def test_metrics_structure():
    tracer = Tracer("test-trace-003")
    span = tracer.start_span("agent", "analyst")
    tracer.end_span(span)
    metrics = tracer.metrics()
    assert "total_agents_invoked" in metrics
    assert "per_agent" in metrics
    assert metrics["total_agents_invoked"] == 1


def test_span_parent_tracking():
    tracer = Tracer("test-trace-004")
    agent_span = tracer.start_span("agent", "analyst")
    tool_span = tracer.start_span("tool", "schema_validator", agent="analyst")
    assert tool_span.parent_span_id == agent_span.span_id
    tracer.end_span(tool_span)
    tracer.end_span(agent_span)


def test_metrics_tool_and_llm_counts():
    tracer = Tracer("test-trace-005")
    a = tracer.start_span("agent", "compliance")
    t = tracer.start_span("tool", "deterministic_policy_engine", agent="compliance")
    tracer.end_span(t)
    l = tracer.start_span("llm", "compliance", agent="compliance",
                           input_tokens=100, output_tokens=50)
    tracer.end_span(l)
    tracer.end_span(a)
    metrics = tracer.metrics()
    assert metrics["total_tool_calls"] == 1
    assert metrics["total_bedrock_calls"] == 1
    assert metrics["total_input_tokens"] == 100
    assert metrics["total_output_tokens"] == 50


def test_span_to_dict():
    tracer = Tracer("test-trace-006")
    span = tracer.start_span("agent", "analyst", outcome="PASS")
    tracer.end_span(span)
    d = span.to_dict()
    assert d["kind"] == "agent"
    assert d["name"] == "analyst"
    assert d["status"] == "ok"


def test_retry_and_hitl_spans():
    tracer = Tracer("test-trace-007")
    r = tracer.start_span("retry", "data_repair", retry_num=1)
    tracer.end_span(r)
    h = tracer.start_span("hitl", "human_checkpoint")
    tracer.end_span(h)
    metrics = tracer.metrics()
    assert metrics["total_retries"] == 1
    assert metrics["human_gates_triggered"] == 1
