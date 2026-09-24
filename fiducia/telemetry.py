"""Span-based orchestration tracer."""
from __future__ import annotations
import hashlib, json, time, uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    kind: str  # agent|tool|llm|handoff|retry|hitl
    name: str
    from_agent: str | None = None
    to_agent: str | None = None
    start_ts: float = field(default_factory=time.time)
    end_ts: float | None = None
    duration_ms: float | None = None
    status: str = "running"  # running|ok|error|skipped
    attributes: dict[str, Any] = field(default_factory=dict)

    def finish(self, status: str = "ok") -> "Span":
        self.end_ts = time.time()
        self.duration_ms = round((self.end_ts - self.start_ts) * 1000, 1)
        self.status = status
        return self

    def to_dict(self) -> dict:
        return asdict(self)


class Tracer:
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.spans: list[Span] = []
        self._stack: list[str] = []  # span_id stack for parent tracking
        self.handoffs: list[dict[str, Any]] = []

    def start_span(self, kind: str, name: str, parent_span_id: str | None = None, **attrs: Any) -> Span:
        parent = parent_span_id or (self._stack[-1] if self._stack else None)
        span = Span(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:12],
            parent_span_id=parent,
            kind=kind,
            name=name,
            attributes=attrs,
        )
        self.spans.append(span)
        self._stack.append(span.span_id)
        return span

    def end_span(self, span: Span, status: str = "ok") -> Span:
        span.finish(status)
        if span.span_id in self._stack:
            self._stack.remove(span.span_id)
        return span

    def record_handoff(self, from_agent: str, to_agent: str, message_type: str,
                       payload_summary: str, payload: Any, reason: str) -> dict[str, Any]:
        sha = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        envelope = {
            "from": from_agent, "to": to_agent,
            "message_type": message_type,
            "payload_summary": payload_summary,
            "payload_sha256": sha,
            "reason": reason,
            "ts": time.time(),
        }
        self.handoffs.append(envelope)
        # also record as a span
        span = Span(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:12],
            parent_span_id=self._stack[-1] if self._stack else None,
            kind="handoff",
            name=f"{from_agent}\u2192{to_agent}",
            from_agent=from_agent,
            to_agent=to_agent,
            start_ts=time.time(),
            attributes=envelope,
        )
        span.finish("ok")
        self.spans.append(span)
        return envelope

    def metrics(self) -> dict[str, Any]:
        """Compute run metrics from spans."""
        per_agent: dict[str, dict] = {}
        for s in self.spans:
            if s.kind == "agent":
                per_agent.setdefault(s.name, {"invocations": 0, "tool_calls": 0, "llm_calls": 0,
                                               "input_tokens": 0, "output_tokens": 0,
                                               "latency_ms": 0.0, "outcome": None, "confidence": None})
                per_agent[s.name]["invocations"] += 1
                per_agent[s.name]["latency_ms"] += s.duration_ms or 0
                per_agent[s.name]["outcome"] = s.attributes.get("outcome")
                per_agent[s.name]["confidence"] = s.attributes.get("confidence")

        for s in self.spans:
            if s.kind == "tool" and s.attributes.get("agent"):
                agent = s.attributes["agent"]
                per_agent.setdefault(agent, {"invocations": 0, "tool_calls": 0, "llm_calls": 0,
                                              "input_tokens": 0, "output_tokens": 0,
                                              "latency_ms": 0.0, "outcome": None, "confidence": None})
                per_agent[agent]["tool_calls"] += 1
            if s.kind == "llm" and s.attributes.get("agent"):
                agent = s.attributes["agent"]
                per_agent.setdefault(agent, {"invocations": 0, "tool_calls": 0, "llm_calls": 0,
                                              "input_tokens": 0, "output_tokens": 0,
                                              "latency_ms": 0.0, "outcome": None, "confidence": None})
                per_agent[agent]["llm_calls"] += 1
                per_agent[agent]["input_tokens"] += s.attributes.get("input_tokens", 0)
                per_agent[agent]["output_tokens"] += s.attributes.get("output_tokens", 0)

        llm_spans = [s for s in self.spans if s.kind == "llm"]
        tool_spans = [s for s in self.spans if s.kind == "tool"]
        retry_spans = [s for s in self.spans if s.kind == "retry"]
        hitl_spans = [s for s in self.spans if s.kind == "hitl"]

        edges: dict[str, int] = {}
        for h in self.handoffs:
            key = f"{h['from']}\u2192{h['to']}"
            edges[key] = edges.get(key, 0) + 1

        return {
            "total_agents_invoked": sum(p["invocations"] for p in per_agent.values()),
            "total_tool_calls": len(tool_spans),
            "total_bedrock_calls": len(llm_spans),
            "total_input_tokens": sum(s.attributes.get("input_tokens", 0) for s in llm_spans),
            "total_output_tokens": sum(s.attributes.get("output_tokens", 0) for s in llm_spans),
            "total_latency_ms": sum(s.duration_ms or 0 for s in self.spans if s.kind == "agent"),
            "total_retries": len(retry_spans),
            "human_gates_triggered": len(hitl_spans),
            "edges_traversed": edges,
            "per_agent": per_agent,
        }
