"""Shared state and type contracts for the Fiducia agent graph."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


Decision = Literal["APPROVE", "APPROVE_WITH_CONDITIONS", "ESCALATE", "REJECT", "PENDING", "SELF_CORRECT"]


class WorkflowState(TypedDict, total=False):
    trace_id: str
    fund: dict[str, Any]
    original_fund: Any
    plan_profile: dict[str, Any]
    policy: dict[str, Any]
    policy_version: str
    policy_hash: str
    ingress_errors: list[str]
    status: str
    active_agent: str
    completed_agents: list[str]
    retries: int
    max_retries: int
    missing_fields: list[str]
    enrichment_history: list[dict[str, Any]]
    agent_results: dict[str, dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    events: list[dict[str, Any]]
    hard_stops: list[str]
    warnings: list[str]
    conflicts: list[str]
    risk_score: int
    confidence: float
    recommendation: Decision
    needs_human: bool
    human_reasons: list[str]
    human_decision: dict[str, Any] | None
    final_summary: str
    audit_path: str
    model_mode: str
    spans: list[dict[str, Any]]           # serialized Span dicts
    handoffs: list[dict[str, Any]]        # handoff envelopes
    run_metrics: dict[str, Any]           # from Tracer.metrics()
    tracer: Any                           # Tracer instance (not serialized to audit)
    fiduciary_guardrail_receipt: dict[str, Any]  # TFGS receipt written by Fiduciary Governor
    tfgs_score: int                       # TIAA Fiduciary Guardrail Score (0-100)
    self_correct_target: str              # "analyst" | "compliance" when SELF_CORRECT


AGENT_ORDER = [
    "analyst",
    "compliance",
    "governance",
    "finance",
    "decision_owner",
]


AGENT_LABELS = {
    "analyst": "Analyst / Reviewer",
    "compliance": "Compliance & Regulatory",
    "governance": "Governance & Suitability",
    "finance": "Finance & Cost Analysis",
    "decision_owner": "Fiduciary Governor",
}
