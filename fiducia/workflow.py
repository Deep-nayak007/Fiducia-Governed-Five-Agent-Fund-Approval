"""LangGraph orchestration, conditional routing, retries, and HITL boundaries."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from .agents import AGENTS
from .audit import AuditLogger
from .models import WorkflowState
from .policy import load_policy
from .telemetry import Tracer
from .tools import lookup_fund_reference, normalize_record, tool_trace
from .validation import validate_fund_values, validate_plan_values


ROOT = Path(__file__).resolve().parents[1]


def _json_safe_snapshot(value: Any) -> Any:
    """Return an audit-safe copy while preserving ordinary JSON values."""

    return json.loads(json.dumps(value, default=str))


def create_initial_state(
    fund: Any,
    *,
    plan_profile: dict[str, Any] | None = None,
    model_mode: str = "offline",
    audit_path: str | None = None,
    trace_id: str | None = None,
) -> WorkflowState:
    policy = load_policy()
    policy_hash = hashlib.sha256(
        json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    resolved_trace = trace_id or str(uuid.uuid4())
    resolved_audit = audit_path or str(ROOT / "audit" / f"trace-{resolved_trace}.jsonl")
    default_plan = {"plan_id": "ASU-DEMO-401A", "max_risk_score": 7}
    if plan_profile is None:
        resolved_plan: dict[str, Any] = default_plan
    elif isinstance(plan_profile, dict):
        # An explicit empty object is malformed, not an implicit request for defaults.
        resolved_plan = deepcopy(plan_profile)
    else:
        resolved_plan = {}
    ingress_errors = validate_fund_values(fund)
    ingress_errors.extend(
        validate_plan_values(
            resolved_plan,
            allowed_asset_classes=set(policy["suitability"]["allowed_asset_classes"]),
        )
    )
    ingress_errors = list(dict.fromkeys(ingress_errors))
    resolved_fund = normalize_record(fund) if isinstance(fund, dict) else {}
    state: WorkflowState = {
        "trace_id": resolved_trace,
        "fund": resolved_fund,
        "original_fund": deepcopy(fund),
        "plan_profile": resolved_plan,
        "policy": policy,
        "policy_version": policy["metadata"]["version"],
        "policy_hash": policy_hash,
        "ingress_errors": ingress_errors,
        "status": "QUEUED",
        "active_agent": "",
        "completed_agents": [],
        "retries": 0,
        "max_retries": int(policy["data_quality"]["max_enrichment_retries"]),
        "missing_fields": [],
        "enrichment_history": [],
        "agent_results": {},
        "tool_calls": [],
        "events": [],
        "hard_stops": list(ingress_errors),
        "warnings": [],
        "conflicts": [],
        "risk_score": 0,
        "confidence": 0.0,
        "recommendation": "PENDING",
        "needs_human": False,
        "human_reasons": [],
        "human_decision": None,
        "final_summary": "",
        "audit_path": resolved_audit,
        "model_mode": model_mode,
        "spans": [],
        "handoffs": [],
        "run_metrics": {},
        "tracer": Tracer(resolved_trace),
        "fiduciary_guardrail_receipt": {},
        "tfgs_score": 0,
        "self_correct_target": None,
    }
    AuditLogger(resolved_audit).append(
        trace_id=resolved_trace,
        event_type="WORKFLOW_CREATED",
        actor="orchestrator",
        payload={
            "ticker": state["fund"].get("ticker"),
            "raw_fund_snapshot": _json_safe_snapshot(fund),
            "normalized_fund_snapshot": state["fund"],
            "raw_plan_profile": _json_safe_snapshot(plan_profile),
            "plan_profile": state["plan_profile"],
            "ingress_errors": ingress_errors,
            "policy_version": state["policy_version"],
            "policy_hash": state["policy_hash"],
            "model_mode": model_mode,
        },
    )
    return state


def _agent_node(name: str):
    def invoke(state: WorkflowState) -> WorkflowState:
        outer_tracer: Tracer | None = state.get("tracer")  # type: ignore[assignment]
        # Snapshot current span IDs so we can detect spans added inside the agent
        # (BaseAgent._start deepcopies state, giving the inner loop its own Tracer clone)
        outer_span_ids_before = {s.span_id for s in outer_tracer.spans} if outer_tracer else set()
        agent_span = outer_tracer.start_span("agent", name) if outer_tracer else None
        run_status = "ok"
        result_state = state
        try:
            result_state = AGENTS[name].run(state)
        except Exception:
            run_status = "error"
            raise
        finally:
            if outer_tracer and agent_span:
                agent_result = result_state.get("agent_results", {}).get(name, {})
                agent_span.attributes["outcome"] = agent_result.get("outcome")
                agent_span.attributes["confidence"] = agent_result.get("confidence")
                outer_tracer.end_span(agent_span, run_status)
                # Merge tool/llm spans that accumulated in the deepcopied inner tracer
                inner_tracer: Tracer | None = result_state.get("tracer")  # type: ignore[assignment]
                if inner_tracer and inner_tracer is not outer_tracer:
                    seen = {s.span_id for s in outer_tracer.spans}
                    for s in inner_tracer.spans:
                        if s.span_id not in seen and s.span_id not in outer_span_ids_before:
                            s.parent_span_id = agent_span.span_id
                            outer_tracer.spans.append(s)
                    for h in inner_tracer.handoffs:
                        key = (h.get("from"), h.get("to"), h.get("ts"))
                        if not any(
                            (x.get("from"), x.get("to"), x.get("ts")) == key
                            for x in outer_tracer.handoffs
                        ):
                            outer_tracer.handoffs.append(h)
                result_state["tracer"] = outer_tracer
                result_state["spans"] = [s.to_dict() for s in outer_tracer.spans]
                result_state["run_metrics"] = outer_tracer.metrics()
        return result_state

    invoke.__name__ = f"{name}_node"
    return invoke


def data_repair_node(incoming: WorkflowState) -> WorkflowState:
    # Grab the outer tracer BEFORE deepcopy so spans survive the clone
    outer_tracer: Tracer | None = incoming.get("tracer")  # type: ignore[assignment]
    state: WorkflowState = deepcopy(incoming)
    retry_num = int(state.get("retries", 0)) + 1
    missing_preview = ", ".join(state.get("missing_fields", [])[:3])
    span = outer_tracer.start_span(
        "retry", "data_repair",
        agent="orchestrator",
        retry_num=retry_num,
        reason=f"{missing_preview} missing, retry {retry_num}/{state.get('max_retries', 2)}",
    ) if outer_tracer else None
    missing = list(state.get("missing_fields", []))
    reference = lookup_fund_reference(str(state["fund"].get("ticker", "")))
    repaired: dict[str, Any] = {}
    identity_mismatches: list[str] = []
    source_hash = None
    if reference:
        for identity_field in ("fund_name", "fund_type", "asset_class"):
            submitted = str(state["fund"].get(identity_field, "")).strip().casefold()
            catalog = str(reference.get(identity_field, "")).strip().casefold()
            if not submitted or submitted != catalog:
                identity_mismatches.append(identity_field)
        source_hash = hashlib.sha256(
            json.dumps(
                reference, sort_keys=True, separators=(",", ":"), default=str
            ).encode("utf-8")
        ).hexdigest()
        if not identity_mismatches:
            for field in missing:
                value = reference.get(field)
                if value not in (None, ""):
                    state["fund"][field] = value
                    repaired[field] = value
        else:
            conflict = (
                "Reference-catalog identity mismatch on "
                + ", ".join(identity_mismatches)
                + "; no fields were enriched"
            )
            if conflict not in state.setdefault("conflicts", []):
                state["conflicts"].append(conflict)
    state["retries"] = int(state.get("retries", 0)) + 1
    attempt = {"attempt": state["retries"], "requested_fields": missing, "repaired_fields": sorted(repaired), "source": "synthetic_reference_catalog", "source_sha256": source_hash, "identity_fields_checked": ["ticker", "fund_name", "fund_type", "asset_class"], "identity_mismatches": identity_mismatches, "field_provenance": {field: {"source": "synthetic_reference_catalog", "ticker": reference.get("ticker") if reference else None, "as_of_date": reference.get("as_of_date") if reference else None, "source_sha256": source_hash} for field in repaired}}
    state.setdefault("enrichment_history", []).append(attempt)
    state.setdefault("tool_calls", []).append(tool_trace("orchestrator", "reference_catalog_lookup", {"ticker": state["fund"].get("ticker"), "fields": missing}, f"repaired={sorted(repaired)}", "SUCCESS" if repaired else "NO_MATCH"))
    state.setdefault("events", []).append({"agent": "orchestrator", "kind": "SELF_CORRECTION", "message": f"Enrichment retry {state['retries']}/{state['max_retries']}", "details": attempt})
    AuditLogger(state["audit_path"]).append(trace_id=state["trace_id"], event_type="SELF_CORRECTION", actor="orchestrator", payload=attempt)
    if outer_tracer and span:
        outer_tracer.end_span(span, "ok")
        outer_tracer.record_handoff(
            "data_repair", "analyst", "RETRY_ANALYST",
            f"retry {state['retries']}/{state['max_retries']} after repair of {sorted(repaired) or 'nothing'}",
            {"repaired": sorted(repaired), "missing_remaining": state.get("missing_fields", [])},
            f"data_repair complete, retry {state['retries']}/{state['max_retries']}",
        )
        state["tracer"] = outer_tracer
        state["spans"] = [s.to_dict() for s in outer_tracer.spans]
        state["handoffs"] = list(outer_tracer.handoffs)
        state["run_metrics"] = outer_tracer.metrics()
    return state


def human_review_node(incoming: WorkflowState) -> WorkflowState:
    outer_tracer: Tracer | None = incoming.get("tracer")  # type: ignore[assignment]
    state: WorkflowState = deepcopy(incoming)
    span = outer_tracer.start_span(
        "hitl", "human_checkpoint",
        recommendation=state.get("recommendation"),
        risk_score=state.get("risk_score"),
        reasons=state.get("human_reasons", []),
    ) if outer_tracer else None
    state["active_agent"] = "human_review"
    state["status"] = "AWAITING_HUMAN_REVIEW"
    state.setdefault("events", []).append({"agent": "human_review", "kind": "WORKFLOW_PAUSED", "message": "Workflow paused at governed human checkpoint", "details": {"reasons": state.get("human_reasons", [])}})
    AuditLogger(state["audit_path"]).append(trace_id=state["trace_id"], event_type="HITL_REQUIRED", actor="orchestrator", payload={"recommendation": state.get("recommendation"), "risk_score": state.get("risk_score"), "reasons": state.get("human_reasons", [])})
    if outer_tracer and span:
        outer_tracer.end_span(span, "ok")
        state["tracer"] = outer_tracer
        state["spans"] = [s.to_dict() for s in outer_tracer.spans]
        state["handoffs"] = list(outer_tracer.handoffs)
        state["run_metrics"] = outer_tracer.metrics()
    return state


def route_after_analyst(state: WorkflowState) -> str:
    if state.get("agent_results", {}).get("analyst", {}).get("outcome") == "FAIL":
        return "decision_owner"
    if state.get("missing_fields"):
        return "data_repair" if int(state.get("retries", 0)) < int(state.get("max_retries", 2)) else "decision_owner"
    return "compliance"


def route_after_governor(state: WorkflowState) -> str:
    if state.get("recommendation") == "SELF_CORRECT":
        return "self_correct"
    return "human_review" if state.get("needs_human") else "end"


def route_after_governor_self_correct(state: WorkflowState) -> str:
    return state.get("self_correct_target") or "analyst"


def governor_self_correct_node(incoming: WorkflowState) -> WorkflowState:
    """Transition node: resets downstream agents so the governor's SELF_CORRECT loop reruns."""
    outer_tracer: Tracer | None = incoming.get("tracer")  # type: ignore[assignment]
    state: WorkflowState = deepcopy(incoming)
    target = state.get("self_correct_target") or "analyst"
    retry_num = int(state.get("retries", 0)) + 1
    receipt = state.get("fiduciary_guardrail_receipt", {})

    span = outer_tracer.start_span(
        "retry", "governor_self_correct",
        agent="orchestrator",
        retry_num=retry_num,
        self_correct_target=target,
        tfgs_score=receipt.get("tfgs_score"),
        reason=f"TFGS {receipt.get('tfgs_score')}, retry {retry_num}/{state.get('max_retries', 2)}",
    ) if outer_tracer else None

    agents_to_reset = (
        ["analyst", "compliance", "governance", "finance", "decision_owner"]
        if target == "analyst"
        else ["compliance", "governance", "finance", "decision_owner"]
    )
    completed = [a for a in state.get("completed_agents", []) if a not in agents_to_reset]
    state["completed_agents"] = completed
    agent_results = {k: v for k, v in state.get("agent_results", {}).items() if k not in agents_to_reset}
    state["agent_results"] = agent_results

    if target == "analyst":
        state["hard_stops"] = list(state.get("ingress_errors", []))
        state["warnings"] = []
        state["conflicts"] = []
        state["missing_fields"] = []

    state["retries"] = retry_num
    state["recommendation"] = "PENDING"
    state["status"] = "RUNNING"

    state.setdefault("events", []).append({
        "agent": "orchestrator", "kind": "GOVERNOR_SELF_CORRECT",
        "message": f"Fiduciary Governor triggered self-correction (target: {target}, retry {retry_num}/{state.get('max_retries', 2)})",
        "details": {"target": target, "tfgs_score": receipt.get("tfgs_score"), "retry": retry_num},
    })
    AuditLogger(state["audit_path"]).append(
        trace_id=state["trace_id"], event_type="GOVERNOR_SELF_CORRECT", actor="orchestrator",
        payload={"target": target, "retry": retry_num, "tfgs_score": receipt.get("tfgs_score"), "reason": receipt.get("itemized_deductions")},
    )

    if outer_tracer:
        if span:
            outer_tracer.end_span(span, "ok")
        outer_tracer.record_handoff(
            "decision_owner", target, "GOVERNOR_SELF_CORRECT",
            f"TFGS {receipt.get('tfgs_score')}, retry {retry_num}/{state.get('max_retries', 2)}",
            {"deductions": receipt.get("itemized_deductions", [])},
            f"governor → {target}: SELF_CORRECT retry {retry_num}/{state.get('max_retries', 2)}",
        )
        state["tracer"] = outer_tracer
        state["spans"] = [s.to_dict() for s in outer_tracer.spans]
        state["handoffs"] = list(outer_tracer.handoffs)
        state["run_metrics"] = outer_tracer.metrics()

    return state


