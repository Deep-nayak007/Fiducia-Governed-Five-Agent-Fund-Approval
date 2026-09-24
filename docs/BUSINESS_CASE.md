# Fiducia — Business Case, Scale Plan, and Risk Register

## Executive proposition

**Fiducia turns a mutual-fund or ETF submission into an evidence-backed, review-ready approval recommendation using five role-aligned agents, deterministic controls, and configurable human gates.** It is a decision-support and workflow-control system—not a substitute for fiduciary, legal, compliance, or sponsor accountability.

The five agents mirror a representative approval process:

1. **Analyst/Reviewer** normalizes the structured submission and validates quantitative facts.
2. **Compliance & Regulatory** tests versioned rules and records supporting evidence.
3. **Governance & Suitability** evaluates plan fit and retirement-portfolio considerations.
4. **Finance & Cost Analysis** compares configured fee structures, breakpoints, and category benchmarks.
5. **Decision Owner/Sponsor** reconciles the specialist findings and issues a recommendation, risk rating, and required next action.

The core product is not “five chatbots.” The executable prototype is a controlled case graph with typed state, fixed role-specific tool calls, versioned policy-as-code, bounded retries, fail-closed recommendations, a human checkpoint, and a tamper-evident local event trail. Field-level document citations, authenticated approval identities, durable checkpoints, and WORM retention are enterprise targets rather than current prototype capabilities.

## Business value hypothesis

| Value lever | Current friction represented in the challenge | Fiducia intervention | Measurable outcome |
|---|---|---|---|
| Faster decisions | Sequential email handoffs and duplicate data entry | Structured handoffs now; parallel specialist execution is an enterprise scaling target | Median and 95th-percentile cycle time |
| More reviewer capacity | Experts spend time finding, copying, and reconciling facts | Structured extraction, deterministic calculations, reusable evidence packet | Human touch-hours per case; cases per reviewer |
| Better control consistency | Rules can be applied differently across reviewers | Versioned policy packs and required control checks | Rule-test pass rate; reviewer concordance |
| Less rework | Missing fields and incompatible benchmarks surface late | Intake completeness gate and self-correction before downstream review | First-pass-complete rate; reopen rate |
| Audit readiness | Evidence is scattered across files and messages | One case ID links inputs, rule version, tool events, decisions, and overrides | Time to reconstruct a case; audit-log completeness |
| Safer automation | A fluent model answer may be mistaken for a verified decision | Structured synthetic-data outputs, deterministic validation, fail-closed routing, HITL; field-level evidence binding is a production target | Unsupported-claim rate; critical false-approval rate |
| Lower marginal cost | Each new review repeats similar collection work | Reusable agent services and policy packs | Fully loaded cost per completed case |

### Stakeholder value target

The table below describes the intended operating value. The current prototype demonstrates the decision packet, deterministic checks, two-retry enrichment, local audit trail, and an attestation-gated review form; it does not yet provide production source integrations, SSO/RBAC, durable replay, or a WORM archive.

| Stakeholder | Value received | What remains under human control |
|---|---|---|
| Analyst/Reviewer | Pre-populated metrics, reconciled identifiers, missing-data requests | Source validation and novel-product judgment |
| Compliance & Regulatory | Every test linked to policy version, effective date, and evidence | Interpretation of ambiguous or conflicting obligations |
| Governance/Suitability | Consistent plan-fit memo and documented assumptions | Fiduciary and committee judgment |
| Finance/Cost | Normalized share-class and benchmark comparison with reproducible math | Commercial exceptions and negotiated terms |
| Sponsor/Decision Owner | One decision packet, dissent view, residual risks, and clear next action | Final authority at configured approval gates |
| Risk/Internal Audit | Searchable, replayable lineage rather than reconstructed email history | Control design, sampling, and challenge |
| Technology/Operations | Modular workflow, model portability, observable cost and latency | Platform governance, security, resilience, and releases |

