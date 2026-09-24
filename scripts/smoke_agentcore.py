"""Exercise the AgentCore SDK adapter locally without AWS credentials."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient

from agentcore_app import app  # noqa: E402
from fiducia.tools import load_funds  # noqa: E402


def main() -> None:
    if app is None:
        raise SystemExit("Install requirements-aws.txt before running this smoke check")

    fund = next(row for row in load_funds() if row["ticker"] == "SUNX")
    invalid = dict(fund)
    invalid["expense_ratio"] = False

    with TestClient(app) as client:
        rejected = client.post(
            "/invocations", json={"fund": invalid, "model_mode": "offline"}
        )
        accepted = client.post(
            "/invocations", json={"fund": fund, "model_mode": "offline"}
        )

    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["error"] == "REQUEST_VALIDATION_FAILED"
    assert accepted.status_code == 200, accepted.text
    result = accepted.json()
    assert result["status"] == "COMPLETED"
    assert result["recommendation"] == "APPROVE"
    print(
        json.dumps(
            {
                "invalid_status": rejected.status_code,
                "valid_status": accepted.status_code,
                "recommendation": result["recommendation"],
                "trace_id": result["trace_id"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
