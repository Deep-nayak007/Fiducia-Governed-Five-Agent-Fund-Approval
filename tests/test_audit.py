import json
import hashlib

from fiducia.audit import AuditLogger


def test_hash_chain_verifies_and_detects_tamper(tmp_path):
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path, signing_key="unit-test-key")
    logger.append(trace_id="t1", event_type="START", actor="test", payload={"x": 1})
    logger.append(trace_id="t1", event_type="END", actor="test", payload={"decision": "APPROVE"})
    assert logger.verify() == (True, [])

    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["payload"]["x"] = 999
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    valid, errors = logger.verify()
    assert valid is False
    assert any("hash mismatch" in error for error in errors)


def test_signed_mode_rejects_stripped_signature(tmp_path):
    path = tmp_path / "signed.jsonl"
    logger = AuditLogger(path, signing_key="unit-test-key")
    logger.append(trace_id="t2", event_type="START", actor="test", payload={})
    record = json.loads(path.read_text(encoding="utf-8"))
    record.pop("hmac_sha256")
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    valid, errors = logger.verify()
    assert valid is False
    assert any("required HMAC is missing" in error for error in errors)


def test_nonfinite_values_are_encoded_as_valid_explicit_json(tmp_path):
    path = tmp_path / "nonfinite.jsonl"
    logger = AuditLogger(path)
    logger.append(
        trace_id="t3",
        event_type="INVALID_INPUT",
        actor="test",
        payload={"nan": float("nan"), "positive_inf": float("inf")},
    )

    def reject_constant(value):
        raise AssertionError(f"non-standard JSON constant emitted: {value}")

    record = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    assert record["payload"]["nan"] == {"invalid_numeric": "NaN"}
    assert record["payload"]["positive_inf"] == {"invalid_numeric": "Infinity"}
    assert logger.verify() == (True, [])


def test_schema_1_0_nonfinite_trace_remains_backward_verifiable(tmp_path):
    path = tmp_path / "legacy-nonfinite.jsonl"
    legacy = {
        "schema_version": "1.0",
        "sequence": 1,
        "timestamp_utc": "2026-09-23T00:00:00+00:00",
        "trace_id": "legacy",
        "event_type": "INVALID_INPUT",
        "actor": "test",
        "payload": {"nan": float("nan")},
        "previous_hash": "0" * 64,
    }
    canonical = json.dumps(
        legacy, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    legacy["event_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    path.write_text(
        json.dumps(legacy, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    assert AuditLogger(path).verify() == (True, [])
