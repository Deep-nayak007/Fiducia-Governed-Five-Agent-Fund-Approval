"""Append-only, hash-chained JSON audit records.

The local file is tamper-evident rather than physically immutable. Production maps
the same records to versioned S3 with Object Lock (Compliance mode), KMS, and CloudTrail.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # POSIX in the demo/AWS runtime; tests still work without it on other platforms.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


GENESIS_HASH = "0" * 64


def _json_compatible(value: Any) -> Any:
    """Convert exceptional Python values into explicit, standards-safe evidence."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return {"invalid_numeric": "NaN"}
        if math.isinf(value):
            return {"invalid_numeric": "Infinity" if value > 0 else "-Infinity"}
        return value
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    if isinstance(value, set):
        items = [_json_compatible(item) for item in value]
        return sorted(
            items,
            key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False),
        )
    return {"non_json_type": type(value).__name__, "value": str(value)}


def _canonical(value: dict[str, Any]) -> str:
    return json.dumps(
        _json_compatible(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _legacy_canonical(value: dict[str, Any]) -> str:
    """Canonical form used by schema 1.0, including Python's NaN literals."""

    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _digest(record_without_hash: dict[str, Any]) -> str:
    serializer = (
        _legacy_canonical
        if record_without_hash.get("schema_version") == "1.0"
        else _canonical
    )
    return hashlib.sha256(serializer(record_without_hash).encode("utf-8")).hexdigest()


class AuditLogger:
    """Write and verify regulatory-style JSONL traces with a cryptographic hash chain."""

    def __init__(self, path: str | Path, signing_key: str | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.signing_key = signing_key or os.getenv("FIDUCIA_AUDIT_HMAC_KEY")

    def append(
        self,
        *,
        trace_id: str,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        with self.path.open("a+", encoding="utf-8") as handle:
            if fcntl:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            lines = [line for line in handle.read().splitlines() if line.strip()]
            previous = json.loads(lines[-1]) if lines else None
            record: dict[str, Any] = {
                "schema_version": "1.1",
                "sequence": int(previous["sequence"]) + 1 if previous else 1,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
                "event_type": event_type,
                "actor": actor,
                "payload": _json_compatible(payload),
                "previous_hash": previous["event_hash"] if previous else GENESIS_HASH,
            }
            if self.signing_key:
                record["hmac_key_id"] = os.getenv(
                    "FIDUCIA_AUDIT_HMAC_KEY_ID", "environment-managed-key"
                )
            record["event_hash"] = _digest(record)
            if self.signing_key:
                record["hmac_sha256"] = hmac.new(
                    self.signing_key.encode("utf-8"),
                    record["event_hash"].encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
            handle.seek(0, os.SEEK_END)
            handle.write(_canonical(record) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            if fcntl:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return record

    def verify(self) -> tuple[bool, list[str]]:
        if not self.path.exists():
            return True, []
        errors: list[str] = []
        previous_hash = GENESIS_HASH
        previous_sequence = 0
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    errors.append(f"line {line_number}: invalid JSON")
                    continue
                supplied_hash = record.pop("event_hash", None)
                supplied_hmac = record.pop("hmac_sha256", None)
                expected_hash = _digest(record)
                if supplied_hash != expected_hash:
                    errors.append(f"line {line_number}: event hash mismatch")
                if record.get("previous_hash") != previous_hash:
                    errors.append(f"line {line_number}: broken previous-hash link")
                if int(record.get("sequence", -1)) != previous_sequence + 1:
                    errors.append(f"line {line_number}: non-contiguous sequence")
                if self.signing_key:
                    if not supplied_hmac:
                        errors.append(f"line {line_number}: required HMAC is missing")
                    else:
                        expected_hmac = hmac.new(
                            self.signing_key.encode("utf-8"),
                            str(supplied_hash).encode("utf-8"),
                            hashlib.sha256,
                        ).hexdigest()
                        if not hmac.compare_digest(supplied_hmac, expected_hmac):
                            errors.append(f"line {line_number}: HMAC mismatch")
                elif supplied_hmac:
                    errors.append(
                        f"line {line_number}: HMAC present but verification key unavailable"
                    )
                previous_hash = supplied_hash or ""
                previous_sequence = int(record.get("sequence", 0))
        return not errors, errors


def immutable_audit_log(
    path: str | Path,
    trace_id: str,
    event_type: str,
    actor: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Convenience function requested by the challenge blueprint."""
    return AuditLogger(path).append(
        trace_id=trace_id,
        event_type=event_type,
        actor=actor,
        payload=payload,
    )
