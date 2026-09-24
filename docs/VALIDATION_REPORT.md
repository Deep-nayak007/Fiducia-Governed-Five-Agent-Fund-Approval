# Fiducia Validation Report

**Validation date:** 2026-09-24  
**Environment:** macOS 26.6.2 arm64, Python 3.14.4  
**Validated dependency path:** LangGraph 1.2.12, Streamlit 1.64.0, boto3 1.43.101, pandas 3.0.6, bedrock-agentcore 1.23.1

## Reproduced result

| Check | Result | Evidence boundary |
|---|---|---|
| Python compilation | Pass | `app.py`, `agentcore_app.py`, `fiducia/`, and `scripts/*.py` compiled without error |
| Automated unit/integration suite | **46 passed / 46 collected** | 4 audit, 10 ingress, 4 policy, and 28 workflow cases |
| Real LangGraph invocation | Pass | Installed LangGraph executed the workflow for all seeded cases; the no-LangGraph fallback also has a dedicated test |
| All 10 seeded scenarios | Pass with expected routes | Reproduced with deterministic/offline narrative mode |
| Streamlit process startup | Pass | Headless server started; root returned HTTP `200` |
| Streamlit health endpoint | Pass | `/_stcore/health` returned `ok` |
| Streamlit AppTest smoke | Pass | Initial render; SUNX, DATA, INJX, and SPECX submissions; and SPECX dialog open completed with zero app exceptions. The dialog exposed Reviewer ID, Second approver ID, attestation, and `Attest & record decision`. This is framework-level smoke coverage, not a real-browser or end-to-end identity/authentication test. |
| Audit integrity controls | Pass | Hash-chain tampering is detected; signed mode rejects a stripped HMAC |
| HITL state controls | Pass | Review-state precondition, required reason/attestation, distinct second ID for reject-to-approve, and no second final action |
| Strict external request validator | Pass | Tests cover boolean-as-number values, an unsupported envelope field, malformed plan objects, and invalid identity types; the same validator also rejects unsupported fund fields and invalid model mode |
| Local AgentCore SDK adapter smoke | Pass | With bedrock-agentcore 1.23.1 and Starlette TestClient, invalid boolean fee input returned HTTP `422`; valid offline SUNX returned HTTP `200`, `COMPLETED`, and `APPROVE`. This did not deploy to AWS or call Bedrock. |
| Regulatory-reference framing | Pass | Tests require `WITHIN_CONFIGURED_REFERENCE` and `regulatory_determination = NOT_MADE...`, never a legal `PASS` conclusion |

Commands reproduced:

```bash
.venv/bin/pytest -q
# 46 passed

.venv/bin/pytest --collect-only -q
# tests/test_audit.py: 4
# tests/test_ingress.py: 10
# tests/test_policy.py: 4
# tests/test_workflow.py: 28

.venv/bin/python -m compileall -q app.py agentcore_app.py fiducia scripts
.venv/bin/python scripts/run_demo.py --scenario all
.venv/bin/python scripts/smoke_agentcore.py
# invalid_status=422; valid_status=200; recommendation=APPROVE
```

## Seeded outcome matrix

| Ticker | Purpose | Observed recommendation | Human? | Observed status |
|---|---|---|---:|---|
| SUNX | Clean, low-cost index fund | `APPROVE` | No | `COMPLETED` |
| AZQ | Low-cost ETF with peer-cost warning | `APPROVE_WITH_CONDITIONS` | Yes | `AWAITING_HUMAN_REVIEW` |
| RET2045 | Target-date fund with peer-cost warning | `APPROVE_WITH_CONDITIONS` | Yes | `AWAITING_HUMAN_REVIEW` |
| ALPHX | Internal fee-cap exception | `ESCALATE` | Yes | `AWAITING_HUMAN_REVIEW` |
| NEWB | Insufficient track record | `ESCALATE` | Yes | `AWAITING_HUMAN_REVIEW` |
| SPECX | Status, suitability, and cost hard stops | `REJECT` recommendation | Yes | `AWAITING_HUMAN_REVIEW` |
| DATA | Missing Sharpe ratio | Repair once, then `APPROVE_WITH_CONDITIONS` | Yes | `AWAITING_HUMAN_REVIEW` |
| CONFX | Conflicting source flag and fee-boundary condition | `ESCALATE` | Yes | `AWAITING_HUMAN_REVIEW` |
| INJX | Injection keywords in evidence note | `ESCALATE` | Yes | `AWAITING_HUMAN_REVIEW` |
| BLANK | Fee evidence absent from approved synthetic sources | Retry `2/2`, then `ESCALATE` | Yes | `AWAITING_HUMAN_REVIEW` |

## What the automated suite proves

- Missing values remain distinct from numeric zero; `sales_load_pct` is required evidence and is not silently defaulted to a no-load value.
- Nonnumeric, boolean, NaN, infinite, out-of-range, and future-dated decision inputs fail closed; evidence older than the 120-day demo threshold produces `APPROVE_WITH_CONDITIONS` and mandatory human review.
- The first audit record preserves raw and normalized fund/plan snapshots plus ingress errors.
- New schema `1.1` audit records serialize NaN and infinity into explicit standards-compliant JSON evidence objects rather than non-standard numeric constants; the verifier remains backward-compatible with legacy schema `1.0` traces.
- Malformed explicit plans cannot fall back to permissive demo defaults; malformed identity fields and unknown/blocked product types cannot auto-approve.
- A total 12b-1 fee differing from distribution plus service components by more than `1 bp` escalates, and a fund within `5 bps` of its configured expense cap requires a human.
- Breakpoint calculations are deterministic, but absent or invalid load evidence is not assumed away; any positive front-end load routes to human review under the demo policy.
- Reference-catalog repair requires ticker plus matching fund name, product type, and asset class.
- Optional model prose cannot replace the deterministic decision summary.
- Local audit edits are detected, and configuring an HMAC key makes a missing/stripped signature a verification failure.

## Explicitly not validated locally

- Live inference against the hackathon AWS account; no event-account credentials were available in this workspace.
- Bedrock Guardrail IDs, IAM policies, VPC endpoints, AgentCore CLI/runtime deployment, or the entrypoint behind an AWS-managed network endpoint. The SDK adapter was exercised only in-process with Starlette TestClient.
- Authenticated reviewer identity, SSO/RBAC, step-up authentication, or real maker-checker separation. The prototype uses free-text IDs and a checkbox attestation.
- Durable LangGraph checkpoints/interrupts, idempotent callbacks, SQS/EventBridge fan-out, DynamoDB state, replay, or regional recovery. The local graph is in-process and specialist nodes are serial.
- Document upload/OCR, malware scanning, field-level source spans, citation grounding, signed/effective-dated rule bundles, or automated rule-conflict precedence.
- S3 Object Lock/KMS/CloudTrail production immutability. Local JSONL is tamper-evident and optionally HMAC-authenticated, but it is not WORM storage.
- Production load, latency SLOs, chaos/disaster recovery, legal applicability, model-risk approval, privacy/tenant isolation, or accessibility certification.
- Docker image build, because Docker is not installed in this environment; the Dockerfile remains a deployment artifact.

These are deployment gates, not assumed capabilities. The offline demonstration remains functional without AWS access; Bedrock is optional narrative generation and cannot change deterministic policy, risk, or routing results.
