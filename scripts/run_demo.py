#!/usr/bin/env python3
"""Run one or all deterministic demo scenarios from the command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fiducia.tools import load_funds  # noqa: E402
from fiducia.workflow import run_workflow  # noqa: E402


def summary(state: dict) -> dict:
    return {
        "trace_id": state["trace_id"],
        "ticker": state["fund"].get("ticker"),
        "status": state["status"],
        "recommendation": state["recommendation"],
        "risk_score": state["risk_score"],
        "confidence": state["confidence"],
        "retries": state["retries"],
        "missing_fields": state["missing_fields"],
        "needs_human": state["needs_human"],
        "human_reasons": state["human_reasons"],
        "audit_path": state["audit_path"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="SUNX", help="Ticker or 'all'")
    parser.add_argument("--model-mode", choices=["offline", "bedrock"], default="offline")
    args = parser.parse_args()
    funds = load_funds()
    selected = funds if args.scenario.lower() == "all" else [fund for fund in funds if fund["ticker"] == args.scenario.upper()]
    if not selected:
        parser.error(f"unknown scenario {args.scenario!r}")
    for fund in selected:
        state = run_workflow(fund, model_mode=args.model_mode)
        print(json.dumps(summary(state), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
