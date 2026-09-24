import json

import pytest

from fiducia.tools import load_funds
from fiducia.validation import PayloadValidationError, validate_api_payload
from fiducia.workflow import run_workflow


@pytest.fixture()
def clean_fund():
    return next(fund for fund in load_funds() if fund["ticker"] == "SUNX")


def test_boolean_financial_values_fail_closed_and_raw_type_is_audited(
    tmp_path, clean_fund
):
    fund = dict(clean_fund)
    for field in (
        "expense_ratio",
        "fee_12b1",
        "distribution_12b1_fee",
        "service_fee",
    ):
        fund[field] = False
    path = tmp_path / "boolean-input.jsonl"
    state = run_workflow(fund, audit_path=str(path))

    assert state["recommendation"] == "REJECT"
    assert state["needs_human"] is True
    assert "compliance" not in state["completed_agents"]
    assert state["fund"]["expense_ratio"] is False

    created = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert created["payload"]["raw_fund_snapshot"]["expense_ratio"] is False
    assert created["payload"]["normalized_fund_snapshot"]["expense_ratio"] is False


@pytest.mark.parametrize("bad_plan", [[], "not-an-object", {}, {"plan_id": ""}])
def test_malformed_explicit_plan_cannot_select_demo_defaults(
    tmp_path, clean_fund, bad_plan
):
    state = run_workflow(
        clean_fund,
        plan_profile=bad_plan,  # type: ignore[arg-type]
        audit_path=str(tmp_path / f"bad-plan-{len(str(bad_plan))}.jsonl"),
    )
    assert state["recommendation"] == "REJECT"
    assert state["needs_human"] is True
    assert state["ingress_errors"]


@pytest.mark.parametrize(
    "updates",
    [
        {"ticker": 123},
        {"fund_name": {"unexpected": "object"}},
    ],
)
def test_non_string_fund_identity_fails_closed(tmp_path, clean_fund, updates):
    fund = dict(clean_fund)
    fund.update(updates)
    state = run_workflow(fund, audit_path=str(tmp_path / "bad-identity.jsonl"))
    assert state["recommendation"] == "REJECT"
    assert "compliance" not in state["completed_agents"]


def test_external_api_contract_rejects_boolean_numbers_and_bad_plan(clean_fund):
    bad_fund = dict(clean_fund)
    bad_fund["expense_ratio"] = False
    with pytest.raises(PayloadValidationError, match="boolean"):
        validate_api_payload({"fund": bad_fund, "model_mode": "offline"})
    with pytest.raises(PayloadValidationError, match="plan_profile"):
        validate_api_payload(
            {"fund": clean_fund, "plan_profile": [], "model_mode": "offline"}
        )
    with pytest.raises(PayloadValidationError, match="unsupported field"):
        validate_api_payload(
            {"fund": clean_fund, "model_mode": "offline", "surprise": True}
        )


def test_absent_sales_load_is_missing_evidence_not_zero(tmp_path, clean_fund):
    fund = dict(clean_fund)
    fund.update({"ticker": "NOSALE", "fund_name": "No Sales Load Evidence"})
    fund.pop("sales_load_pct")
    state = run_workflow(fund, audit_path=str(tmp_path / "missing-load.jsonl"))
    assert "sales_load_pct" in state["missing_fields"]
    assert state["recommendation"] == "ESCALATE"
    assert "finance" not in state["completed_agents"]


def test_regulatory_reference_is_not_reported_as_legal_pass(tmp_path, clean_fund):
    state = run_workflow(clean_fund, audit_path=str(tmp_path / "reference.jsonl"))
    compliance = state["agent_results"]["compliance"]
    reference_checks = [
        check
        for check in compliance["checks"]
        if check["type"] == "regulatory_reference_requires_counsel_validation"
    ]
    assert reference_checks
    assert all(
        check["outcome"] == "WITHIN_CONFIGURED_REFERENCE"
        for check in reference_checks
    )
    assert compliance["regulatory_determination"].startswith("NOT_MADE")
