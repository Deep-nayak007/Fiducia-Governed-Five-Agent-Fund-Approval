# Fiducia — Hackathon Submission Blueprint

## Executive summary

**One-liner:** Fiducia is an evidence-first, five-agent approval pipeline that converts a mutual-fund or ETF nomination into a policy-tested, audit-ready recommendation—while keeping material exceptions under accountable human control.

Fiducia directly addresses the challenge's six success criteria:

| Challenge criterion | Working proof in Fiducia |
|---|---|
| Autonomous end-to-end pipeline | The graph defines exactly five stakeholder roles. Valid intake runs through all five; invalid or unresolved intake deliberately short-circuits from Analyst to Decision Owner and skips unsafe downstream analysis. |
| AWS integration | Optional Bedrock Converse/Guardrail parameters and an AgentCore SDK-compatible entrypoint. The local SDK adapter passed HTTP 200/422 smoke checks; live Bedrock inference and AWS deployment were not validated in the event account. |
| Self-correction | Required-field detection, approved-source enrichment, conditional graph loop and a hard two-retry ceiling. |
| Insights and data joins | Category caps, benchmark comparison, fee-drag projection, plan profile and reference-catalog join. |
| Intuitive UI | Live node graph, editable intake, structured rationale, tool ledger, fee dashboard and attestation-gated HITL modal. |
| Modularity, scale and value | Role-separated in-process specialists, a versioned demo policy, an AgentCore-compatible adapter, and a transparent ROI sensitivity model. Queue-backed horizontal scale is an enterprise target. |

The differentiator is not more autonomy at any price. It is **safe straight-through recommendation assembly for clear cases and provable abstention for uncertain ones**.

## 1. Concept and architecture

### Product promise

Fiducia models a representative email-and-spreadsheet sequence as one typed case graph. Each node receives the shared workflow state, executes fixed role-specific Python operations, writes a structured result, and appends tool/audit receipts. Per-agent IAM and a dynamically enforced tool gateway are production targets.

```text
Submission → Analyst → Compliance → Governance → Finance → Decision Owner
                 ↘ bounded data-repair loop              ↘ human checkpoint
```

The hackathon implementation uses LangGraph for orchestration and the Bedrock Converse API for optional narrative generation. It supplies an Amazon Bedrock AgentCore SDK-compatible entrypoint, but that entrypoint has not been deployed or exercised in the event account. This choice follows AWS's September 2026 direction: AWS documents Bedrock Agents as Agents Classic, closed to new customers, and directs new agentic applications toward AgentCore.

The entrypoint's public contract is fail-closed: it accepts only the `fund`, optional `plan_profile`, and optional `model_mode` envelope; rejects unknown fields, boolean-as-number values, malformed identity/plan types, and non-finite numerics; and returns a JSON `422 REQUEST_VALIDATION_FAILED` response on validation errors. The local AgentCore SDK adapter was exercised in-process with Starlette TestClient; the AWS-managed deployment path remains unvalidated.

### Control-plane separation

| Plane | Authority | Examples |
|---|---|---|
| Evidence plane | Supplies facts; never instructions | Synthetic prospectus metrics, plan profile, source hash, as-of date |
| Agent plane | Extracts, classifies and explains | Five bounded prompts; concise rationale only |
| Policy plane | Owns pass/fail and routing | Python comparators, fee math, risk score, thresholds, retry ceiling |
| Human plane | Owns exceptions and overrides | Prototype: free-text reviewer IDs, reason, checkbox attestation, and distinct second ID for reject-to-approve; production authentication remains a target |
| Audit plane | Preserves lineage | Inputs, policy hash, tools, findings, transitions and decisions |

This separation contains hallucinations: a fluent response has no write permission to the policy result.

### AWS production topology target

The diagram below is a deployment design, not the locally validated runtime. The current build is a single-process Streamlit/LangGraph application with local JSONL audit files.

