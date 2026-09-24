"""Tests for Bedrock Converse tool-use loop."""
from unittest.mock import MagicMock, patch
from fiducia.llm import BedrockNarrativeEngine


def test_offline_mode_returns_fallback():
    engine = BedrockNarrativeEngine(mode="offline")
    result, meta = engine.explain(
        system_prompt="test", agent_name="analyst",
        facts={"outcome": "PASS"}, fallback="fallback text"
    )
    assert result == "fallback text"
    assert meta["provider"] == "deterministic-template"


def test_health_check_offline():
    engine = BedrockNarrativeEngine(mode="offline")
    assert engine.health_check() is False


def test_default_model_id():
    engine = BedrockNarrativeEngine(mode="offline")
    from fiducia.llm import DEFAULT_MODEL_ID
    # Should default to Sonnet 5, not Nova
    assert "nova" not in engine.model_id.lower()
    assert engine.model_id == DEFAULT_MODEL_ID


def test_build_converse_tools():
    engine = BedrockNarrativeEngine(mode="offline")
    tools = engine._build_converse_tools("analyst")
    assert len(tools) > 0
    # Each tool has a toolSpec
    for t in tools:
        assert "toolSpec" in t
        assert "name" in t["toolSpec"]
        assert "inputSchema" in t["toolSpec"]


def test_model_outcome_rejection(monkeypatch):
    """Model outcome that disagrees with deterministic outcome is rejected."""
    engine = BedrockNarrativeEngine(mode="bedrock")
    engine.model_id = "test-model"

    # Mock boto3 client to return a tool_use then end_turn
    mock_client = MagicMock()
    mock_client.converse.side_effect = [
        # First call: model requests a tool
        {
            "stopReason": "tool_use",
            "output": {"message": {"role": "assistant", "content": [
                {"toolUse": {"toolUseId": "id1", "name": "schema_validator", "input": {"query": "check"}}}
            ]}},
            "usage": {"inputTokens": 100, "outputTokens": 50},
            "ResponseMetadata": {"RequestId": "req-123"},
        },
        # Second call: model gives final answer with WRONG outcome
        {
            "stopReason": "end_turn",
            "output": {"message": {"role": "assistant", "content": [
                {"text": '{"outcome": "FAIL", "rationale": "wrong", "evidence_refs": []}'}
            ]}},
            "usage": {"inputTokens": 150, "outputTokens": 60},
            "ResponseMetadata": {"RequestId": "req-124"},
        },
    ]

    with patch("boto3.client", return_value=mock_client):
        result, meta = engine.explain(
            system_prompt="test", agent_name="analyst",
            facts={"outcome": "PASS", "missing_fields": [], "range_errors": [], "checks": []},
            fallback="fallback text",
            deterministic_outcome="PASS",  # deterministic says PASS
        )

    # Model said FAIL but deterministic says PASS -> flag should be set
    assert meta.get("model_outcome_rejected") is True or result == "fallback text" or "PASS" in result


def test_model_outcome_agreement(monkeypatch):
    """Model outcome that agrees with deterministic outcome is accepted."""
    engine = BedrockNarrativeEngine(mode="bedrock")
    engine.model_id = "test-model"

    mock_client = MagicMock()
    mock_client.converse.return_value = {
        "stopReason": "end_turn",
        "output": {"message": {"role": "assistant", "content": [
            {"text": '{"outcome": "PASS", "rationale": "all checks passed", "evidence_refs": ["schema_validator"]}'}
        ]}},
        "usage": {"inputTokens": 100, "outputTokens": 40},
        "ResponseMetadata": {"RequestId": "req-200"},
    }

    with patch("boto3.client", return_value=mock_client):
        result, meta = engine.explain(
            system_prompt="test", agent_name="analyst",
            facts={"outcome": "PASS", "missing_fields": []},
            fallback="fallback text",
            deterministic_outcome="PASS",
        )

    # Should NOT be rejected
    assert meta.get("model_outcome_rejected") is False


def test_bedrock_exception_returns_fallback(monkeypatch):
    """Any exception from Bedrock returns the fallback without raising."""
    engine = BedrockNarrativeEngine(mode="bedrock")
    engine.model_id = "test-model"

    mock_client = MagicMock()
    mock_client.converse.side_effect = RuntimeError("network error")

    with patch("boto3.client", return_value=mock_client):
        result, meta = engine.explain(
            system_prompt="test", agent_name="analyst",
            facts={"outcome": "PASS"},
            fallback="safe fallback",
        )

    assert result == "safe fallback"
    assert meta.get("fallback") is True
    assert meta.get("error_type") == "RuntimeError"
