"""Fiducia AgentCore entrypoint.

Accepts either {"scenario": "TICKER"} or a full fund payload, runs the existing
LangGraph workflow, and returns recommendation, human_reasons, metrics, and spans.
Credentials come from the runtime IAM role — never embedded here.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

# fiducia/, config/, and data/ are bundled alongside this file
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from fiducia.tools import load_funds
from fiducia.workflow import run_workflow

app = BedrockAgentCoreApp()
log = app.logger

_FUNDS_BY_TICKER: dict[str, dict[str, Any]] = {}


def _get_funds() -> dict[str, dict[str, Any]]:
    global _FUNDS_BY_TICKER
    if not _FUNDS_BY_TICKER:
        _FUNDS_BY_TICKER = {str(f["ticker"]): f for f in load_funds()}
    return _FUNDS_BY_TICKER


def _s3_write(trace_id: str, payload: dict[str, Any]) -> None:
    bucket = os.environ.get("FIDUCIA_AUDIT_S3_BUCKET", "").strip()
    if not bucket:
        return
    try:
        import boto3
        key = f"fiducia-audit/{trace_id}.json"
        boto3.client("s3", region_name="us-east-1").put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(payload, default=str).encode("utf-8"),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
        )
        log.info("Audit written to s3://%s/%s", bucket, key)
    except Exception as exc:
        log.warning("S3 audit write failed: %s", exc)


@app.entrypoint
async def invoke(payload: dict[str, Any], context: Any):
    log.info("Fiducia AgentCore invoke: %s", list(payload.keys()))

    # Resolve fund data
    if "scenario" in payload:
        ticker = str(payload["scenario"]).strip().upper()
        fund = _get_funds().get(ticker)
        if fund is None:
            yield {"error": f"Unknown scenario ticker: {ticker}"}
            return
    elif "fund" in payload:
        fund = payload["fund"]
    elif "ticker" in payload:
        fund = payload
    else:
        yield {"error": "Payload must contain 'scenario', 'fund', or a direct fund dict with 'ticker'"}
        return

    model_mode = str(payload.get("model_mode", os.environ.get("BEDROCK_MODEL_ID", "") and "bedrock" or "offline"))
    plan_profile = payload.get("plan_profile") or {"plan_id": "ASU-DEMO-401A", "max_risk_score": 7}

    state = run_workflow(fund, plan_profile=plan_profile, model_mode=model_mode)

    spans_sample = state.get("spans", [])[:50]  # cap response size

    result = {
        "trace_id": state["trace_id"],
        "recommendation": state["recommendation"],
        "risk_score": state["risk_score"],
        "confidence": state["confidence"],
        "needs_human": state["needs_human"],
        "human_reasons": state["human_reasons"],
        "final_summary": state["final_summary"],
        "retries": state["retries"],
        "metrics": state.get("run_metrics", {}),
        "spans": spans_sample,
        "handoffs": state.get("handoffs", []),
        "status": state["status"],
    }

    _s3_write(state["trace_id"], result)

    yield result


if __name__ == "__main__":
    app.run()