```text
CloudFront / React or Streamlit
          ↓
API Gateway + Cognito / enterprise SSO + WAF
          ↓
SQS / EventBridge ─→ AgentCore Runtime (LangGraph)
                         ├─ Bedrock Converse + Guardrails
                         ├─ AgentCore Gateway / least-privilege tools
                         ├─ DynamoDB state checkpoints
                         └─ S3 evidence + policy bundles
                                      ↓
                    S3 Object Lock + KMS + CloudTrail
                                      ↓
                   CloudWatch / OpenTelemetry / Evaluations
```

In the target design, AgentCore would host isolated runtime sessions, SQS would absorb spikes, DynamoDB would provide durable case state, and S3 Object Lock/KMS/CloudTrail would harden retention. None of those managed-service controls was deployed or load-tested locally.

## 2. Exactly five agents

### 1 — Analyst / Reviewer

- **Mission:** normalize structured intake and validate schema/ranges/freshness for NAV, expense ratio, Sharpe, 12b-1 components, explicit sales-load evidence, turnover, AUM, history and risk.
- **Tools:** schema and range validators, freshness calculator, untrusted-content scanner, approved reference lookup.
- **Output:** normalized metrics, missing fields, evidence SHA-256, quality score, confidence and concise rationale.
- **Handoff:** complete → Compliance; incomplete → enrichment loop; still incomplete after two tries → Decision Owner for fail-closed escalation.

### 2 — Compliance & Regulatory

- **Mission:** apply the versioned control library to product status/type and fee components.
- **Tools:** deterministic policy evaluator and approved reference index.
- **Output:** atomic internal-control results plus `WITHIN_CONFIGURED_REFERENCE`/`FAIL` labels for counsel-dependent regulatory references; no legal determination is made.
- **Handoff:** structured results always continue; hard stops cannot be cleared by later agents and force human confirmation.

### 3 — Governance & Suitability

- **Mission:** assess plan-level fit, not individual investment advice.
- **Tools:** plan-policy matcher, risk-band mapper and lineup-overlap checker.
- **Output:** checks for allowed class, risk ceiling, history, AUM and turnover.
- **Handoff:** sends every mismatch and condition to Finance and the Sponsor.

### 4 — Finance & Cost Analysis

- **Mission:** compare fees with the configured category cap and benchmark; quantify basis points and long-horizon impact; verify load/breakpoint evidence.
- **Tools:** benchmark lookup, fee-drag calculator and breakpoint validator.
- **Output:** cap delta, peer delta, transparent assumptions, estimated dollar drag and boundary flag.
- **Handoff:** sends structured economics and exceptions to the Sponsor.

### 5 — Decision Owner / Sponsor

- **Mission:** aggregate without overwriting specialist findings, calculate deterministic residual risk, and recommend a next action.
- **Tools:** finding aggregator, risk scorer, HITL router and audit writer.
- **Output:** `APPROVE`, `APPROVE_WITH_CONDITIONS`, `ESCALATE` or `REJECT`, plus confidence, decisive evidence and exact human reasons.
- **Handoff:** only exception-free, high-confidence, low-risk `APPROVE` completes automatically. Every other result pauses.

The executable prompts and tool lists live in `fiducia/prompts.py`; the expanded contracts are in `ARCHITECTURE_AND_GOVERNANCE.md`.

## 3. Self-correction without self-deception

Fiducia uses a bounded state machine:

1. Analyst returns an explicit list of required missing fields.
2. The orchestrator—not an LLM—queries an approved synthetic reference catalog by stable ticker.
3. Only requested blank fields may be filled; zero is never treated as blank.
4. The source and repaired field names enter the audit trace.
5. The Analyst reruns all validations.
6. At most two attempts are permitted.
7. No match or no material new evidence after two attempts routes to human review; downstream compliance never evaluates invented defaults.

`sales_load_pct` is required evidence: an absent load is missing, not silently converted to a no-load `0`. The first audit event preserves both raw and normalized fund/plan snapshots plus ingress errors, so failed coercion cannot erase what was submitted.

Source conflicts are never resolved through agent majority: explicit source-conflict flags and a `>1 bp` 12b-1 component mismatch route to a human. A general effective-dated rule registry and deterministic rule-precedence resolver are not in the prototype; they are required before production policy expansion.

## 4. Human-in-the-loop thresholds

### Auto-approval requires all of these

