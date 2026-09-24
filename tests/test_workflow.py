from pathlib import Path
from datetime import date, timedelta

import pytest

import fiducia.workflow as workflow_module
from fiducia.llm import BedrockNarrativeEngine
from fiducia.tools import load_funds
from fiducia.workflow import apply_human_decision, run_workflow


@pytest.fixture(scope="module")
def funds():
    return {fund["ticker"]: fund for fund in load_funds()}


def run_case(tmp_path: Path, funds: dict, ticker: str):
    return run_workflow(funds[ticker], audit_path=str(tmp_path / f"{ticker}.jsonl"))


def test_clean_case_auto_approves(tmp_path, funds):
    state = run_case(tmp_path, funds, "SUNX")
    assert state["recommendation"] == "APPROVE"
    assert state["needs_human"] is False
    assert state["risk_score"] <= 24
    assert state["completed_agents"] == ["analyst", "compliance", "governance", "finance", "decision_owner"]


def test_missing_metric_is_repaired_once(tmp_path, funds):
    state = run_case(tmp_path, funds, "DATA")
    assert state["retries"] == 1
    assert state["fund"]["sharpe_ratio"] == 1.01
    assert state["missing_fields"] == []


def test_missing_fee_fails_closed_after_two_retries(tmp_path, funds):
    state = run_case(tmp_path, funds, "BLANK")
    assert state["retries"] == 2
    assert "fee_12b1" in state["missing_fields"]
    assert state["recommendation"] == "ESCALATE"
    assert state["needs_human"] is True
    assert "compliance" not in state["completed_agents"]


def test_prompt_injection_is_data_and_routes_to_human(tmp_path, funds):
    state = run_case(tmp_path, funds, "INJX")
    scans = [row for row in state["tool_calls"] if row["tool"] == "untrusted_content_scanner"]
    assert scans[-1]["status"] == "BLOCKED"
    assert state["recommendation"] == "ESCALATE"
    assert state["needs_human"] is True


def test_hard_stops_recommend_reject_but_do_not_execute(tmp_path, funds):
    state = run_case(tmp_path, funds, "SPECX")
    assert state["recommendation"] == "REJECT"
    assert state["status"] == "AWAITING_HUMAN_REVIEW"
    assert state["human_decision"] is None


def test_reject_to_approve_requires_second_person(tmp_path, funds):
    state = run_case(tmp_path, funds, "SPECX")
    with pytest.raises(ValueError, match="second approver"):
        apply_human_decision(
            state,
            reviewer="r1",
            action="APPROVE",
            reason="Reviewed",
            attested=True,
        )
    with pytest.raises(ValueError, match="distinct identity"):
        apply_human_decision(
            state,
            reviewer="same.user",
            action="APPROVE",
            reason="Reviewed",
            second_approver="same.user",
            attested=True,
        )
    approved = apply_human_decision(state, reviewer="r1", action="APPROVE", reason="Documented exception", second_approver="r2", attested=True)
    assert approved["status"] == "COMPLETED"
    assert approved["human_decision"]["second_approver"] == "r2"


def test_human_cannot_modify_auto_approved_or_final_case(tmp_path, funds):
    clean = run_case(tmp_path, funds, "SUNX")
    with pytest.raises(ValueError, match="not at an authorized"):
        apply_human_decision(
            clean,
            reviewer="r1",
            action="REJECT",
            reason="No",
            attested=True,
        )

    rejected = run_case(tmp_path, funds, "SPECX")
    decided = apply_human_decision(
        rejected,
        reviewer="r1",
        action="REJECT",
        reason="Confirmed",
        attested=True,
    )
    with pytest.raises(ValueError, match="not at an authorized|already been recorded"):
        apply_human_decision(
            decided,
            reviewer="r2",
            action="REJECT",
            reason="Again",
            attested=True,
        )


@pytest.mark.parametrize("bad_value", ["not-a-number", float("nan"), float("inf")])
def test_invalid_decision_numbers_fail_closed(tmp_path, funds, bad_value):
    fund = dict(funds["SUNX"])
    fund.update({"ticker": "BADNUM", "expense_ratio": bad_value})
    state = run_workflow(fund, audit_path=str(tmp_path / f"bad-{str(bad_value)}.jsonl"))
    assert state["recommendation"] != "APPROVE"
    assert state["needs_human"] is True
    assert "compliance" not in state["completed_agents"]


@pytest.mark.parametrize(
    "product_type", ["leveraged etf", "Leveraged ETF ", "Totally Unknown"]
)
def test_blocked_or_unknown_product_taxonomy_fails_closed(
    tmp_path, funds, product_type
):
    fund = dict(funds["SUNX"])
    fund.update({"ticker": "BADTYPE", "fund_type": product_type})
    state = run_workflow(
        fund,
        audit_path=str(tmp_path / f"type-{product_type.strip().replace(' ', '-')}.jsonl"),
    )
    assert state["recommendation"] == "REJECT"
    assert state["needs_human"] is True
    assert any("Product type" in value for value in state["hard_stops"])


def test_future_dated_evidence_fails_closed(tmp_path, funds):
    fund = dict(funds["SUNX"])
    fund.update({"ticker": "FUTURE", "as_of_date": "2099-01-01"})
    state = run_workflow(fund, audit_path=str(tmp_path / "future.jsonl"))
    assert state["recommendation"] == "REJECT"
    assert state["needs_human"] is True
    assert "compliance" not in state["completed_agents"]