def build_graph():
    """Build the challenge graph. Import is lazy so offline tests have a graceful fallback."""
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(WorkflowState)
    for name in ("analyst", "compliance", "governance", "finance", "decision_owner"):
        builder.add_node(name, _agent_node(name))
    builder.add_node("data_repair", data_repair_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("governor_self_correct", governor_self_correct_node)
    builder.add_edge(START, "analyst")
    builder.add_conditional_edges(
        "analyst", route_after_analyst,
        {"data_repair": "data_repair", "compliance": "compliance", "decision_owner": "decision_owner"},
    )
    builder.add_edge("data_repair", "analyst")
    builder.add_edge("compliance", "governance")
    builder.add_edge("governance", "finance")
    builder.add_edge("finance", "decision_owner")
    builder.add_conditional_edges(
        "decision_owner", route_after_governor,
        {"self_correct": "governor_self_correct", "human_review": "human_review", "end": END},
    )
    builder.add_conditional_edges(
        "governor_self_correct", route_after_governor_self_correct,
        {"analyst": "analyst", "compliance": "compliance"},
    )
    builder.add_edge("human_review", END)
    return builder.compile()


def _fallback_run(state: WorkflowState) -> WorkflowState:
    state = AGENTS["analyst"].run(state)
    while (
        state.get("missing_fields")
        and state.get("agent_results", {}).get("analyst", {}).get("outcome") != "FAIL"
        and state["retries"] < state["max_retries"]
    ):
        state = data_repair_node(state)
        state = AGENTS["analyst"].run(state)
    analyst_failed = (
        state.get("agent_results", {}).get("analyst", {}).get("outcome") == "FAIL"
    )
    if state.get("missing_fields") or analyst_failed:
        state = AGENTS["decision_owner"].run(state)
    else:
        for name in ("compliance", "governance", "finance", "decision_owner"):
            state = AGENTS[name].run(state)

    # Handle governor SELF_CORRECT loops (bounded by max_retries)
    _sc_loops = 0
    while state.get("recommendation") == "SELF_CORRECT" and _sc_loops < int(state.get("max_retries", 2)):
        _sc_loops += 1
        state = governor_self_correct_node(state)
        target = state.get("self_correct_target", "analyst")
        if target == "analyst":
            state = AGENTS["analyst"].run(state)
            while (
                state.get("missing_fields")
                and state.get("agent_results", {}).get("analyst", {}).get("outcome") != "FAIL"
                and state["retries"] < state["max_retries"]
            ):
                state = data_repair_node(state)
                state = AGENTS["analyst"].run(state)
        for name in ("compliance", "governance", "finance", "decision_owner"):
            state = AGENTS[name].run(state)

    if state.get("needs_human"):
        state = human_review_node(state)
    return state


def run_workflow(
    fund: dict[str, Any],
    *,
    plan_profile: dict[str, Any] | None = None,
    model_mode: str = "offline",
    audit_path: str | None = None,
    trace_id: str | None = None,
) -> WorkflowState:
    state = create_initial_state(fund, plan_profile=plan_profile, model_mode=model_mode, audit_path=audit_path, trace_id=trace_id)
    try:
        final: WorkflowState = build_graph().invoke(state)
    except ImportError:
        final = _fallback_run(state)
    tracer: Tracer | None = final.get("tracer")  # type: ignore[assignment]
    if tracer:
        final["run_metrics"] = tracer.metrics()
        final["spans"] = [s.to_dict() for s in tracer.spans]
        final["handoffs"] = list(tracer.handoffs)
    AuditLogger(final["audit_path"]).append(trace_id=final["trace_id"], event_type="WORKFLOW_CHECKPOINT", actor="orchestrator", payload={"status": final["status"], "recommendation": final["recommendation"], "risk_score": final["risk_score"], "confidence": final["confidence"], "needs_human": final["needs_human"], "human_reasons": final["human_reasons"], "final_summary": final["final_summary"]})
    try:
        from fiducia.observability import post_run_telemetry
        post_run_telemetry(final)
    except Exception:
        pass
    return final


def stream_workflow(
    fund: dict[str, Any],
    *,
    plan_profile: dict[str, Any] | None = None,
    model_mode: str = "offline",
    audit_path: str | None = None,
    trace_id: str | None = None,
) -> Iterator[WorkflowState]:
    """Yield governed state checkpoints so the UI can render the live agent graph."""
    state = create_initial_state(
        fund,
        plan_profile=plan_profile,
        model_mode=model_mode,
        audit_path=audit_path,
        trace_id=trace_id,
    )
    yield state
    try:
        for snapshot in build_graph().stream(state, stream_mode="values"):
            state = snapshot
            yield state
    except ImportError:
        state = AGENTS["analyst"].run(state)
        yield state
        while (
            state.get("missing_fields")
            and state.get("agent_results", {}).get("analyst", {}).get("outcome") != "FAIL"
            and state["retries"] < state["max_retries"]
        ):
            state = data_repair_node(state)
            yield state
            state = AGENTS["analyst"].run(state)
            yield state
        analyst_failed = (
            state.get("agent_results", {}).get("analyst", {}).get("outcome")
            == "FAIL"
        )
        if state.get("missing_fields") or analyst_failed:
            state = AGENTS["decision_owner"].run(state)
            yield state
        else:
            for name in ("compliance", "governance", "finance", "decision_owner"):
                state = AGENTS[name].run(state)
                yield state
        if state.get("needs_human"):
            state = human_review_node(state)
            yield state
    AuditLogger(state["audit_path"]).append(
        trace_id=state["trace_id"],
        event_type="WORKFLOW_CHECKPOINT",
        actor="orchestrator",
        payload={
            "status": state["status"],
            "recommendation": state["recommendation"],
            "risk_score": state["risk_score"],
            "needs_human": state["needs_human"],
        },
    )


def apply_human_decision(
    state: WorkflowState,
    *,
    reviewer: str,
    action: str,
    reason: str,
    second_approver: str | None = None,
    attested: bool = False,
) -> WorkflowState:
    action = action.upper()
    if action not in {"APPROVE", "REJECT", "RETURN_FOR_REVIEW"}:
        raise ValueError("action must be APPROVE, REJECT, or RETURN_FOR_REVIEW")
    if state.get("status") != "AWAITING_HUMAN_REVIEW" or not state.get("needs_human"):
        raise ValueError("The case is not at an authorized human-review checkpoint")
    if state.get("human_decision") is not None:
        raise ValueError("A human decision has already been recorded for this case")
    hitl_policy = state["policy"]["human_in_the_loop"]
    if not reviewer.strip():
        raise ValueError("reviewer is required")
    if hitl_policy["override_requires_reason"] and not reason.strip():
        raise ValueError("reviewer reason is required")
    if not attested:
        raise ValueError("reviewer attestation is required")
    recommended = state.get("recommendation")
    if (
        recommended == "REJECT"
        and action == "APPROVE"
        and hitl_policy["reject_to_approve_requires_two_person_control"]
        and not (second_approver or "").strip()
    ):
        raise ValueError("A second approver is required to override REJECT to APPROVE")
    if (
        second_approver
        and reviewer.strip().casefold() == second_approver.strip().casefold()
    ):
        raise ValueError("The second approver must be a distinct identity")
    updated: WorkflowState = deepcopy(state)
    decision = {"reviewer": reviewer.strip(), "action": action, "reason": reason.strip(), "second_approver": (second_approver or "").strip() or None, "attested": True, "agent_recommendation": recommended}
    updated["human_decision"] = decision
    updated["status"] = "COMPLETED" if action in {"APPROVE", "REJECT"} else "RETURNED_FOR_REVIEW"
    updated["events"].append({"agent": "human_reviewer", "kind": "HUMAN_DECISION", "message": f"Human reviewer selected {action}", "details": decision})
    AuditLogger(updated["audit_path"]).append(trace_id=updated["trace_id"], event_type="HUMAN_DECISION", actor=f"human:{reviewer.strip()}", payload=decision)
    return updated
