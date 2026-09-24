from fiducia.policy import expense_cap, fee_drag_projection, load_policy, missing_required_fields
from fiducia.tools import analyze_breakpoints


def test_expense_caps_are_internal_and_asset_specific():
    policy = load_policy()
    assert expense_cap("US Equity Index", policy) == 0.25
    assert expense_cap("US Equity Active", policy) == 0.75
    assert policy["metadata"]["authority_type"] == "illustrative_internal_policy"


def test_blank_is_missing_not_zero():
    policy = load_policy()
    missing = missing_required_fields({"fee_12b1": ""}, policy)
    assert "fee_12b1" in missing


def test_fee_projection_is_reproducible_and_nonnegative():
    result = fee_drag_projection(1_000_000, 20, 6.0, 0.75, 0.25)
    assert result["estimated_fee_drag_vs_benchmark"] > 0
    assert result == fee_drag_projection(1_000_000, 20, 6.0, 0.75, 0.25)


def test_breakpoint_analysis_is_deterministic_and_validated():
    result = analyze_breakpoints(
        principal=1_000_000,
        base_sales_load_pct=4.5,
        schedule="250000:3.5;500000:2.5;1000000:1.5",
    )
    assert result["status"] == "VERIFIED"
    assert result["eligible_load_pct"] == 1.5
    assert result["upfront_savings"] == 30_000
    invalid = analyze_breakpoints(
        principal=1_000_000,
        base_sales_load_pct=4.5,
        schedule="not-a-schedule",
    )
    assert invalid["status"] == "INVALID_SCHEDULE"