## Illustrative ROI model—not a TIAA forecast

All figures below are **hypothetical planning assumptions for a representative financial-services workflow**. They are not based on TIAA internal volumes, staffing, costs, control performance, or expected savings. A real business case must replace each assumption with measured baseline data from a shadow pilot.

### Formula

For one year:

```text
capacity_value = annual_cases × baseline_touch_hours_per_case
                 × loaded_hourly_cost × touch_time_reduction

rework_value   = annual_cases × baseline_rework_rate
                 × rework_hours_per_case × loaded_hourly_cost
                 × rework_reduction

gross_value    = capacity_value + rework_value
net_value      = gross_value - year_1_cost
year_1_ROI     = net_value / year_1_cost
benefit_cost   = gross_value / year_1_cost
break_even_cases = year_1_cost / value_per_case
```

“Capacity value” becomes cash savings only if recovered time is redeployed to valuable work, absorbs growth, avoids incremental hiring, or removes third-party spend. Avoided regulatory loss, revenue uplift, and faster product availability are intentionally excluded because they would be speculative without organization-specific evidence.

### Base-case illustration

| Assumption | Illustrative value | How to validate |
|---|---:|---|
| Annual cases | 5,000 | Count completed cases over the last 12 months |
| Baseline first-pass human touch time | 8.0 hours/case | Time study by process step and role, excluding reopened-case rework counted below |
| Fully loaded labor rate | $95/hour | Finance-approved blended rate |
| Touch-time reduction | 55% | Shadow-run delta versus control cohort |
| Baseline rework rate | 15% | Cases reopened for missing or inconsistent information |
| Rework effort | 2.5 hours/reworked case | Sampled case review |
| Rework reduction | 60% | Pilot comparison after completeness gate |
| One-time implementation/change cost | $850,000 | Integration, controls, testing, training, and launch |
| First-year run cost | $400,000 | Models, compute, storage, monitoring, support, and SMEs |

Calculation:

```text
capacity_value = 5,000 × 8.0 × $95 × 55% = $2,090,000
rework_value   = 5,000 × 15% × 2.5 × $95 × 60% = $106,875
gross_value    = $2,196,875
year_1_cost    = $850,000 + $400,000 = $1,250,000
net_value      = $946,875
year_1_ROI     = $946,875 / $1,250,000 = 75.8%
benefit_cost   = 1.76×
annual net operating benefit = $2,196,875 - $400,000 = $1,796,875
simple payback = $850,000 / ($1,796,875 / 12) = 5.7 months
```

At these assumptions, value per case is `$439.38`, so the simple first-year break-even volume is about `2,845 cases`. The payback calculation assumes benefits arrive uniformly after go-live and separates one-time implementation from run cost. A production financial model should use monthly cash flows, ramp curves, depreciation/accounting treatment, and confidence ranges.

### Sensitivity—not promises

| Scenario | Annual cases | Touch hours | Loaded rate | Touch reduction | Rework assumptions* | Gross value | Year-1 cost | Year-1 ROI |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| Limited pilot economics | 2,000 | 6.0 | $85 | 35% | 10%; 2.0h; 30% reduction | $367,200 | $800,000 | -54.1% |
| Base illustration | 5,000 | 8.0 | $95 | 55% | 15%; 2.5h; 60% reduction | $2,196,875 | $1,250,000 | 75.8% |
| Broader reuse illustration | 10,000 | 8.5 | $100 | 60% | 18%; 2.5h; 65% reduction | $5,392,500 | $1,800,000 | 199.6% |

\* Rework assumptions are `baseline rework rate; hours per reworked case; rework reduction`.

The sensitivity table makes the investment decision honest: low volume may not justify a production platform unless the same control layer is reused across workflows. The first pilot should optimize **learning and risk reduction**, not force a favorable ROI result.

## KPI scorecard and stage gates

Targets are proposed pilot hypotheses, not observed performance.

### Safety and control KPIs

