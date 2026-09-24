"""Optional Bedrock narrative layer with safe offline fallback.

The model explains already-computed findings. It is never authorized to set a metric,
pass a rule, route a case, approve a fund, or write a human override.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-5-20271001:0"

# Map tool names to the deterministic_facts key whose value the tool should return
_TOOL_TO_FACT_KEY: dict[str, str] = {
    "schema_validator": "missing_fields",
    "range_validator": "range_errors",
    "freshness_calculator": "age_days",
    "fee_component_reconciler": "fee_delta_bps",
    "untrusted_content_scanner": "injection_markers",
    "reference_catalog_lookup": "missing_fields",
    "deterministic_policy_engine": "checks",
    "approved_regulatory_reference_index": "references",
    "evidence_citation": "outcome",
    "plan_policy_matcher": "checks",
    "risk_band_mapper": "checks",
    "lineup_overlap_checker": "checks",
    "category_benchmark_lookup": "projection",
    "fee_drag_calculator": "projection",
    "breakpoint_validator": "breakpoint_analysis",
    "finding_aggregator": "decisive_evidence",
    "deterministic_risk_scorer": "risk_score",
    "HITL_router": "needs_human",
    "audit_writer": "outcome",
}


class BedrockNarrativeEngine:
    def __init__(self, mode: str = "offline") -> None:
        self.mode = mode
        self.model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
        self.region = os.getenv("AWS_REGION", "us-east-1")

    @property
    def enabled(self) -> bool:
        return self.mode.lower() == "bedrock"

    def health_check(self) -> bool:
        """Try a minimal Converse call (1 token). Returns True on success, False on any failure."""
        if not self.enabled:
            return False
        try:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
                config=Config(
                    connect_timeout=3.0,
                    read_timeout=5.0,
                    retries={"max_attempts": 1, "mode": "standard"},
                ),
            )
            client.converse(
                modelId=self.model_id,
                messages=[{"role": "user", "content": [{"text": "ping"}]}],
                inferenceConfig={"maxTokens": 1},
            )
            return True
        except Exception:
            return False

    def _build_converse_tools(self, agent_name: str) -> list[dict]:
        """Build toolConfig.tools list from TOOL_SETS[agent_name]."""
        from .prompts import TOOL_SETS

        tool_list = TOOL_SETS.get(agent_name, [])
        tools = []
        for tool_name in tool_list:
            tools.append(
                {
                    "toolSpec": {
                        "name": tool_name,
                        "description": f"Deterministic {tool_name.replace('_', ' ')} tool for {agent_name} agent",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {"query": {"type": "string"}},
                                "required": ["query"],
                            }
                        },
                    }
                }
            )
        return tools

    def converse_agent_loop(
        self,
        *,
        system_prompt: str,
        agent_name: str,
        deterministic_facts: dict[str, Any],
        deterministic_outcome: str | None,
        fallback: str,
    ) -> tuple[str, dict[str, Any]]:
        """
        Run a Bedrock Converse tool-use loop up to 6 turns.
        Returns (narrative_text, metadata_dict).
        """
        try:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
                config=Config(
                    connect_timeout=float(os.getenv("BEDROCK_CONNECT_TIMEOUT_SECONDS", "3")),
                    read_timeout=float(os.getenv("BEDROCK_READ_TIMEOUT_SECONDS", "30")),
                    retries={"max_attempts": 2, "mode": "standard"},
                ),
            )

            tools = self._build_converse_tools(agent_name)
            tool_names_ordered = [t["toolSpec"]["name"] for t in tools]

            user_content = (
                f"Agent: {agent_name}\n"
                "Here are the deterministic findings computed by the policy engine. "
                "Call the tools listed in the toolConfig in order to verify the analysis, "
                "then return a final JSON object with keys: "
                '{"outcome": "...", "rationale": "...", "evidence_refs": [...]}.\n'
                "Do not alter or contradict the deterministic outcomes.\n"
                + json.dumps(deterministic_facts, default=str)
            )

            messages: list[dict] = [
                {"role": "user", "content": [{"text": user_content}]}
            ]

            tool_config: dict[str, Any] = {"tools": tools} if tools else {}

            converse_kwargs: dict[str, Any] = {
                "modelId": self.model_id,
                "system": [{"text": system_prompt}],
                "messages": messages,
                "inferenceConfig": {"temperature": 0.0, "maxTokens": 512},
            }
            if tool_config:
                converse_kwargs["toolConfig"] = tool_config

            guardrail_id = os.getenv("BEDROCK_GUARDRAIL_ID")
            guardrail_version = os.getenv("BEDROCK_GUARDRAIL_VERSION")
            if guardrail_id and guardrail_version:
                converse_kwargs["guardrailConfig"] = {
                    "guardrailIdentifier": guardrail_id,
                    "guardrailVersion": guardrail_version,
                    "trace": "enabled",
                }

            tools_called: list[str] = []
            total_input_tokens = 0
            total_output_tokens = 0
            last_request_id = None
            last_stop_reason = None
            final_text = ""
            final_outcome = None
            final_rationale = None
            final_evidence_refs: list = []
            t0 = time.time()

            for _turn in range(6):
                response = client.converse(**converse_kwargs)
                stop_reason = response.get("stopReason", "")
                last_stop_reason = stop_reason
                usage = response.get("usage", {})
                total_input_tokens += usage.get("inputTokens", 0)
                total_output_tokens += usage.get("outputTokens", 0)
                last_request_id = response.get("ResponseMetadata", {}).get("RequestId")

                assistant_message = response["output"]["message"]
                # Append assistant message to conversation
                messages.append(assistant_message)

                if stop_reason == "tool_use":
                    # Collect tool_use blocks
                    tool_results_content: list[dict] = []
                    for block in assistant_message.get("content", []):
                        if "toolUse" in block:
                            tool_use = block["toolUse"]
                            tool_use_id = tool_use["toolUseId"]
                            tool_name = tool_use["name"]
                            tools_called.append(tool_name)

                            # Look up pre-computed value from deterministic_facts
                            fact_key = _TOOL_TO_FACT_KEY.get(tool_name)
                            fact_value = deterministic_facts.get(fact_key) if fact_key else None

                            tool_results_content.append(
                                {
                                    "toolResult": {
                                        "toolUseId": tool_use_id,
                                        "content": [
                                            {
                                                "text": json.dumps(fact_value, default=str)
                                            }
                                        ],
                                    }
                                }
                            )

                    # Add user message with tool results
                    messages.append(
                        {"role": "user", "content": tool_results_content}
                    )
                    converse_kwargs["messages"] = messages
                    continue

                elif stop_reason == "end_turn":
                    # Parse final text content as JSON
                    for block in assistant_message.get("content", []):
                        if "text" in block:
                            final_text = block["text"].strip()
                            break
                    # Try to parse JSON response
                    try:
                        parsed = json.loads(final_text)
                        final_outcome = str(parsed.get("outcome", "")).strip()
                        final_rationale = str(parsed.get("rationale", "")).strip()
                        final_evidence_refs = parsed.get("evidence_refs", [])
                    except (json.JSONDecodeError, AttributeError):
                        # Model didn't return valid JSON — use raw text as rationale
                        final_rationale = final_text
                        final_outcome = None
                    break
                else:
                    # Unexpected stop reason — break
                    break

            latency_ms = round((time.time() - t0) * 1000, 1)

            # Compute skipped tools
            model_skipped_tools = [t for t in tool_names_ordered if t not in tools_called]

            # Validate model outcome vs deterministic
            model_outcome_rejected = False
            if deterministic_outcome and final_outcome:
                if final_outcome.upper() != deterministic_outcome.upper():
                    model_outcome_rejected = True

            # Build narrative text
            narrative = final_rationale or fallback

            meta: dict[str, Any] = {
                "provider": "amazon-bedrock-converse",
                "model_id": self.model_id,
                "request_id": last_request_id,
                "latency_ms": latency_ms,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "stop_reason": last_stop_reason,
                "tool_use_count": len(tools_called),
                "tools_called": tools_called,
                "model_skipped_tools": model_skipped_tools,
                "model_outcome_rejected": model_outcome_rejected,
                "fallback": not bool(narrative and narrative != fallback),
            }

            return narrative or fallback, meta

        except Exception as exc:
            return fallback, {
                "provider": "deterministic-template",
                "fallback": True,
                "error_type": type(exc).__name__,
            }

    def explain(
        self,
        *,
        system_prompt: str,
        agent_name: str,
        facts: dict[str, Any],
        fallback: str,
        deterministic_outcome: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        if not self.enabled:
            return fallback, {
                "provider": "deterministic-template",
                "model_id": None,
                "fallback": False,
            }
        return self.converse_agent_loop(
            system_prompt=system_prompt,
            agent_name=agent_name,
            deterministic_facts=facts,
            deterministic_outcome=deterministic_outcome,
            fallback=fallback,
        )
