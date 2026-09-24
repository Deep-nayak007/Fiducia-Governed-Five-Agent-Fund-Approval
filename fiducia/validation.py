"""Fail-closed request and case-input validation.

Business-level missing data may enter the graph for bounded repair; malformed
types do not get silently coerced into valid financial values.
"""

from __future__ import annotations

import math
import re
from typing import Any


NUMERIC_INPUT_FIELDS = {
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

TEXT_INPUT_FIELDS = {
    "ticker",
    "fund_name",
    "fund_type",
    "asset_class",
    "regulatory_status",
    "as_of_date",
    "evidence_note",
    "breakpoint_schedule",
}

ALLOWED_FUND_FIELDS = NUMERIC_INPUT_FIELDS | TEXT_INPUT_FIELDS | {"source_conflict"}
IDENTITY_FIELDS = ("ticker", "fund_name", "fund_type", "asset_class")
TICKER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,14}$")


class PayloadValidationError(ValueError):
    """Raised when an external request does not satisfy the public contract."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_fund_values(
    fund: Any,
    *,
    strict_numeric_types: bool = False,
    reject_unknown_fields: bool = False,
) -> list[str]:
    """Return schema errors without mutating the submitted evidence."""

    if not isinstance(fund, dict):
        return ["fund must be an object"]

    errors: list[str] = []
    if reject_unknown_fields:
        unknown = sorted(str(key) for key in set(fund) - ALLOWED_FUND_FIELDS)
        if unknown:
            errors.append(f"fund contains unsupported field(s): {', '.join(unknown)}")

    for field in TEXT_INPUT_FIELDS:
        if field not in fund or fund[field] in (None, ""):
            continue
        if not isinstance(fund[field], str):
            errors.append(f"fund.{field} must be a string")

    ticker = fund.get("ticker")
    if isinstance(ticker, str) and ticker and not TICKER_PATTERN.fullmatch(ticker.strip()):
        errors.append("fund.ticker must be 1-15 letters, numbers, dots, or hyphens")
    fund_name = fund.get("fund_name")
    if isinstance(fund_name, str) and len(fund_name.strip()) > 200:
        errors.append("fund.fund_name must be at most 200 characters")

    for field in NUMERIC_INPUT_FIELDS:
        if field not in fund or fund[field] in (None, ""):
            continue
        value = fund[field]
        if isinstance(value, bool):
            errors.append(f"fund.{field} must be a number, not a boolean")
            continue
        if strict_numeric_types and not isinstance(value, (int, float)):
            errors.append(f"fund.{field} must be a JSON number or null")
            continue
        try:
            observed = float(value)
        except (TypeError, ValueError):
            errors.append(f"fund.{field} must be a finite number")
            continue
        if not math.isfinite(observed):
            errors.append(f"fund.{field} must be a finite number")

    if "source_conflict" in fund and not isinstance(fund["source_conflict"], bool):
        if strict_numeric_types or str(fund["source_conflict"]).strip().lower() not in {
            "true",
            "false",
            "1",
            "0",
            "yes",
            "no",
            "y",
            "n",
        }:
            errors.append("fund.source_conflict must be a boolean")
    return list(dict.fromkeys(errors))


def validate_plan_values(
    plan_profile: Any,
    *,
    allowed_asset_classes: set[str] | None = None,
    require_identity: bool = True,
) -> list[str]:
    """Validate the plan scope independently of fund suitability decisions."""

    if not isinstance(plan_profile, dict):
        return ["plan_profile must be an object"]

    errors: list[str] = []
    plan_id = plan_profile.get("plan_id")
    if require_identity and (not isinstance(plan_id, str) or not plan_id.strip()):
        errors.append("plan_profile.plan_id must be a non-empty string")

    risk = plan_profile.get("max_risk_score")
    if isinstance(risk, bool) or not isinstance(risk, (int, float)):
        errors.append("plan_profile.max_risk_score must be a number from 1 to 10")
    elif not math.isfinite(float(risk)) or not 1 <= float(risk) <= 10:
        errors.append("plan_profile.max_risk_score must be a number from 1 to 10")

    if "allowed_asset_classes" in plan_profile:
        assets = plan_profile["allowed_asset_classes"]
        if not isinstance(assets, list) or not assets:
            errors.append("plan_profile.allowed_asset_classes must be a non-empty list")
        elif any(not isinstance(asset, str) or not asset.strip() for asset in assets):
            errors.append("plan_profile.allowed_asset_classes must contain strings")
        elif allowed_asset_classes is not None and any(
            asset not in allowed_asset_classes for asset in assets
        ):
            errors.append("plan_profile contains an unknown allowed asset class")

    if "current_lineup" in plan_profile:
        lineup = plan_profile["current_lineup"]
        if not isinstance(lineup, list) or any(
            not isinstance(ticker, str) or not ticker.strip() for ticker in lineup
        ):
            errors.append("plan_profile.current_lineup must be a list of ticker strings")
    return list(dict.fromkeys(errors))


def validate_api_payload(payload: Any) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
    """Validate and unpack the strict external AgentCore request envelope."""

    if not isinstance(payload, dict):
        raise PayloadValidationError(["request body must be an object"])
    unknown_envelope_fields = sorted(
        str(key) for key in set(payload) - {"fund", "plan_profile", "model_mode"}
    )
    fund = payload.get("fund")
    errors = validate_fund_values(
        fund, strict_numeric_types=True, reject_unknown_fields=True
    )
    if unknown_envelope_fields:
        errors.append(
            "request contains unsupported field(s): "
            + ", ".join(unknown_envelope_fields)
        )
    if isinstance(fund, dict):
        for field in IDENTITY_FIELDS:
            value = fund.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"fund.{field} is required and must be a non-empty string")

    supplied_plan = "plan_profile" in payload
    plan_profile = payload.get("plan_profile")
    if supplied_plan:
        errors.extend(validate_plan_values(plan_profile))

    model_mode = payload.get("model_mode", "bedrock")
    if model_mode not in {"offline", "bedrock"}:
        errors.append("model_mode must be 'offline' or 'bedrock'")
    if errors:
        raise PayloadValidationError(list(dict.fromkeys(errors)))
    return fund, plan_profile, model_mode


# Documentation-friendly public request shape. Runtime validation above adds
# finite-number and cross-field checks that JSON Schema alone cannot express.
AGENTCORE_REQUEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["fund"],
    "additionalProperties": False,
    "properties": {
        "fund": {"type": "object"},
        "plan_profile": {"type": "object"},
        "model_mode": {"enum": ["offline", "bedrock"]},
    },
}