| KPI | Definition | Proposed gate |
|---|---|---|
| Critical false-approval rate | Cases recommended for approval despite a labeled hard-stop condition | **0 in release test set**; any confirmed production event pauses affected policy/model version |
| Evidence coverage | Required decision claims with valid source ID, location, retrieval time, and policy link | 100% for final recommendations |
| Unsupported-claim rate | Material claims not entailed by cited evidence | <1% in labeled test set; 0 tolerated for hard-stop claims |
| Numeric reconciliation rate | Extracted/calculated values matching deterministic validators within defined tolerance | ≥99.5%; failures cannot auto-progress |
| Policy-version coverage | Rule evaluations tied to approved version and effective date | 100% |
| Audit completeness | Required lifecycle events present and integrity-checked | 100% |
| Override traceability | Overrides with actor, timestamp, reason code, narrative, and prior recommendation | 100% |
| High-severity security findings | Open critical/high findings at launch gate | 0 critical; risk owner signs any high exception |

### Operational and adoption KPIs

| KPI | Baseline | Pilot hypothesis |
|---|---|---|
| Median submission-to-recommendation time | Measure in discovery | <10 minutes of system time for complete, standard cases |
| End-to-end business cycle time | Measure in discovery | ≥50% reduction for eligible cases |
| Human touch time per case | Measure in discovery | 35–55% reduction without lower decision quality |
| First-pass-complete rate | Measure in discovery | ≥90% for submissions using guided intake |
| Reopen/rework rate | Measure in discovery | ≥40% relative reduction |
| Reviewer concordance | Double-blind human disposition versus Fiducia on labeled cases | ≥90% overall and 100% recall on labeled hard stops before controlled launch |
| Straight-through recommendation rate | Eligible low-risk cases requiring no clarification; final authority remains policy-configured | 50–70% after calibration, never at expense of safety KPIs |
| Human override rate | Share of recommendations changed by authorized reviewer | Observe and segment; do not suppress—overrides are learning signals |
| Unit cost | Total model/platform/operations cost per completed case | Establish in pilot; trend down with safe optimization |
| Availability and latency | Successful runs and p95 completion time | Set SLO after load test; do not infer from demo performance |

### Go/no-go sequence

1. **Offline validation:** pass safety gates on golden, adversarial, missing-data, conflict, and time-versioned cases.
2. **Shadow mode:** Fiducia recommends; humans execute the current process; compare outcomes without operational impact.
3. **Assisted production:** humans approve every final disposition; monitor overrides and near misses.
4. **Scoped automation:** only complete, low-risk, in-policy cases may move straight through to a recommendation or configured administrative action. Material decisions remain subject to the organization’s approved authority matrix.
5. **Expansion:** add product types, rules, or teams only after their own data, policy, security, and control validation.

## Human-in-the-loop policy

These are the executable thresholds in `config/policy_rules.json`; they are illustrative demo controls, not legal or fiduciary standards. Fiducia **fails closed** by withholding an automatic approval when a configured gate fails.

### Current prototype behavior

- The Analyst makes at most **two** reference-catalog enrichment attempts. Unresolved required fields route directly to the Decision Owner; Compliance, Governance, and Finance are skipped.
- `sales_load_pct` is required evidence; omission is treated as missing rather than a no-load zero. Boolean financial values, malformed fund identities, malformed explicit plan objects, non-finite numbers, and unsupported API-envelope fields fail closed.
- `APPROVE_WITH_CONDITIONS`, `ESCALATE`, and `REJECT` always require human review.
- Human review is also required when minimum specialist confidence is below `0.85`, risk is `≥40/100`, the expense ratio is within `±5 bps` of its category cap, required data remains missing, a source/fee-component conflict exists, an injection keyword is detected, or a hard stop fires.
- An otherwise clean `APPROVE` may auto-complete only with confidence `≥0.90`, risk `≤24/100`, no fee-boundary flag, and none of the exception conditions above.
- Any front-end sales load produces a Finance warning under the current demo policy and therefore an `APPROVE_WITH_CONDITIONS`/human route when no more severe issue applies.
- A human action is accepted only while the case is awaiting review, with a reviewer ID, rationale, and checked attestation. A `REJECT` → `APPROVE` action additionally requires a distinct second ID, and a finalized case cannot be edited again.

