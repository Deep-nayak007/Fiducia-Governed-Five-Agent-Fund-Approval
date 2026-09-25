"""Fiducia AgentCore entrypoint.

Accepts either {"scenario": "TICKER"} or a full fund payload, or a free-text
{"prompt": "..."} that is routed through the Strands natural-language router.
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

_NL_ROUTER_SYSTEM = """You are Fiducia, an AI assistant for the governed fund-approval platform.
When a user asks about a fund or requests a fund approval, call run_fund_approval with the
appropriate ticker or fund details. For general questions, answer directly.
Never invent approval outcomes — only run_fund_approval produces authoritative results."""


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


def _build_nl_router(model_mode: str) -> Any:
    """Build a Strands Agent with the run_fund_approval tool."""
    try:
        from strands import Agent, tool
        from strands.models import BedrockModel

        @tool
        def run_fund_approval(ticker: str) -> dict:
            """Run the Fiducia governed approval workflow for a fund by its ticker symbol.

            Args:
                ticker: The fund ticker symbol (e.g. SUNX, DATA, SPECX).

            Returns:
                Approval result with recommendation, risk_score, needs_human, and summary.
            """
            fund = _get_funds().get(ticker.strip().upper())
            if fund is None:
                return {"error": f"Unknown ticker: {ticker}"}
            state = run_workflow(fund, model_mode=model_mode)
            return {
                "ticker": ticker.upper(),
                "recommendation": state["recommendation"],
                "risk_score": state["risk_score"],
                "confidence": state["confidence"],
                "needs_human": state["needs_human"],
                "human_reasons": state["human_reasons"],
                "final_summary": state["final_summary"],
                "retries": state["retries"],
                "status": state["status"],
            }

        model_id = "us.anthropic.claude-sonnet-5"
        bedrock_model = BedrockModel(model_id=model_id, region_name="us-east-1")
        return Agent(
            model=bedrock_model,
            system_prompt=_NL_ROUTER_SYSTEM,
            tools=[run_fund_approval],
        )
    except Exception as exc:
        log.warning("Strands router unavailable: %s", exc)
        return None


@app.entrypoint
async def invoke(payload: dict[str, Any], context: Any):
    log.info("Fiducia AgentCore invoke: %s", list(payload.keys()))

    model_mode = str(payload.get("model_mode", os.environ.get("BEDROCK_MODEL_ID", "") and "bedrock" or "offline"))
    plan_profile = payload.get("plan_profile") or {"plan_id": "ASU-DEMO-401A", "max_risk_score": 7}

    # Natural-language routing via Strands
    if "prompt" in payload:
        prompt = str(payload["prompt"]).strip()
        router = _build_nl_router(model_mode)
        if router is None:
            yield {"error": "Strands router unavailable; provide scenario or fund payload instead"}
            return
        try:
            response = router(prompt)
            yield {"nl_response": str(response), "routed_via": "strands"}
        except Exception as exc:
            log.error("Strands router error: %s", exc)
            yield {"error": f"Router error: {exc}"}
        return

    # Structured fund payload routing
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
        yield {"error": "Payload must contain 'prompt', 'scenario', 'fund', or a direct fund dict with 'ticker'"}
        return

    state = run_workflow(fund, plan_profile=plan_profile, model_mode=model_mode)

    spans_sample = state.get("spans", [])[:50]

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
