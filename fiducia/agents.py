"""Implementations of Fiducia's five bounded specialist agents."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

from .audit import AuditLogger
from .llm import BedrockNarrativeEngine
from .models import AGENT_LABELS, WorkflowState
from .policy import (
    data_age_days,
    expense_benchmark,
    expense_cap,
    fee_drag_projection,
    missing_required_fields,
    numeric,
    parse_bool,
)
from .prompts import AGENT_PROMPTS, TOOL_SETS
from .tools import OFFICIAL_REFERENCES, analyze_breakpoints, tool_trace


def _event(agent: str, kind: str, message: str, **details: Any) -> dict[str, Any]:
    return {"agent": agent, "kind": kind, "message": message, "details": details}


class BaseAgent:
    key = "base"

    def run(self, incoming: WorkflowState) -> WorkflowState:
        raise NotImplementedError

    def _start(self, incoming: WorkflowState) -> WorkflowState:
        state: WorkflowState = deepcopy(incoming)
        state["active_agent"] = self.key
        state["status"] = "RUNNING"
        state.setdefault("events", []).append(
            _event(self.key, "AGENT_STARTED", f"{AGENT_LABELS[self.key]} started")
        )
        self._audit(state, "AGENT_STARTED", {"agent": self.key, "policy_version": state["policy_version"]})
        return state

    def _record_tool(
        self,
        state: WorkflowState,
        tool: str,
        inputs: dict[str, Any],
        summary: str,
        status: str = "SUCCESS",
    ) -> None:
        state.setdefault("tool_calls", []).append(tool_trace(self.key, tool, inputs, summary, status))

    def _finish(self, state: WorkflowState, result: dict[str, Any]) -> WorkflowState:
        state.setdefault("agent_results", {})[self.key] = result
        completed = state.setdefault("completed_agents", [])
        if self.key not in completed:
            completed.append(self.key)
        state["events"].append(
            _event(
                self.key,
                "AGENT_COMPLETED",
                f"{AGENT_LABELS[self.key]} completed",
                outcome=result.get("outcome"),
                confidence=result.get("confidence"),
            )
        )
        self._audit(
            state,
            "AGENT_COMPLETED",
            {
                "agent": self.key,
                "outcome": result.get("outcome"),
                "confidence": result.get("confidence"),
                "result": result,
                "tool_calls": [
                    call
                    for call in state.get("tool_calls", [])
                    if call.get("agent") == self.key
                ],
            },
        )
        return state

    def _narrative(
        self,
        state: WorkflowState,
        facts: dict[str, Any],
        fallback: str,
        deterministic_outcome: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        return BedrockNarrativeEngine(state.get("model_mode", "offline")).explain(
            system_prompt=AGENT_PROMPTS[self.key],
            agent_name=AGENT_LABELS[self.key],
            facts=facts,
            fallback=fallback,
            deterministic_outcome=deterministic_outcome,
        )

    def _audit(self, state: WorkflowState, event_type: str, payload: dict[str, Any]) -> None:
        path = state.get("audit_path")
        if path:
            AuditLogger(path).append(
                trace_id=state["trace_id"], event_type=event_type, actor=self.key, payload=payload
            )


class AnalystAgent(BaseAgent):
    key = "analyst"

    def run(self, incoming: WorkflowState) -> WorkflowState:
        state = self._start(incoming)
        fund, policy = state["fund"], state["policy"]
        missing = missing_required_fields(fund, policy)
        self._record_tool(state, "schema_validator", {"required_count": len(policy["data_quality"]["required_fields"])}, f"{len(missing)} missing field(s)")

        range_errors: list[str] = list(state.get("ingress_errors", []))
        numeric_ranges = policy["data_quality"]["numeric_ranges"]
        for field, (lower, upper) in numeric_ranges.items():
            if field in missing or field not in fund or fund.get(field) in (None, ""):
                continue
            if isinstance(fund.get(field), bool):
                range_errors.append(f"{field} must be a number, not a boolean")
                continue
            try:
                observed = float(fund.get(field))
            except (TypeError, ValueError):
                range_errors.append(f"{field} must be a finite number")
                continue
            if not math.isfinite(observed):
                range_errors.append(f"{field} must be a finite number")
            elif not lower <= observed <= upper:
                range_errors.append(
                    f"{field} is outside the accepted range [{lower}, {upper}]"
                )
        self._record_tool(state, "range_validator", {"fields": list(numeric_ranges)}, f"{len(range_errors)} range error(s)", "FAILED" if range_errors else "SUCCESS")

        warnings = list(state.get("warnings", []))
        conflicts = list(state.get("conflicts", []))
        age = None
        if "as_of_date" not in missing:
            try:
                age = data_age_days(str(fund["as_of_date"]))
                if age < -int(policy["data_quality"]["future_date_tolerance_days"]):
                    range_errors.append("as_of_date cannot be in the future")
                elif age > int(policy["data_quality"]["max_data_age_days"]):
                    warnings.append(f"Source data is {age} days old; maximum is {policy['data_quality']['max_data_age_days']} days")
            except ValueError:
                range_errors.append("as_of_date must use YYYY-MM-DD")
        self._record_tool(state, "freshness_calculator", {"as_of_date": fund.get("as_of_date")}, f"age_days={age}")

        if parse_bool(fund.get("source_conflict", False)):
            conflicts.append("Conflicting values were reported by source systems")
        fee_delta_bps = None
        fee_fields = {"fee_12b1", "distribution_12b1_fee", "service_fee"}
        if not fee_fields.intersection(missing):
            try:
                total_fee = Decimal(str(fund["fee_12b1"]))
                component_total = Decimal(
                    str(fund["distribution_12b1_fee"])
                ) + Decimal(str(fund["service_fee"]))
                fee_delta_bps = float(
                    (total_fee - component_total) * Decimal("100")
                )
            except (InvalidOperation, TypeError, ValueError):
                fee_delta_bps = None
            else:
                if math.isfinite(fee_delta_bps) and abs(fee_delta_bps) > numeric(
                    policy["data_quality"]["fee_reconciliation_tolerance_bps"]
                ):
                    conflicts.append(
                        f"12b-1 total and components differ by {fee_delta_bps:+.2f} bps"
                    )
        self._record_tool(
            state,
            "fee_component_reconciler",
            {"fields": sorted(fee_fields), "tolerance_bps": policy["data_quality"]["fee_reconciliation_tolerance_bps"]},
            "not evaluated: missing component"
            if fee_delta_bps is None
            else f"delta_bps={fee_delta_bps:+.2f}",
            "NOT_RUN"
            if fee_delta_bps is None
            else "FAILED"
            if abs(fee_delta_bps) > numeric(policy["data_quality"]["fee_reconciliation_tolerance_bps"])
            else "SUCCESS",
        )
        evidence_note = str(fund.get("evidence_note", ""))
        injection_markers = (
            "ignore previous",
            "system prompt",
            "approve this fund",
            "override the rule",
            "reveal the",
        )
        detected_markers = [
            marker for marker in injection_markers if marker in evidence_note.lower()
        ]
        if detected_markers:
            conflicts.append(
                "Potential prompt injection detected in untrusted evidence; content was isolated"
            )
        self._record_tool(
            state,
            "untrusted_content_scanner",
            {
                "content_sha256": hashlib.sha256(
                    evidence_note.encode("utf-8")
                ).hexdigest(),
                "length": len(evidence_note),
            },
            f"detected_markers={detected_markers}",
            "BLOCKED" if detected_markers else "SUCCESS",
        )
        if range_errors:
            state.setdefault("hard_stops", []).extend(x for x in range_errors if x not in state["hard_stops"])
        state["warnings"] = list(dict.fromkeys(warnings))
        state["conflicts"] = list(dict.fromkeys(conflicts))
        state["missing_fields"] = missing
        required = len(policy["data_quality"]["required_fields"])
        confidence = max(0.0, min(0.99, 0.99 - (len(missing) / max(required, 1)) - 0.12 * len(range_errors) - 0.15 * bool(conflicts)))
        quality_score = round(max(0, 100 - len(missing) * 10 - len(range_errors) * 20 - len(conflicts) * 15))
        outcome = "FAIL" if range_errors else "INCOMPLETE" if missing else "PASS_WITH_WARNING" if warnings or conflicts else "PASS"
        evidence_hash = hashlib.sha256(
            json.dumps(
                fund, sort_keys=True, default=str, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        facts = {
            "outcome": outcome,
            "missing_fields": missing,
            "range_errors": range_errors,
            "age_days": age,
            "data_quality_score": quality_score,
            "evidence_hash": evidence_hash,
            "injection_markers": detected_markers,
        }
        fallback = (
            f"Intake {outcome.lower()}: {len(missing)} required field(s) missing, "
            f"{len(range_errors)} range error(s), and data-quality score {quality_score}/100."
        )
        rationale, model = self._narrative(state, facts, fallback, deterministic_outcome=outcome)
        result = {
            "outcome": outcome,
            "confidence": round(confidence, 3),
            "data_quality_score": quality_score,
            "evidence_sha256": evidence_hash,
            "missing_fields": missing,
            "range_errors": range_errors,
            "metrics": {key: fund.get(key) for key in policy["data_quality"]["required_fields"]},
            "rationale": rationale,
            "model": model,
            "tools": TOOL_SETS[self.key],
        }
        return self._finish(state, result)


class ComplianceAgent(BaseAgent):
    key = "compliance"

    def run(self, incoming: WorkflowState) -> WorkflowState:
        state = self._start(incoming)
        fund, rules = state["fund"], state["policy"]["compliance"]
        checks: list[dict[str, Any]] = []
        hard_stops = list(state.get("hard_stops", []))

        status_pass = fund.get("regulatory_status") in rules["allowed_regulatory_statuses"]
        checks.append({"rule_id": "COMP-STATUS-001", "type": "internal_control", "outcome": "PASS" if status_pass else "FAIL", "evidence": fund.get("regulatory_status"), "threshold": rules["allowed_regulatory_statuses"]})
        if not status_pass:
            hard_stops.append(f"Regulatory status is {fund.get('regulatory_status')!r}, not an allowed status")

        observed_type = str(fund.get("fund_type", "")).strip().casefold()
        allowed_types = {
            str(value).strip().casefold(): value
            for value in rules["allowed_fund_types"]
        }
        blocked_types = {
            str(value).strip().casefold(): value
            for value in rules["blocked_fund_types"]
        }
        type_pass = observed_type in allowed_types and observed_type not in blocked_types
        checks.append({"rule_id": "COMP-PRODUCT-002", "type": "internal_control", "outcome": "PASS" if type_pass else "FAIL", "evidence": fund.get("fund_type"), "threshold": f"one of {rules['allowed_fund_types']}"})
        if not type_pass:
            category = "blocked" if observed_type in blocked_types else "unknown/out of scope"
            hard_stops.append(
                f"Product type {fund.get('fund_type')!r} is {category} under illustrative plan policy"
            )

        fee = numeric(fund.get("fee_12b1"))
        distribution_fee = numeric(fund.get("distribution_12b1_fee"))
        service_fee = numeric(fund.get("service_fee"))
        distribution_max = numeric(
            rules["illustrative_distribution_12b1_reference_max_pct"]
        )
        service_max = numeric(rules["illustrative_service_fee_reference_max_pct"])
        combined_max = numeric(
            rules["illustrative_combined_12b1_reference_max_pct"]
        )
        distribution_pass = distribution_fee <= distribution_max
        service_pass = service_fee <= service_max
        combined_pass = fee <= combined_max
        checks.extend(
            [
                {
                    "rule_id": "COMP-12B1-DIST-003A",
                    "type": "regulatory_reference_requires_counsel_validation",
                    "outcome": "WITHIN_CONFIGURED_REFERENCE" if distribution_pass else "FAIL",
                    "evidence_pct": distribution_fee,
                    "threshold_pct": distribution_max,
                    "source": "FINRA_2341",
                },
                {
                    "rule_id": "COMP-12B1-SVC-003B",
                    "type": "regulatory_reference_requires_counsel_validation",
                    "outcome": "WITHIN_CONFIGURED_REFERENCE" if service_pass else "FAIL",
                    "evidence_pct": service_fee,
                    "threshold_pct": service_max,
                    "source": "FINRA_2341",
                },
                {
                    "rule_id": "COMP-12B1-COMB-003C",
                    "type": "regulatory_reference_requires_counsel_validation",
                    "outcome": "WITHIN_CONFIGURED_REFERENCE" if combined_pass else "FAIL",
                    "evidence_pct": fee,
                    "threshold_pct": combined_max,
                    "source": "FINRA_2341",
                },
            ]
        )
        if not (distribution_pass and service_pass and combined_pass):
            hard_stops.append(
                "A configured FINRA 2341 fee-reference threshold was exceeded; counsel applicability review required"
            )

        internal_max = numeric(rules["internal_retirement_plan_12b1_max_pct"])
        internal_pass = fee <= internal_max
        checks.append({"rule_id": "COMP-PLAN-FEE-004", "type": "internal_control", "outcome": "PASS" if internal_pass else "FAIL", "evidence": fee, "threshold_pct": internal_max})
        self._record_tool(state, "deterministic_policy_engine", {"policy_version": state["policy_version"], "fund_type": fund.get("fund_type"), "fee_12b1": fee}, f"{sum(c['outcome'] == 'FAIL' for c in checks)} failed check(s)")
        self._record_tool(state, "approved_regulatory_reference_index", {"reference_ids": ["SEC_FEES", "FINRA_2341"]}, "2 approved references returned")

        state["hard_stops"] = list(dict.fromkeys(hard_stops))
        failures = [c for c in checks if c["outcome"] == "FAIL"]
        outcome = "FAIL" if failures else "PASS"
        confidence = 0.96 if not state.get("conflicts") else 0.80
        facts = {"outcome": outcome, "checks": checks, "hard_stop_count": len(hard_stops)}
        fallback = f"Compliance controls produced {len(checks) - len(failures)} satisfied/configured-reference checks and {len(failures)} failure(s) under policy {state['policy_version']}; no legal conclusion was made."
        rationale, model = self._narrative(state, facts, fallback, deterministic_outcome=outcome)
        return self._finish(state, {
            "outcome": outcome,
            "confidence": confidence,
            "checks": checks,
            "hard_stops": list(dict.fromkeys(hard_stops)),
            "references": OFFICIAL_REFERENCES,
            "rationale": rationale,
            "model": model,
            "tools": TOOL_SETS[self.key],
            "disclaimer": rules["note"],
            "regulatory_determination": "NOT_MADE; production applicability and counsel validation are required",
        })


class GovernanceAgent(BaseAgent):
    key = "governance"

    def run(self, incoming: WorkflowState) -> WorkflowState:
        state = self._start(incoming)
        fund, rules, plan = state["fund"], state["policy"]["suitability"], state.get("plan_profile", {})
        if "allowed_asset_classes" in plan:
            supplied_assets = plan["allowed_asset_classes"]
            allowed_assets = supplied_assets if isinstance(supplied_assets, list) else []
        else:
            allowed_assets = rules["allowed_asset_classes"]
        risk_ceiling = min(numeric(rules["max_risk_score"]), numeric(plan.get("max_risk_score", rules["max_risk_score"])))
        criteria = [
            ("GOV-ASSET-001", fund.get("asset_class") in allowed_assets, fund.get("asset_class"), allowed_assets, "asset class eligibility"),
            ("GOV-RISK-002", numeric(fund.get("risk_score")) <= risk_ceiling, numeric(fund.get("risk_score")), risk_ceiling, "plan risk ceiling"),
            ("GOV-HISTORY-003", numeric(fund.get("track_record_years")) >= numeric(rules["min_track_record_years"]), numeric(fund.get("track_record_years")), rules["min_track_record_years"], "minimum track record"),
            ("GOV-AUM-004", numeric(fund.get("aum_millions")) >= numeric(rules["min_aum_millions"]), numeric(fund.get("aum_millions")), rules["min_aum_millions"], "minimum AUM (millions)"),
            ("GOV-TURNOVER-005", numeric(fund.get("turnover_rate")) <= numeric(rules["max_turnover_pct"]), numeric(fund.get("turnover_rate")), rules["max_turnover_pct"], "maximum turnover percent"),
        ]
        current_lineup = plan.get("current_lineup")
        overlap_found = False
        if isinstance(current_lineup, list):
            normalized_lineup = {
                str(item).strip().upper() for item in current_lineup if str(item).strip()
            }
            overlap_found = str(fund.get("ticker", "")).strip().upper() in normalized_lineup
            criteria.append(
                (
                    "GOV-LINEUP-006",
                    not overlap_found,
                    overlap_found,
                    False,
                    "exact ticker already present in plan lineup",
                )
            )
        checks = [{"rule_id": rid, "type": "plan_suitability_control", "outcome": "PASS" if passed else "FAIL", "evidence": evidence, "threshold": threshold, "criterion": label} for rid, passed, evidence, threshold, label in criteria]
        failures = [check for check in checks if check["outcome"] == "FAIL"]
        self._record_tool(state, "plan_policy_matcher", {"plan_id": plan.get("plan_id", "DEMO-PLAN"), "asset_class": fund.get("asset_class")}, f"{len(failures)} mismatch(es)")
        self._record_tool(state, "risk_band_mapper", {"risk_score": fund.get("risk_score"), "ceiling": risk_ceiling}, "within ceiling" if numeric(fund.get("risk_score")) <= risk_ceiling else "above ceiling")
        if isinstance(current_lineup, list):
            self._record_tool(
                state,
                "lineup_overlap_checker",
                {"ticker": fund.get("ticker"), "lineup_count": len(normalized_lineup)},
                f"exact_ticker_overlap={overlap_found}",
            )
        else:
            self._record_tool(
                state,
                "lineup_overlap_checker",
                {"ticker": fund.get("ticker")},
                "NOT_EVALUATED: current_lineup was not supplied",
                "NOT_RUN",
            )
        outcome = "FAIL" if failures else "PASS"
        confidence = 0.94 if not state.get("conflicts") else 0.79
        facts = {"outcome": outcome, "checks": checks, "plan_id": plan.get("plan_id", "DEMO-PLAN")}
        fallback = f"Plan-fit review passed {len(checks) - len(failures)} of {len(checks)} configured criteria; {len(failures)} exception(s) require sponsor attention."
        rationale, model = self._narrative(state, facts, fallback, deterministic_outcome=outcome)
        return self._finish(state, {"outcome": outcome, "confidence": confidence, "checks": checks, "rationale": rationale, "model": model, "tools": TOOL_SETS[self.key], "scope": "Plan-level fit only; not participant-level advice."})


class FinanceAgent(BaseAgent):
    key = "finance"

    def run(self, incoming: WorkflowState) -> WorkflowState:
        state = self._start(incoming)
        fund, rules = state["fund"], state["policy"]["fees"]
        asset_class = str(fund.get("asset_class", "Other"))
        expense = numeric(fund.get("expense_ratio"))
        cap = expense_cap(asset_class, state["policy"])
        benchmark = expense_benchmark(asset_class, state["policy"])
        expense_decimal = Decimal(str(expense))
        cap_decimal = Decimal(str(cap))
        benchmark_decimal = Decimal(str(benchmark))
        cap_delta_bps = float(
            (expense_decimal - cap_decimal) * Decimal("100")
        )
        benchmark_delta_bps = float(
            (expense_decimal - benchmark_decimal) * Decimal("100")
        )
        within_cap = expense_decimal <= cap_decimal
        boundary_bps = numeric(state["policy"]["human_in_the_loop"]["fee_boundary_bps"])
        boundary_flag = abs(cap_delta_bps) <= boundary_bps
        projection = fee_drag_projection(
            numeric(rules["default_investment_amount"]),
            int(rules["default_horizon_years"]),
            numeric(rules["illustrative_gross_return_pct"]),
            expense,
            benchmark,
        )
        sales_load = numeric(fund.get("sales_load_pct", 0))
        breakpoint_schedule = fund.get("breakpoint_schedule")
        breakpoint_analysis = analyze_breakpoints(
            principal=numeric(rules["default_investment_amount"]),
            base_sales_load_pct=sales_load,
            schedule=str(breakpoint_schedule) if breakpoint_schedule else None,
        )
        breakpoint_status = breakpoint_analysis["status"]
        checks = [
            {"rule_id": "FIN-EXPENSE-001", "type": "internal_cost_control", "outcome": "PASS" if within_cap else "FAIL", "evidence_pct": expense, "cap_pct": cap, "delta_bps": cap_delta_bps},
            {"rule_id": "FIN-BENCHMARK-002", "type": "peer_benchmark", "outcome": "PASS" if expense <= benchmark else "WARN", "evidence_pct": expense, "benchmark_pct": benchmark, "delta_bps": benchmark_delta_bps},
            {"rule_id": "FIN-BREAKPOINT-003", "type": "breakpoint_evidence", "outcome": "PASS" if breakpoint_status in {"VERIFIED", "NOT_APPLICABLE_NO_LOAD"} else "WARN", "sales_load_pct": sales_load, "status": breakpoint_status, "eligible_load_pct": breakpoint_analysis["eligible_load_pct"], "upfront_savings": breakpoint_analysis["upfront_savings"]},
            {"rule_id": "FIN-SALES-LOAD-004", "type": "illustrative_internal_review_control", "outcome": "WARN" if sales_load > numeric(rules["front_end_load_requires_human_above_pct"]) else "PASS", "sales_load_pct": sales_load, "human_review_above_pct": rules["front_end_load_requires_human_above_pct"], "note": "Not represented as a universal regulatory cap."},
        ]
        self._record_tool(state, "category_benchmark_lookup", {"asset_class": asset_class}, f"cap={cap:.2f}%, benchmark={benchmark:.2f}%")
        self._record_tool(state, "fee_drag_calculator", {"principal": projection["principal"], "years": projection["years"], "gross_return_pct": projection["gross_return_pct"]}, f"estimated drag=${projection['estimated_fee_drag_vs_benchmark']:,.0f}")
        self._record_tool(state, "breakpoint_validator", {"sales_load_pct": sales_load, "investment_amount": rules["default_investment_amount"]}, f"{breakpoint_status}; eligible_load={breakpoint_analysis['eligible_load_pct']:.2f}%; savings=${breakpoint_analysis['upfront_savings']:,.0f}", "FAILED" if breakpoint_status in {"MISSING_EVIDENCE", "INVALID_SCHEDULE"} else "SUCCESS")
        outcome = "FAIL" if not within_cap else "PASS_WITH_WARNING" if any(c["outcome"] == "WARN" for c in checks) else "PASS"
        confidence = 0.96 if breakpoint_status in {"VERIFIED", "NOT_APPLICABLE_NO_LOAD"} else 0.82
        facts = {"outcome": outcome, "checks": checks, "projection": projection, "boundary_flag": boundary_flag, "breakpoint_analysis": breakpoint_analysis}
        fallback = f"Expense ratio is {expense:.2f}% versus a {cap:.2f}% category cap and {benchmark:.2f}% benchmark ({benchmark_delta_bps:+.0f} bps); illustrative 20-year drag versus benchmark is ${projection['estimated_fee_drag_vs_benchmark']:,.0f}."
        rationale, model = self._narrative(state, facts, fallback, deterministic_outcome=outcome)
        return self._finish(state, {"outcome": outcome, "confidence": confidence, "checks": checks, "projection": projection, "cap_delta_bps": cap_delta_bps, "benchmark_delta_bps": benchmark_delta_bps, "fee_boundary_flag": boundary_flag, "breakpoint_status": breakpoint_status, "breakpoint_analysis": breakpoint_analysis, "rationale": rationale, "model": model, "tools": TOOL_SETS[self.key], "disclaimer": "Illustration assumes a constant gross return and is not a forecast."})


class DecisionOwnerAgent(BaseAgent):
    key = "decision_owner"

    def run(self, incoming: WorkflowState) -> WorkflowState:
        state = self._start(incoming)
        results = state.get("agent_results", {})
        specialist_results = [results[key] for key in ("analyst", "compliance", "governance", "finance") if key in results]
        failures = sum(1 for result in specialist_results if result.get("outcome") == "FAIL")
        warnings_count = sum(1 for result in specialist_results if result.get("outcome") in {"PASS_WITH_WARNING", "INCOMPLETE"}) + len(state.get("warnings", []))
        hard_stops = list(dict.fromkeys(state.get("hard_stops", [])))
        conflicts = list(dict.fromkeys(state.get("conflicts", [])))
        missing = state.get("missing_fields", [])
        finance = results.get("finance", {})
        fee_boundary = bool(finance.get("fee_boundary_flag"))

        scoring = state["policy"]["decision_scoring"]
        weights = scoring["weights"]
        risk_score = min(
            int(scoring["maximum_score"]),
            len(hard_stops) * int(weights["hard_stop"])
            + failures * int(weights["failed_specialist"])
            + len(conflicts) * int(weights["source_conflict"])
            + len(missing) * int(weights["missing_required_field"])
            + warnings_count * int(weights["warning"])
            + (int(weights["fee_boundary"]) if fee_boundary else 0),
        )
        confidences = [numeric(result.get("confidence")) for result in specialist_results]
        confidence = round(min(confidences), 3) if confidences else 0.0

        if hard_stops or risk_score >= int(scoring["reject_at_or_above"]):
            recommendation = "REJECT"
        elif missing or conflicts or failures or risk_score >= int(scoring["escalate_at_or_above"]):
            recommendation = "ESCALATE"
        elif warnings_count:
            recommendation = "APPROVE_WITH_CONDITIONS"
        else:
            recommendation = "APPROVE"

        hitl = state["policy"]["human_in_the_loop"]
        human_reasons: list[str] = []
        if recommendation != "APPROVE":
            human_reasons.append(f"Recommendation is {recommendation}")
        if confidence < numeric(hitl["escalate_below_confidence"]):
            human_reasons.append(f"Confidence {confidence:.2f} is below {numeric(hitl['escalate_below_confidence']):.2f}")
        if risk_score >= int(hitl["mandatory_review_risk_score"]):
            human_reasons.append(f"Risk score {risk_score} meets mandatory-review threshold {hitl['mandatory_review_risk_score']}")
        if fee_boundary:
            human_reasons.append(f"Expense ratio is within {hitl['fee_boundary_bps']} bps of its cap")
        if conflicts:
            human_reasons.append("Source evidence conflicts")
        if missing:
            human_reasons.append("Required data remains missing after enrichment")
        if hard_stops and "Hard-stop control triggered" not in human_reasons:
            human_reasons.append("Hard-stop control triggered")
        if recommendation == "APPROVE" and confidence < numeric(hitl["minimum_auto_approval_confidence"]):
            human_reasons.append(f"Auto-approval requires confidence >= {numeric(hitl['minimum_auto_approval_confidence']):.2f}")
        if recommendation == "APPROVE" and risk_score > int(hitl["auto_approval_max_risk_score"]):
            human_reasons.append(f"Auto-approval requires risk <= {hitl['auto_approval_max_risk_score']}")
        needs_human = bool(human_reasons)
        if needs_human and recommendation == "APPROVE":
            recommendation = "ESCALATE"

        decisive = {
            "hard_stops": hard_stops,
            "conflicts": conflicts,
            "missing_fields": missing,
            "failed_agents": [key for key, result in results.items() if result.get("outcome") == "FAIL"],
        }
        self._record_tool(state, "finding_aggregator", {"specialist_count": len(specialist_results)}, f"failures={failures}, warnings={warnings_count}")
        self._record_tool(state, "deterministic_risk_scorer", {"hard_stops": len(hard_stops), "failures": failures, "conflicts": len(conflicts), "missing": len(missing)}, f"risk_score={risk_score}")
        self._record_tool(state, "HITL_router", {"recommendation": recommendation, "confidence": confidence, "risk_score": risk_score}, f"needs_human={needs_human}")
        facts = {"recommendation": recommendation, "risk_score": risk_score, "confidence": confidence, "human_reasons": human_reasons, "decisive_evidence": decisive}
        fallback = f"Recommendation: {recommendation}. Deterministic risk is {risk_score}/100 with {confidence:.0%} minimum specialist confidence. " + (f"Human review is required: {'; '.join(human_reasons)}." if needs_human else "All auto-approval gates passed.")
        rationale, model = self._narrative(state, facts, fallback, deterministic_outcome=recommendation)

        state["risk_score"] = risk_score
        state["confidence"] = confidence
        state["recommendation"] = recommendation
        state["needs_human"] = needs_human
        state["human_reasons"] = human_reasons
        # The prominent decision summary is deterministic. Optional model prose may
        # appear in the agent detail, but it cannot contradict or replace this gate.
        state["final_summary"] = fallback
        state["status"] = "AWAITING_HUMAN_REVIEW" if needs_human else "COMPLETED"
        result = {"outcome": recommendation, "confidence": confidence, "risk_score": risk_score, "risk_formula": {"version": scoring["formula_version"], "weights": weights, "reject_at_or_above": scoring["reject_at_or_above"], "escalate_at_or_above": scoring["escalate_at_or_above"]}, "needs_human": needs_human, "human_reasons": human_reasons, "decisive_evidence": decisive, "authoritative_summary": fallback, "rationale": rationale, "model": model, "tools": TOOL_SETS[self.key]}
        return self._finish(state, result)


AGENTS = {
    "analyst": AnalystAgent(),
    "compliance": ComplianceAgent(),
    "governance": GovernanceAgent(),
    "finance": FinanceAgent(),
    "decision_owner": DecisionOwnerAgent(),
}