The reviewer and second-approver values are free-text identifiers in one Streamlit session. The checkbox and distinct-string validation demonstrate workflow controls; they are **not** authentication, a cryptographic signature, or production separation of duties. SSO/RBAC, verified identities, step-up authentication, and maker-checker assignment remain enterprise gates.

## Scaling design — enterprise target

### Scale by separating the stable control plane from variable content

The local build runs one case in-process and executes Compliance, Governance, and Finance serially. The mechanisms below are the proposed production design, not benchmarked or deployed capabilities of the hackathon prototype.

| Layer | Scale mechanism |
|---|---|
| Workflow | One isolated, idempotent case graph per submission; checkpoint after every node; retry only the failed node |
| Compute | Queue-backed, stateless workers; parallel Compliance, Governance, and Finance branches after intake validation; horizontal autoscaling |
| State | Typed case state with optimistic concurrency, case-level locks, and resumable checkpoints |
| Evidence | Curated source registry, document fingerprint, effective date, retrieval timestamp, and field-level lineage |
| Policy | Versioned policy packs by product, jurisdiction, plan, and effective date; four-eyes promotion and instant rollback |
| Models | Model gateway with approved versions, task-specific routing, structured outputs, token budgets, and canary releases |
| Security | Least-privilege tool identity per agent, encryption, private networking where required, tenant isolation, and retention policy |
| Audit | Append-only event envelope; integrity hash; durable retention; query index separated from the authoritative record |
| Operations | Traces, safety metrics, cost per case, dead-letter queue, replay tooling, and model/policy drift alerts |

Do not size the platform from a stage demo. Load-test with the measured arrival distribution. A useful first-order capacity equation is:

```text
required_concurrent_cases ≈ peak_arrival_rate_per_second
                            × average_case_runtime_seconds
                            / target_utilization
```

Then test downstream quotas, burst behavior, retry storms, document size, human-queue latency, and regional recovery. Cache only immutable or safely versioned artifacts; never cache a decision across cases.

### Modular expansion path

1. **Same workflow, more volume:** autoscale workers and partition queues without changing control logic.
2. **More fund variants:** add validated schemas and benchmark mappings; do not loosen the base schema.
3. **More rules:** target independently released, signed policy packs rather than changing model prompts.
4. **More business units:** separate tenant configuration, data access, authority matrix, and retention.
5. **More workflows:** reuse intake, evidence, policy, HITL, and audit services while creating a separately validated decision graph.

## Adoption roadmap

| Phase | Indicative duration | Scope | Exit evidence |
|---|---:|---|---|
| 0. Hackathon proof | 2–4 days | Synthetic mutual-fund/ETF data; five agents; two demo cases | End-to-end graph, exception route, tamper-evident local trace, working UI |
| 1. Discovery and controls | 0–6 weeks | Process map, authority matrix, data classification, rule inventory, baseline KPIs | Approved use case, control mapping, labeled validation set, threat model |
| 2. Shadow pilot | 6–12 weeks | One team, narrow product scope, no automated operational disposition | Safety gates passed, outcome comparison, cost/case, reviewer feedback |
| 3. Assisted production | 3–6 months | Human approval on every case; monitored integrations | Stable SLOs, acceptable overrides, audit/security sign-off, rollback drill |
| 4. Scoped scale | 6–12 months | Low-risk in-policy routing, more funds or teams | Realized-value evidence, per-scope validation, quarterly control review |
| 5. Reusable decision platform | 12+ months | Additional approval workflows with separate governance | Portfolio-level ROI, shared controls, workflow-specific certification |

### Change-management workstream

