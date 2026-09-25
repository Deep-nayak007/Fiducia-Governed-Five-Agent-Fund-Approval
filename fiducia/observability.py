"""AWS observability integration for Fiducia.

Exports OTel spans to CloudWatch (via aws-opentelemetry-distro OTLP endpoint when
OTEL_EXPORTER_OTLP_ENDPOINT is set) and publishes custom CloudWatch metrics in the
"Fiducia" namespace (us-east-1). All code is wrapped in try/except; completely
no-op when AWS is not configured.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OTel setup — lazy-initialised once per process
# ---------------------------------------------------------------------------

_otel_tracer: Any = None
_otel_init_attempted = False


def _get_otel_tracer() -> Any:
    global _otel_tracer, _otel_init_attempted
    if _otel_init_attempted:
        return _otel_tracer
    _otel_init_attempted = True

    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") and not os.environ.get("AWS_EMF_NAMESPACE"):
        return None  # no-op: not configured

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": "fiducia", "service.version": "1.0"})
        provider = TracerProvider(resource=resource)

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
        if endpoint:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            log.info("OTel OTLP exporter configured: %s", endpoint)

        trace.set_tracer_provider(provider)
        _otel_tracer = trace.get_tracer("fiducia")
        log.info("OTel tracer initialised")
    except Exception as exc:
        log.debug("OTel setup skipped: %s", exc)
        _otel_tracer = None

    return _otel_tracer


# ---------------------------------------------------------------------------
# Emit OTel spans from Fiducia internal spans
# ---------------------------------------------------------------------------

_KIND_MAP = {
    "agent": "SERVER",
    "tool": "CLIENT",
    "llm": "CLIENT",
    "handoff": "PRODUCER",
    "retry": "INTERNAL",
    "hitl": "INTERNAL",
}


def export_spans(spans: list[dict[str, Any]]) -> None:
    """Convert Fiducia internal spans to OTel spans and export them."""
    tracer = _get_otel_tracer()
    if tracer is None:
        return

    try:
        from opentelemetry import trace as _trace
        from opentelemetry.trace import SpanKind

        kind_lookup = {
            "SERVER": SpanKind.SERVER,
            "CLIENT": SpanKind.CLIENT,
            "PRODUCER": SpanKind.PRODUCER,
            "INTERNAL": SpanKind.INTERNAL,
        }

        # Build span_id → OTel context map for parent linking
        _span_ctx_map: dict[str, Any] = {}

        for s in spans:
            span_id = s.get("span_id", "")
            parent_id = s.get("parent_span_id")
            kind_str = _KIND_MAP.get(s.get("kind", ""), "INTERNAL")
            otel_kind = kind_lookup.get(kind_str, SpanKind.INTERNAL)

            start_ns = int(s.get("start_ts", time.time()) * 1e9)
            end_ns = int(s.get("end_ts", time.time()) * 1e9) if s.get("end_ts") else start_ns + 1

            context = None
            if parent_id and parent_id in _span_ctx_map:
                parent_ctx = _span_ctx_map[parent_id]
                context = _trace.set_span_in_context(parent_ctx)

            with tracer.start_as_current_span(
                s.get("name", "unknown"),
                kind=otel_kind,
                context=context,
                start_time=start_ns,
            ) as otel_span:
                attrs = s.get("attributes", {})
                for k, v in attrs.items():
                    if isinstance(v, (str, int, float, bool)):
                        otel_span.set_attribute(f"fiducia.{k}", v)
                otel_span.set_attribute("fiducia.kind", s.get("kind", ""))
                otel_span.set_attribute("fiducia.trace_id", s.get("trace_id", ""))
                if s.get("status") == "error":
                    from opentelemetry.trace import StatusCode
                    otel_span.set_status(StatusCode.ERROR)
                _span_ctx_map[span_id] = _trace.get_current_span()
    except Exception as exc:
        log.debug("OTel span export failed: %s", exc)


# ---------------------------------------------------------------------------
# CloudWatch custom metrics
# ---------------------------------------------------------------------------

_CW_NAMESPACE = "Fiducia"
_CW_REGION = "us-east-1"
_cw_client: Any = None


def _get_cw_client() -> Any:
    global _cw_client
    if _cw_client is not None:
        return _cw_client
    if not os.environ.get("AWS_DEFAULT_REGION") and not os.environ.get("AWS_REGION"):
        os.environ.setdefault("AWS_DEFAULT_REGION", _CW_REGION)
    try:
        import boto3
        _cw_client = boto3.client("cloudwatch", region_name=_CW_REGION)
        return _cw_client
    except Exception as exc:
        log.debug("CloudWatch client unavailable: %s", exc)
        return None


def publish_metrics(state: dict[str, Any]) -> None:
    """Publish run-level CloudWatch metrics in namespace 'Fiducia'.

    Metrics published (dimension: Agent=ALL):
      AgentInvocations, ToolCalls, BedrockCalls, InputTokens, OutputTokens,
      Retries, HumanGates

    Per-agent metrics use dimension Agent=<agent_name>.
    No-op when CloudWatch is unreachable.
    """
    # Skip if explicitly disabled or no AWS credentials
    if os.environ.get("FIDUCIA_DISABLE_CW_METRICS", "").lower() in {"1", "true", "yes"}:
        return

    cw = _get_cw_client()
    if cw is None:
        return

    try:
        metrics_data = state.get("run_metrics", {})
        per_agent = metrics_data.get("per_agent", {})

        metric_data = [
            _metric("AgentInvocations", metrics_data.get("total_agents_invoked",
                    len(state.get("completed_agents", []))), "ALL"),
            _metric("ToolCalls", metrics_data.get("total_tool_calls",
                    len(state.get("tool_calls", []))), "ALL"),
            _metric("BedrockCalls", metrics_data.get("total_bedrock_calls", 0), "ALL"),
            _metric("InputTokens", metrics_data.get("total_input_tokens", 0), "ALL"),
            _metric("OutputTokens", metrics_data.get("total_output_tokens", 0), "ALL"),
            _metric("Retries", state.get("retries", 0), "ALL"),
            _metric("HumanGates", 1 if state.get("needs_human") else 0, "ALL"),
        ]

        for agent_name, agent_data in per_agent.items():
            metric_data += [
                _metric("ToolCalls", agent_data.get("tool_calls", 0), agent_name),
                _metric("BedrockCalls", agent_data.get("llm_calls", 0), agent_name),
                _metric("InputTokens", agent_data.get("input_tokens", 0), agent_name),
                _metric("OutputTokens", agent_data.get("output_tokens", 0), agent_name),
            ]

        # CloudWatch put_metric_data accepts at most 20 metrics per call
        for i in range(0, len(metric_data), 20):
            cw.put_metric_data(Namespace=_CW_NAMESPACE, MetricData=metric_data[i:i + 20])

        log.info("Published %d CloudWatch metrics (namespace=%s)", len(metric_data), _CW_NAMESPACE)
    except Exception as exc:
        log.debug("CloudWatch metrics publish failed: %s", exc)


def _metric(name: str, value: float, agent_dim: str) -> dict:
    return {
        "MetricName": name,
        "Value": float(value),
        "Unit": "Count",
        "Dimensions": [{"Name": "Agent", "Value": agent_dim}],
    }


# ---------------------------------------------------------------------------
# Combined post-run hook: call this after run_workflow() returns
# ---------------------------------------------------------------------------

def post_run_telemetry(state: dict[str, Any]) -> None:
    """Export OTel spans and publish CloudWatch metrics for a completed workflow run."""
    try:
        export_spans(state.get("spans", []))
    except Exception as exc:
        log.debug("post_run export_spans: %s", exc)
    try:
        publish_metrics(state)
    except Exception as exc:
        log.debug("post_run publish_metrics: %s", exc)