- recommendation is exactly `APPROVE`;
- no hard stop, missing critical evidence, source conflict or injection signal;
- minimum specialist confidence is at least `0.90`;
- deterministic risk score is at most `24/100`;
- expense ratio is more than `5 bps` away from its internal category cap;
- the local audit appends complete successfully; an append exception fails the run rather than returning an approval.

### Mandatory human review fires when any is true

- recommendation is `APPROVE_WITH_CONDITIONS`, `ESCALATE` or `REJECT`;
- confidence is below `0.85`;
- risk is `40/100` or higher;
- fee is within `±5 bps` of its cap;
- critical evidence remains missing after `2/2` attempts;
- source values conflict or the product taxonomy is unknown/out of scope;
- untrusted content contains an injection signal;
- a hard stop fires. An audit-write exception currently fails the run and surfaces a UI error rather than creating a human-review state.

Every prototype human action requires a nonblank reviewer ID, reason, and checked attestation. Overriding `REJECT` to `APPROVE` requires a distinct second nonblank ID; the test suite also proves that a finalized case cannot be edited again. These are free-text values in one UI session, so this is a simulated maker-checker control—not authenticated identity, cryptographic signing, RBAC, or production separation of duties.

## 5. Business value

Fiducia creates four measurable value pools:

1. **Cycle-time compression:** the target workflow removes email queues and can later parallelize independent reviews; the prototype executes specialist nodes serially.
2. **Expert capacity:** specialists handle exceptions instead of re-keying and arithmetic.
3. **Control consistency:** one versioned rule pack produces the same comparison every time.
4. **Audit readiness:** the local trace records the submitted snapshot, plan profile, policy version/hash, agent results, tool receipts, routing, and any prototype human decision under one trace ID. Field-level document locators and a production archive remain targets.

### Transparent illustrative ROI

The business-case model uses a representative—not TIAA-derived—base scenario:

- 5,000 annual cases;
- 8 baseline human touch-hours per case;
- $95 fully loaded hourly cost;
- 55% touch-time reduction;
- 15% rework rate, 2.5 hours per rework and 60% rework reduction;
- $850,000 implementation plus $400,000 first-year run cost.

It yields an **illustrative** $2,196,875 gross annual value, $946,875 first-year net value, 75.8% first-year ROI and 5.7-month simplified payback. A limited-volume scenario is negative ROI, which is deliberately shown. A shadow pilot must replace every assumption before investment approval.

### Proposed pilot KPIs—not observed results

- critical false-approval rate target: zero in an independent release test set;
- evidence coverage for decision-critical claims: 100%;
- numeric reconciliation: at least 99.5%;
- policy-version and audit completeness: 100%;
- human touch-time and end-to-end cycle-time reduction;
- rework/reopen rate;
- reviewer concordance, segmented by product and decision;
- p95 latency, run cost per case, override rate and reason distribution.

## 6. Scaling plan

### Phase 0 — two-week discovery

Map one product, establish baseline cycle/touch time, label historical synthetic cases, define the authority matrix and approve the evaluation set.

### Phase 1 — four-to-six-week shadow pilot

Run without affecting decisions. Compare with blinded experts. Gate on zero hard-stop false approvals, full evidence coverage, audit completeness and security testing.

### Phase 2 — assisted production

Fiducia prepares the packet; humans approve every case. Add SSO, least-privilege tools, durable checkpoints, WORM audit, monitoring and rollback.

### Phase 3 — scoped straight-through routing

Permit only approved, low-risk product/rule combinations to auto-complete. Preserve sampling, drift alarms, version rollback and immediate kill switches.

### Phase 4 — modular reuse

Add share-class change reviews, watch-list surveillance, RFP comparisons and periodic re-certification as separate policy packs—not one uncontrolled universal agent.

## 7. When the project fails or hallucinates