- Co-design the case packet and escalation taxonomy with actual reviewers.
- Name a business owner, compliance owner, model-risk owner, data owner, and technology owner before pilot.
- Treat overrides, abstentions, and user edits as labeled learning data after privacy review—not as automatic model training.
- Train reviewers on both appropriate reliance and how to challenge a recommendation.
- Publish the limits of use in the UI and require role-based acknowledgement.
- Review policy and model performance on a defined cadence and after material regulatory, product, or data changes.

## Where Fiducia can fail or hallucinate

Five agents do not create five independent sources of truth. They may share the same model, evidence, or flawed assumption, so consensus alone is not a control.

| Failure scenario | What could go wrong | Prevent/detect | System response |
|---|---|---|---|
| Missing or stale fund data | A plausible value is substituted or old evidence is used | **Current:** required-field, range, future-date, and 120-day freshness checks | Missing fields get up to two synthetic-catalog attempts, then escalate; stale evidence creates a warning/`APPROVE_WITH_CONDITIONS` human route rather than a hard stop |
| Wrong reference identity | Enrichment joins to a similarly named record | **Current:** ticker lookup plus exact fund name, product type, and asset-class match | Refuse enrichment, retain the conflict, retry to the ceiling, then escalate; CUSIP/share-class matching is a target |
| Benchmark mismatch | A fund is compared with an unsuitable category | **Current:** configured asset-class eligibility and category maps | Governance/Finance exception; richer benchmark-period validation is a target |
| Ambiguous or conflicting rules | A model chooses a convenient interpretation | **Target:** scoped, effective-dated rule registry and precedence metadata | Production must fail closed for Compliance adjudication; the prototype has no general rule-conflict resolver |
| Regulatory/policy drift | A previously correct rule becomes obsolete | **Target:** effective dates, owner review, source-change alerts, signed releases | Quarantine and replay are production controls, not demonstrated locally |
| Unsupported narrative | Optional LLM prose contradicts verified findings | **Current:** the prominent final summary is constructed deterministically and cannot be replaced by model prose | Preserve the structured result; claim-to-source-span validation remains a target |
| Arithmetic/unit error | Basis points or percentage values are misread | **Current:** a percentage-valued schema, finite/range checks, `Decimal` fee comparison, basis-point deltas, and fee-component reconciliation | Reject invalid inputs; explicit multi-unit ingestion and currency/annualization contracts are enterprise targets |
| Prompt injection in evidence text | Evidence tells an agent to ignore controls | **Current:** lexical scanner over the evidence note and deterministic routing | Mark the scan `BLOCKED` and escalate; document isolation, Guardrails, and quarantine are enterprise targets |
| Data poisoning or malformed input | Crafted values drive a favorable decision | **Current:** strict external envelope/type/boolean checks, internal finite-number/range/taxonomy/fee-reconciliation/plan-profile checks, and raw plus normalized audit snapshots | Fail closed; production source allowlists and anomaly detection remain targets |
| Correlated agent error | All specialists repeat the same incorrect submitted fact | **Current:** deterministic type/range/freshness checks, fee-component reconciliation, and explicit synthetic source-conflict flags | Production needs independent source retrieval and field-level reconciliation; agent agreement adds no authority |
| Suitability overreach | Generic fund facts are treated as individualized advice | **Current:** plan-level scope and configured plan risk/asset-class/lineup inputs | Produce plan-level analysis only; participant-specific advice is out of scope and requires a separately governed workflow |
| Automation bias | Reviewer accepts polished output without challenge | **Current:** structured findings, deterministic summary, explicit reasons, and attestation | Sampling, dwell-time analysis, and independent review are enterprise targets |
| Override abuse | A hard stop is bypassed without accountability | **Current:** review-state precondition, reason, attestation, distinct second free-text ID for reject-to-approve, and append-only human event | Authenticated RBAC, true maker-checker assignment, and WORM retention are required before production |
| Model/service outage | Workflow stalls or partial results look complete | **Current:** Bedrock narrative calls fall back to deterministic text; decision logic is local | Durable checkpoints, idempotency, queues, circuit breakers, and recovery drills are enterprise targets |
| Audit-log tampering | Decision history is altered | **Current:** canonical JSONL hash chain and optional HMAC verification | Local verification detects edits; restricted roles and S3 Object Lock/KMS/CloudTrail are production targets |
| Privacy or access breach | Sensitive data reaches an unauthorized tool | **Target:** data minimization, redaction, per-agent IAM, encryption, and egress controls | The synthetic local prototype is not evidence of tenant isolation or production privacy controls |

