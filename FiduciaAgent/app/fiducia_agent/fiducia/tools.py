"""Narrow, auditable tools available to Fiducia agents."""

from __future__ import annotations

import csv
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .policy import numeric, parse_bool


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "data" / "enrichment_reference.csv"
MOCK_PATH = ROOT / "data" / "mock_funds.csv"

NUMERIC_FIELDS = {
    "nav",
    "expense_ratio",
    "sharpe_ratio",
    "fee_12b1",
    "distribution_12b1_fee",
    "service_fee",
    "turnover_rate",
    "aum_millions",
    "track_record_years",
    "risk_score",
    "sales_load_pct",
}


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    for field in NUMERIC_FIELDS:
        if field in normalized and normalized[field] not in (None, ""):
            # ``bool`` is an ``int`` subclass in Python. Preserve it so the
            # validators can reject it instead of converting False to 0.0.
            if isinstance(normalized[field], bool):
                continue
            try:
                candidate = float(normalized[field])
            except (TypeError, ValueError):
                # Preserve invalid evidence so the Analyst can reject it explicitly.
                continue
            if math.isfinite(candidate):
                normalized[field] = candidate
    if "source_conflict" in normalized:
        normalized["source_conflict"] = parse_bool(normalized["source_conflict"])
    return normalized


def load_funds(path: str | Path = MOCK_PATH) -> list[dict[str, Any]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [normalize_record(row) for row in csv.DictReader(handle)]


def lookup_fund_reference(
    ticker: str, path: str | Path = REFERENCE_PATH
) -> dict[str, Any] | None:
    target = ticker.strip().upper()
    for record in load_funds(path):
        if str(record.get("ticker", "")).upper() == target:
            return record
    return None


def tool_trace(
    agent: str,
    tool: str,
    inputs: dict[str, Any],
    output_summary: str,
    status: str = "SUCCESS",
) -> dict[str, Any]:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "tool": tool,
        "inputs": inputs,
        "status": status,
        "output_summary": output_summary,
    }


def analyze_breakpoints(
    *, principal: float, base_sales_load_pct: float, schedule: str | None
) -> dict[str, Any]:
    """Apply a synthetic ``threshold:load`` schedule to an investment amount.

    Example: ``250000:3.5;500000:2.5;1000000:1.5``. A production adapter would
    ingest and validate the actual prospectus schedule with effective dates.
    """
    if (
        not math.isfinite(principal)
        or principal < 0
        or not math.isfinite(base_sales_load_pct)
    ):
        return {
            "status": "INVALID_INPUT",
            "eligible_load_pct": 0.0,
            "upfront_savings": 0.0,
            "parsed_breakpoints": [],
        }
    if base_sales_load_pct <= 0:
        return {
            "status": "NOT_APPLICABLE_NO_LOAD",
            "eligible_load_pct": 0.0,
            "upfront_savings": 0.0,
            "parsed_breakpoints": [],
        }
    if not schedule or not str(schedule).strip():
        return {
            "status": "MISSING_EVIDENCE",
            "eligible_load_pct": base_sales_load_pct,
            "upfront_savings": 0.0,
            "parsed_breakpoints": [],
        }
    try:
        pairs = []
        for item in str(schedule).split(";"):
            threshold_text, rate_text = item.strip().split(":", 1)
            threshold, rate = float(threshold_text), float(rate_text)
            if (
                not math.isfinite(threshold)
                or not math.isfinite(rate)
                or threshold < 0
                or not 0 <= rate <= base_sales_load_pct
            ):
                raise ValueError
            pairs.append((threshold, rate))
        pairs.sort(key=lambda pair: pair[0])
    except (TypeError, ValueError):
        return {
            "status": "INVALID_SCHEDULE",
            "eligible_load_pct": base_sales_load_pct,
            "upfront_savings": 0.0,
            "parsed_breakpoints": [],
        }
    eligible = base_sales_load_pct
    for threshold, rate in pairs:
        if principal >= threshold:
            eligible = min(eligible, rate)
    return {
        "status": "VERIFIED",
        "eligible_load_pct": round(eligible, 4),
        "upfront_savings": round(
            principal * max(0.0, base_sales_load_pct - eligible) / 100, 2
        ),
        "parsed_breakpoints": [
            {"threshold": threshold, "load_pct": rate} for threshold, rate in pairs
        ],
    }


OFFICIAL_REFERENCES = {
    "SEC_FEES": {
        "title": "SEC Investor Bulletin: Mutual Fund Fees and Expenses",
        "url": "https://www.sec.gov/investor/alerts/ib_mutualfundfees.pdf",
        "use": "General fee and expense concepts; not a source for Fiducia's internal caps.",
    },
    "FINRA_2341": {
        "title": "FINRA Rule 2341 — Investment Company Securities",
        "url": "https://www.finra.org/rules-guidance/rulebooks/finra-rules/2341",
        "use": "Reference for sales charge and service/distribution fee controls; counsel validation required.",
    },
}
