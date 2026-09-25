"""Tests for the TIAA Fiduciary Guardrail Score (TFGS) and Fiduciary Governor."""

from __future__ import annotations

from pathlib import Path

import pytest

from fiducia.agents import FiduciaryGovernorAgent, calculate_tfgs_score
from fiducia.tools import load_funds
from fiducia.workflow import create_initial_state, run_workflow


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture(scope="module")
def funds():
    return {f["ticker"]: f for f in load_funds()}


# ---------------------------------------------------------------------------
# calculate_tfgs_score unit tests
# ---------------------------------------------------------------------------

def _base_state(tmp_path: Path) -> dict:
    """Minimal state for TFGS unit tests — all fields clean."""
    return {
        "missing_fields": [],
        "risk_score": 0,
        "fund": {"asset_class": "US Equity Index", "expense_ratio": 0.06},
        "policy": {
            "fees": {
                "expense_ratio_caps_pct": {
                    "US Equity Index": 0.25,
                    "US Equity Active": 0.75,
                    "International Equity": 0.85,
                    "Other": 0.80,
                }
            }
        },
        "agent_results": {
            "analyst":    {"confidence": 0.99},
            "compliance": {"confidence": 0.96},
            "governance": {"confidence": 0.94},
            "finance":    {"confidence": 0.96},
        },
    }


def test_clean_case_tfgs_score_is_100(tmp_path):
    state = _base_state(tmp_path)
    result = calculate_tfgs_score(state)
    assert result["score"] == 100
    assert result["deductions"] == []


def test_missing_fields_deducts_15(tmp_path):
    state = _base_state(tmp_path)
    state["missing_fields"] = ["sharpe_ratio"]
    result = calculate_tfgs_score(state)
    assert result["score"] == 85
    assert any(d["points"] == -15 for d in result["deductions"])
    deduction = next(d for d in result["deductions"] if d["points"] == -15)
    assert deduction["source_agent"] == "analyst"
    assert "sharpe_ratio" in deduction["detail"]


def test_risk_score_above_35_deducts_10(tmp_path):
    state = _base_state(tmp_path)
    state["risk_score"] = 36
    result = calculate_tfgs_score(state)
    assert result["score"] == 90
    assert any(d["points"] == -10 and "risk" in d["reason"].lower() for d in result["deductions"])


def test_risk_score_at_35_no_deduction(tmp_path):
    state = _base_state(tmp_path)
    state["risk_score"] = 35
    result = calculate_tfgs_score(state)
    assert result["score"] == 100


def test_expense_within_10bps_of_cap_deducts_10(tmp_path):
    state = _base_state(tmp_path)
    # cap for US Equity Index = 0.25%; expense = 0.24% → 1 bps → within 10 bps
    state["fund"] = {"asset_class": "US Equity Index", "expense_ratio": 0.24}
    result = calculate_tfgs_score(state)
    assert result["score"] == 90
    assert any(d["points"] == -10 and d["source_agent"] == "finance" for d in result["deductions"])


def test_expense_outside_10bps_no_deduction(tmp_path):
    state = _base_state(tmp_path)
    # cap 0.25%, expense 0.06% → 19 bps > 10 bps → no deduction
    result = calculate_tfgs_score(state)
    assert result["score"] == 100


def test_low_specialist_confidence_deducts_15(tmp_path):
    state = _base_state(tmp_path)
    state["agent_results"]["compliance"]["confidence"] = 0.80  # below 0.90
    result = calculate_tfgs_score(state)
    assert result["score"] == 85
    deduction = next(d for d in result["deductions"] if d["evidence_field"] == "confidence")
    assert deduction["points"] == -15
    assert any(a["agent"] == "compliance" for a in deduction["detail"])


def test_multiple_deductions_stack(tmp_path):
    state = _base_state(tmp_path)
    state["missing_fields"] = ["sharpe_ratio"]   # -15
    state["risk_score"] = 50                      # -10
    # compliance confidence below threshold        # -15
    state["agent_results"]["compliance"]["confidence"] = 0.79
    result = calculate_tfgs_score(state)
    assert result["score"] == 60
    assert len(result["deductions"]) == 3


