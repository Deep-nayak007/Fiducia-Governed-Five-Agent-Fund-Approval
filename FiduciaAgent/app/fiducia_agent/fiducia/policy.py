"""Versioned deterministic policy evaluation helpers.

The policy engine, not the language model, owns numerical comparisons and routing.
All thresholds are illustrative and loaded from a versioned configuration file.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "config" / "policy_rules.json"


def load_policy(path: str | Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def missing_required_fields(fund: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    return [
        field
        for field in policy["data_quality"]["required_fields"]
        if field not in fund or is_missing(fund.get(field))
    ]


def numeric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def data_age_days(as_of_date: str, today: date | None = None) -> int:
    observed = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    return ((today or date.today()) - observed).days


def expense_cap(asset_class: str, policy: dict[str, Any]) -> float:
    caps = policy["fees"]["expense_ratio_caps_pct"]
    return numeric(caps.get(asset_class, caps["Other"]))


def expense_benchmark(asset_class: str, policy: dict[str, Any]) -> float:
    benchmarks = policy["fees"]["benchmark_expense_ratio_pct"]
    return numeric(benchmarks.get(asset_class, benchmarks["Other"]))


def fee_drag_projection(
    principal: float,
    years: int,
    gross_return_pct: float,
    expense_ratio_pct: float,
    benchmark_expense_ratio_pct: float,
) -> dict[str, float]:
    """Compare ending values after annual expense drag; this is illustrative, not a forecast."""
    fund_rate = (gross_return_pct - expense_ratio_pct) / 100
    benchmark_rate = (gross_return_pct - benchmark_expense_ratio_pct) / 100
    fund_ending = principal * ((1 + fund_rate) ** years)
    benchmark_ending = principal * ((1 + benchmark_rate) ** years)
    return {
        "principal": round(principal, 2),
        "years": years,
        "gross_return_pct": round(gross_return_pct, 4),
        "fund_ending_value": round(fund_ending, 2),
        "benchmark_ending_value": round(benchmark_ending, 2),
        "estimated_fee_drag_vs_benchmark": round(max(0.0, benchmark_ending - fund_ending), 2),
        "annual_fee_dollars_at_principal": round(principal * expense_ratio_pct / 100, 2),
    }
