"""Amazon Bedrock AgentCore Runtime entrypoint.

Install the optional ``bedrock-agentcore`` extra before deploying. The core demo does
not require AWS credentials and uses the same graph locally.
"""

from __future__ import annotations

from fiducia.workflow import run_workflow
from fiducia.validation import PayloadValidationError, validate_api_payload

try:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp
except ImportError:  # Keeps local imports/test discovery safe.
    BedrockAgentCoreApp = None


if BedrockAgentCoreApp:
    from starlette.responses import JSONResponse

    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke(payload, context):
        try:
            fund, plan_profile, model_mode = validate_api_payload(payload)
        except PayloadValidationError as exc:
            return JSONResponse(
                {
                    "error": "REQUEST_VALIDATION_FAILED",
                    "details": exc.errors,
                },
                status_code=422,
            )
        result = run_workflow(
            fund,
            plan_profile=plan_profile,
            model_mode=model_mode,
        )
        return {
            "trace_id": result["trace_id"],
            "status": result["status"],
            "recommendation": result["recommendation"],
            "risk_score": result["risk_score"],
            "confidence": result["confidence"],
            "needs_human": result["needs_human"],
            "human_reasons": result["human_reasons"],
            "agent_results": result["agent_results"],
        }


if __name__ == "__main__":
    if not BedrockAgentCoreApp:
        raise SystemExit("Install bedrock-agentcore to run the AgentCore entrypoint")
    app.run()