| Failure scenario | Detection | Containment and recovery |
|---|---|---|
| Missing fee | Required-field/null validation | Two synthetic-catalog attempts, then skip downstream specialists and escalate |
| Injection phrase in evidence note | Lexical scanner | Mark the scanner receipt `BLOCKED` and escalate; full document quarantine is a target |
| Wrong or stale rule | Prototype records policy version/hash but has no live regulatory-update service | Prevent production use until an owner-approved, effective-dated rule release process exists |
| Conflicting fee evidence | Explicit conflict flag and `1 bp` component reconciliation | Preserve the conflict and escalate; field-level multi-source adjudication is a target |
| Expense threshold mislabeled as law | Structured authority type and disclaimers | Label category caps as illustrative internal policy; keep SEC/FINRA references separate |
| LLM arithmetic error | Deterministic Decimal/basis-point calculation | Ignore prose number; render tool receipt |
| Five agents repeat the same mistake | Correlated-error evaluation | Independence comes from evidence and code, not agent count; require external test set |
| Bedrock throttling or outage | Converse exception handling | Deterministic narrative fallback preserves the code-computed decision; durable checkpoint/resume is a target |
| Audit write fails | Append exception | The caller receives an error and no result; operational alerting is a target |
| Unauthorized tool or data access | Not production-validated in the local build | Per-agent IAM, Gateway policy, egress allowlists, and tenant isolation are mandatory target controls |
| Rule passes but product is novel | Unknown applicability | Mandatory domain review; no extrapolation |
| Reviewer rubber-stamps output | Prototype exposes reasons and requires a checkbox attestation | Authenticated separation of duties, dwell-time/override analytics, sampling, and training are targets |

The full threat model, a 50+ item **planned** enterprise test catalogue, residual-risk register, and six prototype-safe negative demonstrations are in `RED_TEAM_AND_TEST_PLAN.md`. The actually executed automated-suite count is reported separately in `VALIDATION_REPORT.md`.

## 8. UI and live demonstration

The Streamlit cockpit contains four judge-friendly views:

1. **Decision cockpit:** editable submission, animated agent graph, recommendation, risk/confidence and approval modal.
2. **Agent workspace:** concise rationale, atomic checks, rule/source IDs, declared role-tool sets and invocation ledger.
3. **Audit & controls:** integrity verifier, hash-linked event table, JSONL export and exact HITL gates.
4. **Architecture & value:** deploy topology, business value and scaling story.

Recommended live sequence:

- Run `SUNX` to show the golden path.
- Run `DATA` to show a visible self-correction loop.
- Run `INJX` or `BLANK` to prove the system abstains rather than hallucinates.
- Open the audit tab and verify the chain.
- Open, but do not submit, the governed human modal.

Keep the UI in deterministic/offline mode for the judged demonstration unless the AWS path has been pre-warmed. Bedrock mode is a bonus, not a single point of failure.

## 9. Responsible regulatory framing

There is no claim that the SEC imposes one universal total expense-ratio cap. The demo's category caps are versioned illustrative plan policy. FINRA Rule 2341 fee references are separated into distribution, service and combined components and labeled as requiring legal/applicability review. Final production rule content must be approved by Legal and Compliance.

Primary references:

- [ASU challenge description](https://asuevents.asu.edu/event/ai-investment-spark-challenge?0=&eventDate=2026-09-22)
- [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
- [AWS Bedrock Agents Classic maintenance notice](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-classic-maintenance-mode.html)
- [Amazon Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-how.html)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [SEC mutual-fund fee bulletin](https://www.sec.gov/investor/alerts/ib_mutualfundfees.pdf)
- [FINRA Rule 2341](https://www.finra.org/rules-guidance/rulebooks/finra-rules/2341)

## 10. Submission checklist

- [x] Runnable local application with an AWS-optional path
- [x] Exactly five explicit agents, prompts, tools and handoffs
- [x] LangGraph state and conditional routing
- [x] Mock mutual-fund/ETF data with required metrics
- [x] Self-correction with retry ceiling
- [x] Deterministic fee, risk and policy checks
- [x] Human thresholds and prototype attestation/second-ID override flow
- [x] Tamper-evident JSON audit traces
- [x] Positive, exception and adversarial demo scenarios
- [x] Automated tests
- [x] Scale plan and transparent ROI sensitivity
- [x] Three-minute pitch, demo fallback and judge Q&A
- [x] Generated PowerPoint deck

**Closing message:** Fiducia does not ask judges to trust five agents. It gives judges—and a future risk committee—the evidence to verify every consequential step.