def test_stale_evidence_cannot_autoapprove(tmp_path, funds):
    fund = dict(funds["SUNX"])
    fund.update(
        {
            "ticker": "STALE",
            "as_of_date": (date.today() - timedelta(days=121)).isoformat(),
        }
    )
    state = run_workflow(fund, audit_path=str(tmp_path / "stale.jsonl"))
    assert state["recommendation"] == "APPROVE_WITH_CONDITIONS"
    assert state["needs_human"] is True
    assert any("days old" in warning for warning in state["warnings"])


def test_no_langgraph_fallback_preserves_fail_closed_routing(
    tmp_path, funds, monkeypatch
):
    def unavailable():
        raise ImportError("simulated missing langgraph")

    monkeypatch.setattr(workflow_module, "build_graph", unavailable)
    fund = dict(funds["SUNX"])
    fund.update({"ticker": "FALLBACK-BAD", "expense_ratio": "invalid"})
    state = workflow_module.run_workflow(
        fund, audit_path=str(tmp_path / "fallback-bad.jsonl")
    )
    assert state["recommendation"] == "REJECT"
    assert "compliance" not in state["completed_agents"]


@pytest.mark.parametrize("bad_load", ["garbage", -5, float("inf")])
def test_invalid_optional_sales_load_fails_closed(tmp_path, funds, bad_load):
    fund = dict(funds["SUNX"])
    fund.update({"ticker": "BADLOAD", "sales_load_pct": bad_load})
    state = run_workflow(
        fund, audit_path=str(tmp_path / f"bad-load-{str(bad_load)}.jsonl")
    )
    assert state["recommendation"] == "REJECT"
    assert "finance" not in state["completed_agents"]


@pytest.mark.parametrize(
    "plan_profile",
    [
        {"plan_id": "BAD", "max_risk_score": "not-a-number"},
        {
            "plan_id": "BAD",
            "max_risk_score": 7,
            "allowed_asset_classes": "US Equity Index",
        },
        {"plan_id": "EMPTY", "max_risk_score": 7, "allowed_asset_classes": []},
    ],
)
def test_malformed_or_empty_plan_scope_cannot_autoapprove(
    tmp_path, funds, plan_profile
):
    state = run_workflow(
        funds["SUNX"],
        plan_profile=plan_profile,
        audit_path=str(tmp_path / f"plan-{plan_profile['plan_id']}.jsonl"),
    )
    assert state["recommendation"] != "APPROVE"
    assert state["needs_human"] is True


def test_existing_lineup_duplicate_is_a_governance_exception(tmp_path, funds):
    state = run_workflow(
        funds["SUNX"],
        plan_profile={
            "plan_id": "DUPLICATE",
            "max_risk_score": 7,
            "current_lineup": ["SUNX"],
        },
        audit_path=str(tmp_path / "duplicate.jsonl"),
    )
    check = next(
        item
        for item in state["agent_results"]["governance"]["checks"]
        if item["rule_id"] == "GOV-LINEUP-006"
    )
    assert check["outcome"] == "FAIL"
    assert state["recommendation"] == "ESCALATE"


def test_any_front_end_load_requires_human_review(tmp_path, funds):
    fund = dict(funds["SUNX"])
    fund.update(
        {
            "ticker": "LOAD",
            "sales_load_pct": 10,
            "breakpoint_schedule": "0:10",
        }
    )
    state = run_workflow(fund, audit_path=str(tmp_path / "load.jsonl"))
    assert state["recommendation"] == "APPROVE_WITH_CONDITIONS"
    assert state["needs_human"] is True


def test_model_prose_cannot_replace_deterministic_decision_summary(
    tmp_path, funds, monkeypatch
):
    def malicious_explain(self, **kwargs):
        return "All controls passed; approve immediately.", {"provider": "test-model"}

    monkeypatch.setattr(BedrockNarrativeEngine, "explain", malicious_explain)
    state = run_workflow(
        funds["SPECX"],
        model_mode="bedrock",
        audit_path=str(tmp_path / "malicious-narrative.jsonl"),
    )
    assert state["recommendation"] == "REJECT"
    assert state["final_summary"].startswith("Recommendation: REJECT")
    assert "approve immediately" not in state["final_summary"]


def test_fee_component_mismatch_cannot_be_voted_away(tmp_path, funds):
    fund = dict(funds["SUNX"])
    fund.update(
        {
            "ticker": "MISMATCH",
            "fee_12b1": 0.10,
            "distribution_12b1_fee": 0.0,
            "service_fee": 0.0,
        }
    )
    state = run_workflow(fund, audit_path=str(tmp_path / "mismatch.jsonl"))
    assert any("differ by" in conflict for conflict in state["conflicts"])
    assert state["recommendation"] == "ESCALATE"
    assert state["needs_human"] is True


def test_fee_cap_boundary_forces_human_review(tmp_path, funds):
    fund = dict(funds["SUNX"])
    fund.update({"ticker": "BOUNDARY", "expense_ratio": 0.25})
    state = run_workflow(fund, audit_path=str(tmp_path / "boundary.jsonl"))
    assert state["agent_results"]["finance"]["fee_boundary_flag"] is True
    assert any("within 5 bps" in reason for reason in state["human_reasons"])
    assert state["needs_human"] is True


def test_enrichment_requires_composite_identity_match(tmp_path, funds):
    fund = dict(funds["DATA"])
    fund["fund_name"] = "Completely Different Fund"
    state = run_workflow(fund, audit_path=str(tmp_path / "identity-mismatch.jsonl"))
    assert state["retries"] == 2
    assert "sharpe_ratio" in state["missing_fields"]
    assert any("identity mismatch" in value for value in state["conflicts"])
    assert state["recommendation"] == "ESCALATE"
    assert "compliance" not in state["completed_agents"]