### Red-team cases to show judges

1. **`BLANK` — missing fee components:** the Analyst makes two catalog attempts, keeps the fields missing, skips the three downstream specialists, and escalates.
2. **Fee-component mismatch:** a submitted total more than `1 bp` away from distribution plus service components creates a conflict and escalates.
3. **`INJX` — injected evidence note:** the lexical scanner marks its tool receipt `BLOCKED`; deterministic routing escalates. This demonstrates containment, not a full document-security gateway.
4. **Invalid numbers and dates:** nonnumeric/NaN/infinite values, out-of-range values, and future-dated evidence cannot auto-approve.
5. **`SPECX` — hard stops:** status, product/suitability, and fee failures produce a `REJECT` recommendation that still pauses for human confirmation.

## Business and delivery risk register

Likelihood and impact are initial planning judgments to revisit during discovery.

| Risk | Likelihood | Impact | Mitigation and leading indicator | Accountable owner |
|---|---|---|---|---|
| Policy inventory is incomplete or ambiguous | High | High | Start with one bounded scope; require policy-owner sign-off; track unresolved conflicts | Compliance owner |
| Source data is incomplete, inconsistent, or not licensed for this use | High | High | Source contracts, quality profiling, provenance, and fail-closed intake; monitor missing-field rate | Data owner |
| Reviewers do not trust or use the output | Medium | High | Co-design evidence view; shadow mode; expose dissent; monitor adoption and override reasons | Business/product owner |
| Capacity value never becomes realized financial value | Medium | High | Agree redeployment, avoided-hiring, or service-level plan before funding; Finance validates realized hours | Finance sponsor |
| Automation bias raises false-approval risk | Medium | High | Evidence-first UI, sampled second review, hard-stop recall gate, reviewer training | Model-risk/governance owner |
| Prompt injection or excessive agent permissions cause a security event | Medium | High | Untrusted-content isolation, least privilege, egress/tool allowlists, adversarial tests | Security owner |
| Model, policy, or source changes degrade results | Medium | High | Version pinning, canaries, drift tests, change alerts, rollback, impact replay | Model-risk and compliance owners |
| Inference latency or cost erodes the case economics | Medium | Medium | Token budgets, task-sized models, caching of safe static artifacts, cost/case alerts | Technology owner |
| Integration outage creates an approval backlog | Medium | High | Durable queue, checkpoints, circuit breakers, manual fallback, recovery drills | Operations owner |
| Scope expands before the first workflow is validated | High | Medium | Named scope owner, stage-gate funding, separate validation for every product/workflow | Executive sponsor |
| Audit retention or evidence lineage is insufficient | Low | High | Records schedule, integrity tests, retrieval drills, and audit-owner acceptance | Records/audit owner |

## Decision recommendation

Advance Fiducia as a **narrow, shadow-mode pilot** if the hackathon prototype demonstrates four things: end-to-end state orchestration, a visible fail-closed exception, a structured rule/tool trace tied to the submitted snapshot and policy hash, and a complete prototype override/audit record. Fund a broader rollout only after field-level source lineage, authenticated authority controls, measured baseline economics, and the safety gates above are implemented and validated. That is a credible enterprise proposition: automate preparation and routing aggressively, but automate authority only where policy, evidence, and validation permit.
