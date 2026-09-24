"""Amazon Bedrock AgentCore Runtime entrypoint.

Install the optional ``bedrock-agentcore`` extra before deploying. The core demo does
not require AWS credentials and uses the same graph locally.

Accepts either:
  {"scenario": "TICKER"}           -- loads a seeded demo fund by ticker
  {"fund": {...}, ...}             -- full fund payload (with optional plan_profile, model_mode)

Returns:
  {recommendation, human_reasons, metrics, spans, audit_entries}

Optional env vars:
  FIDUCIA_AUDIT_S3_BUCKET  -- if set, writes the audit JSONL to S3 (us-east-1)
  AGENTCORE_ENDPOINT       -- if set, the UI shows an AgentCore mode toggle
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fiducia.workflow import run_workflow
from fiducia.validation import PayloadValidationError, validate_api_payload

try:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp
except ImportError:  # Keeps local imports/test discovery safe.
    BedrockAgentCoreApp = None  # type: ignore[assignment,misc]


def _load_seeded_fund(ticker: str) -> dict | None:
    """Load a seeded demo fund by ticker from the mock catalog."""
    from fiducia.tools import load_funds
    for fund in load_funds():
        if str(fund.get("ticker", "")).upper() == ticker.upper():
            return fund
    return None


def _write_audit_to_s3(audit_path: str, trace_id: str, bucket: str) -> None:
    """Optionally write audit JSONL to S3 us-east-1 if bucket is configured."""
    try:
        import boto3
        s3 = boto3.client("s3", region_name="us-east-1")
        key = f"fiducia-audit/trace-{trace_id}.jsonl"
        with open(audit_path, "rb") as f:
            s3.put_object(Bucket=bucket, Key=key, Body=f.read(),
                          ContentType="application/x-ndjson")
    except Exception:
        pass  # S3 write is best-effort; never fails the response


def _handle_request(payload: dict) -> dict:
    """Core handler: accepts scenario ticker or full fund payload."""
    # Scenario shortcut
    if "scenario" in payload:
        ticker = str(payload["scenario"]).upper()
        fund = _load_seeded_fund(ticker)
        if fund is None:
            return {"error": "SCENARIO_NOT_FOUND", "details": f"No seeded fund for ticker {ticker}"}
        plan_profile = payload.get("plan_profile")
        model_mode = payload.get("model_mode", "offline")
    else:
        try:
            fund, plan_profile, model_mode = validate_api_payload(payload)
        except PayloadValidationError as exc:
            return {"error": "REQUEST_VALIDATION_FAILED", "details": exc.errors}

    result = run_workflow(fund, plan_profile=plan_profile, model_mode=model_mode)

    # Optional S3 audit write
    audit_bucket = os.getenv("FIDUCIA_AUDIT_S3_BUCKET")
    if audit_bucket and result.get("audit_path"):
        _write_audit_to_s3(result["audit_path"], result["trace_id"], audit_bucket)

    # Read audit entries
    audit_entries: list[dict] = []
    audit_path = result.get("audit_path", "")
    if audit_path:
        try:
            p = Path(audit_path)
            if p.exists():
                audit_entries = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception:
            pass

    return {
        "trace_id": result["trace_id"],
        "status": result["status"],
        "recommendation": result["recommendation"],
        "risk_score": result["risk_score"],
        "confidence": result["confidence"],
        "needs_human": result["needs_human"],
        "human_reasons": result["human_reasons"],
        "agent_results": result["agent_results"],
        "metrics": result.get("run_metrics", {}),
        "spans": result.get("spans", []),
        "audit_entries": audit_entries,
    }


if BedrockAgentCoreApp:
    from starlette.responses import JSONResponse

    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke(payload, context):
        result = _handle_request(payload)
        if "error" in result:
            status_code = 404 if result["error"] == "SCENARIO_NOT_FOUND" else 422
            return JSONResponse(result, status_code=status_code)
        return result


if __name__ == "__main__":
    if not BedrockAgentCoreApp:
        raise SystemExit("Install bedrock-agentcore to run the AgentCore entrypoint")
    app.run()
