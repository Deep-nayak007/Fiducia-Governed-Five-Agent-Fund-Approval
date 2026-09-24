"""Optional Bedrock narrative layer with safe offline fallback.

The model explains already-computed findings. It is never authorized to set a metric,
pass a rule, route a case, approve a fund, or write a human override.
"""

from __future__ import annotations

import json
import os
from typing import Any


class BedrockNarrativeEngine:
    def __init__(self, mode: str = "offline") -> None:
        self.mode = mode
        self.model_id = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
        self.region = os.getenv("AWS_REGION", "us-east-1")

    @property
    def enabled(self) -> bool:
        return self.mode.lower() == "bedrock"

    def explain(
        self,
        *,
        system_prompt: str,
        agent_name: str,
        facts: dict[str, Any],
        fallback: str,
    ) -> tuple[str, dict[str, Any]]:
        if not self.enabled:
            return fallback, {"provider": "deterministic-template", "model_id": None, "fallback": False}
        try:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
                config=Config(
                    connect_timeout=float(os.getenv("BEDROCK_CONNECT_TIMEOUT_SECONDS", "3")),
                    read_timeout=float(os.getenv("BEDROCK_READ_TIMEOUT_SECONDS", "8")),
                    retries={"max_attempts": 2, "mode": "standard"},
                ),
            )
            expected_outcome = str(
                facts.get("recommendation") or facts.get("outcome") or ""
            ).strip()
            required_marker = f"[OUTCOME:{expected_outcome}]" if expected_outcome else ""
            request: dict[str, Any] = {
                "modelId": self.model_id,
                "system": [{"text": system_prompt}],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": (
                                    f"Agent: {agent_name}\n"
                                    "Write at most 90 words explaining these deterministic findings. "
                                    "Do not add facts or change outcomes. "
                                    + (
                                        f"Begin exactly with {required_marker}.\n"
                                        if required_marker
                                        else "\n"
                                    )
                                    + json.dumps(facts, sort_keys=True, default=str)
                                )
                            }
                        ],
                    }
                ],
                "inferenceConfig": {"temperature": 0.0, "maxTokens": 220},
            }
            guardrail_id = os.getenv("BEDROCK_GUARDRAIL_ID")
            guardrail_version = os.getenv("BEDROCK_GUARDRAIL_VERSION")
            if guardrail_id and guardrail_version:
                request["guardrailConfig"] = {
                    "guardrailIdentifier": guardrail_id,
                    "guardrailVersion": guardrail_version,
                    "trace": "enabled",
                }
            response = client.converse(**request)
            text = "".join(
                item.get("text", "")
                for item in response["output"]["message"]["content"]
                if "text" in item
            ).strip()
            outcome_validated = not required_marker or text.casefold().startswith(
                required_marker.casefold()
            )
            if text and not outcome_validated:
                return fallback, {
                    "provider": "deterministic-template",
                    "model_id": self.model_id,
                    "fallback": True,
                    "validation_failure": "required outcome marker absent or misplaced",
                    "request_id": response.get("ResponseMetadata", {}).get("RequestId"),
                }
            display_text = text[len(required_marker) :].lstrip(" .:\n-") if required_marker else text
            return display_text or fallback, {
                "provider": "amazon-bedrock-converse",
                "model_id": self.model_id,
                "fallback": not bool(text),
                "outcome_token_validated": outcome_validated,
                "request_id": response.get("ResponseMetadata", {}).get("RequestId"),
            }
        except Exception as exc:  # Demo must remain available if credentials/network fail.
            return fallback, {
                "provider": "deterministic-template",
                "model_id": self.model_id,
                "fallback": True,
                "error_type": type(exc).__name__,
            }