# ---------------------------------------------------------------------------
# Governor SELF_CORRECT integration — unit-style with crafted state
# ---------------------------------------------------------------------------

def _governor_state(tmp_path: Path, missing: list[str], retries: int, max_retries: int, conflicts: list[str], hard_stops: list[str], analyst_outcome: str = "INCOMPLETE") -> dict:
    """Craft a governor-ready state for SELF_CORRECT path testing."""
    from fiducia.workflow import create_initial_state
    from fiducia.tools import load_funds
    funds = {f["ticker"]: f for f in load_funds()}
    fund = dict(funds["DATA"])
    state = create_initial_state(fund, audit_path=str(tmp_path / "gov.jsonl"))
    state["missing_fields"] = missing
    state["conflicts"] = conflicts
    state["hard_stops"] = hard_stops
    state["retries"] = retries
    state["max_retries"] = max_retries
    state["agent_results"] = {
        "analyst":    {"outcome": analyst_outcome, "confidence": 0.94, "missing_fields": missing},
        "compliance": {"outcome": "PASS", "confidence": 0.96, "checks": []},
        "governance": {"outcome": "PASS", "confidence": 0.94, "checks": []},
        "finance":    {"outcome": "PASS", "confidence": 0.96, "checks": [], "fee_boundary_flag": False},
    }
    state["completed_agents"] = ["analyst", "compliance", "governance", "finance"]
    return state


def test_governor_self_corrects_to_analyst(tmp_path):
    """Governor emits SELF_CORRECT when TFGS < 80 due to missing fields + expense near cap.

    Two deductions: missing data (−15) + expense within 10 bps of cap (−10) = TFGS 75 < 80.
    """
    from fiducia.workflow import create_initial_state
    from fiducia.tools import load_funds
    funds_map = {f["ticker"]: f for f in load_funds()}
    fund = dict(funds_map["DATA"])
    fund["expense_ratio"] = 0.24   # cap for US Equity Index = 0.25% → 1 bps → −10 deduction
    fund["sharpe_ratio"] = None    # missing → −15 deduction  →  TFGS = 75
    state = create_initial_state(fund, audit_path=str(tmp_path / "gov_sc.jsonl"))
    state["missing_fields"] = ["sharpe_ratio"]
    state["conflicts"] = []
    state["hard_stops"] = []
    state["retries"] = 0
    state["max_retries"] = 2
    state["agent_results"] = {
        "analyst":    {"outcome": "INCOMPLETE", "confidence": 0.94, "missing_fields": ["sharpe_ratio"]},
        "compliance": {"outcome": "PASS",       "confidence": 0.96, "checks": []},
        "governance": {"outcome": "PASS",       "confidence": 0.94, "checks": []},
        "finance":    {"outcome": "PASS",       "confidence": 0.96, "checks": [], "fee_boundary_flag": False},
    }
    state["completed_agents"] = ["analyst", "compliance", "governance", "finance"]
    result = FiduciaryGovernorAgent().run(state)
    assert result["recommendation"] == "SELF_CORRECT", (
        f"Expected SELF_CORRECT but got {result['recommendation']!r}; "
        f"TFGS={result.get('tfgs_score')}, receipt={result.get('fiduciary_guardrail_receipt')}"
    )
    assert result["self_correct_target"] == "analyst"
    receipt = result["fiduciary_guardrail_receipt"]
    assert receipt["decision"] == "SELF_CORRECT"
    assert receipt["tfgs_score"] < 80
    assert receipt["receipt_sha256"]  # integrity hash populated


def test_retry_exhaustion_routes_to_human_not_self_correct(tmp_path):
    """When retries == max_retries the governor must not issue SELF_CORRECT."""
    state = _governor_state(tmp_path, missing=["sharpe_ratio"], retries=2, max_retries=2,
                            conflicts=[], hard_stops=[])
    result = FiduciaryGovernorAgent().run(state)
    assert result["recommendation"] != "SELF_CORRECT"
    assert result["needs_human"] is True


def test_self_correct_blocked_by_conflicts(tmp_path):
    """Conflicts (CONFX/INJX pattern) must never produce SELF_CORRECT."""
    state = _governor_state(tmp_path, missing=["sharpe_ratio"], retries=0, max_retries=2,
                            conflicts=["Conflicting values from source systems"],
                            hard_stops=[])
    result = FiduciaryGovernorAgent().run(state)
    assert result["recommendation"] != "SELF_CORRECT"


def test_self_correct_blocked_by_hard_stops(tmp_path):
    """Hard stops must prevent SELF_CORRECT (SPECX-like guard)."""
    state = _governor_state(tmp_path, missing=["sharpe_ratio"], retries=0, max_retries=2,
                            conflicts=[], hard_stops=["Regulatory status is 'Under Review'"])
    result = FiduciaryGovernorAgent().run(state)
    assert result["recommendation"] != "SELF_CORRECT"


def test_self_correct_blocked_when_analyst_failed(tmp_path):
    """Analyst FAIL (range errors) must not route to SELF_CORRECT."""
    state = _governor_state(tmp_path, missing=["sharpe_ratio"], retries=0, max_retries=2,
                            conflicts=[], hard_stops=[], analyst_outcome="FAIL")
    result = FiduciaryGovernorAgent().run(state)
    assert result["recommendation"] != "SELF_CORRECT"


# ---------------------------------------------------------------------------
# Guardrail: 7 demo scenarios must never SELF_CORRECT and routes must match
# ---------------------------------------------------------------------------

_EXPECTED = [
    ("SUNX",  "APPROVE",                 False),
    ("DATA",  "APPROVE_WITH_CONDITIONS", True),
    ("ALPHX", "ESCALATE",                True),
    ("SPECX", "REJECT",                  True),
    ("CONFX", "ESCALATE",                True),
    ("INJX",  "ESCALATE",                True),
    ("BLANK", "ESCALATE",                True),
]


@pytest.mark.parametrize("ticker,expected_rec,expected_human", _EXPECTED)
def test_scenario_route_locked_and_no_self_correct(tmp_path, funds, ticker, expected_rec, expected_human):
    """Each scenario must hit its documented route and must never end as SELF_CORRECT."""
    state = run_workflow(funds[ticker], audit_path=str(tmp_path / f"{ticker}.jsonl"))
    assert state["recommendation"] == expected_rec, (
        f"{ticker}: expected {expected_rec!r}, got {state['recommendation']!r}"
    )
    assert state["needs_human"] is expected_human
    assert state["recommendation"] != "SELF_CORRECT"
    # receipt must be present and have a valid sha256
    receipt = state.get("fiduciary_guardrail_receipt", {})
    assert receipt.get("receipt_sha256"), f"{ticker}: receipt sha256 missing"
    assert "tfgs_score" in receipt


@pytest.mark.parametrize("ticker", ["SPECX", "CONFX", "INJX"])
def test_conflict_or_hardstop_scenarios_never_self_correct(tmp_path, funds, ticker):
    """SPECX/CONFX/INJX must never trigger SELF_CORRECT per guardrails."""
    state = run_workflow(funds[ticker], audit_path=str(tmp_path / f"{ticker}.jsonl"))
    assert state["recommendation"] != "SELF_CORRECT"
    receipt = state.get("fiduciary_guardrail_receipt", {})
    assert receipt.get("decision") != "SELF_CORRECT"


# ---------------------------------------------------------------------------
# TFGS values for all 7 scenarios (informational assertions on score range)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ticker,min_score,max_score", [
    ("SUNX",  95, 100),  # clean: 100
    ("DATA",  95, 100),  # clean after repair: 100
    ("ALPHX", 95, 100),  # no deductions: 100
    ("SPECX", 85,  95),  # risk_score deduction: 90
    ("CONFX", 60,  85),  # confidence + expense-near-cap deductions: 75
    ("INJX",  75,  95),  # confidence deduction: 85
    ("BLANK", 55,  80),  # missing + confidence deductions: 70
])
def test_tfgs_score_in_expected_range(tmp_path, funds, ticker, min_score, max_score):
    state = run_workflow(funds[ticker], audit_path=str(tmp_path / f"tfgs-{ticker}.jsonl"))
    tfgs = state.get("tfgs_score", -1)
    assert min_score <= tfgs <= max_score, (
        f"{ticker}: TFGS {tfgs} not in [{min_score}, {max_score}]"
    )
