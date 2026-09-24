# Fiducia

**Five bounded agents. One evidence chain. Accountable decisions.**

Fiducia is a runnable, synthetic prototype for the 2026 ASU / TIAA AI Investment Spark Challenge. It turns a mutual-fund or ETF nomination into an evidence-backed due-diligence packet, deterministic control results, a fee comparison, a plan-fit assessment, and a governed approval recommendation.

The key design choice is simple: **the model may extract and explain; it may not invent a number, change a rule, execute an override, or approve its own exception.**

> This is an educational hackathon prototype using synthetic data and illustrative internal policy. It is not legal, fiduciary, tax, or investment advice and does not model or claim to represent TIAA's internal process.

## Demo in two minutes

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/streamlit run app.py
```

Open the URL printed by Streamlit, then run these scenarios:

Keep **Lock seeded identity** enabled for the rehearsed routes. Use **Restore
scenario defaults** before a live run if a field was edited. In particular,
`DATA` must remain `US Equity Index`; changing an identity field intentionally
blocks catalog enrichment and demonstrates the fail-closed route.

| Scenario | What it proves | Expected route |
|---|---|---|
| `SUNX` | Complete, low-cost golden path | `APPROVE`, no human touch |
| `DATA` | Missing Sharpe ratio | Approved-source enrichment, retry `1/2`, then green `APPROVE` with no human touch |
| `ALPHX` | Expense ratio over internal category cap | `ESCALATE` to human |
| `SPECX` | Status, suitability and cost hard stops | `REJECT` recommendation; no autonomous execution |
| `CONFX` | Conflicting source evidence | Fail closed to human |
| `INJX` | Prompt-injection text inside evidence | Content isolated, scanner `BLOCKED`, human route |
| `BLANK` | Fee absent from every approved source | Blank remains missing after `2/2`; compliance never runs |

For a terminal smoke demo:

```bash
.venv/bin/python scripts/run_demo.py --scenario all
```

## Five-agent graph

```mermaid
flowchart LR
    A[1 Analyst / Reviewer] -->|complete| C[2 Compliance]
    A -->|missing data| R[Approved-source repair]
    R -->|max 2| A
    A -->|still missing| S[5 Decision Owner]
    C --> G[3 Governance / Suitability]
    G --> F[4 Finance / Cost]
    F --> S
    S -->|all auto gates pass| E[Completed]
    S -->|exception / conflict / boundary| H[Human checkpoint]
```

LangGraph owns state and conditional routing. Amazon Bedrock Converse is an optional narrative layer. Deterministic Python owns validation, math, policy outcomes, risk scoring and human-intervention gates. The same graph has an Amazon Bedrock AgentCore entrypoint in [`agentcore_app.py`](agentcore_app.py).

AWS now describes Bedrock Agents as **Agents Classic** and directs new applications toward AgentCore. Fiducia therefore uses Bedrock Runtime/Converse plus an AgentCore-compatible adapter instead of creating a new Classic dependency. See the [official Agents Classic maintenance notice](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-classic-maintenance-mode.html) and [AgentCore Runtime documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html).

## Why this is not “five chatbots”

- A typed case state moves through explicit conditional edges.
- Each specialist has one role, a version-controlled prompt and a declared fixed tool set.
- Numeric checks and fee projections are deterministic and reproducible.
- Missing data triggers at most two materially bounded catalog lookups.
- Source conflicts, injection signals and boundary conditions cannot be voted away.
- The sponsor agent aggregates findings but cannot overwrite them.
- Human overrides require a reviewer ID, rationale and attestation; `REJECT → APPROVE` also requires a distinct second ID. Production still requires authenticated SSO/RBAC.
- Every transition is written to an append-only, SHA-256 hash-chained JSONL trace.

The local audit is accurately described as **tamper-evident**. Production hardens it to immutable/WORM storage using S3 Object Lock (Compliance mode), KMS and CloudTrail.

## Exact human gates

A case pauses for a named human when any of the following is true:

- recommendation is not plain `APPROVE`;
- minimum specialist confidence is below `0.85`;
- auto-approval confidence is below `0.90`;
- deterministic risk is at least `40/100` (mandatory review);
- expense ratio is within `±5 bps` of its category cap;
- any required field remains missing after two approved-source retries;
- sources conflict, an injection pattern is detected, or a hard-stop control fires;
- a `REJECT → APPROVE` override is attempted (the prototype requires a distinct second free-text ID; authenticated maker-checker is a production gate).

All values live in [`config/policy_rules.json`](config/policy_rules.json), with version, owner, scope, effective date and a runtime SHA-256 hash.

## Data model

The synthetic catalog includes the challenge metrics:

- NAV;
- expense ratio;
- Sharpe ratio;
- total 12b-1 fee plus distribution/service components;
- turnover rate.

It also carries explicit front-end sales-load evidence, AUM, track record, plan-risk score, status, as-of date, source-conflict flag and an untrusted evidence note. Empty and zero are different values. See [`data/mock_funds.csv`](data/mock_funds.csv).

## Bedrock modes

Offline mode is the default and is presentation-safe. It uses evidence-grounded templates while running the complete graph, tools, policies, retries, audit and HITL logic.

To enable Bedrock explanations:

```bash
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0
.venv/bin/streamlit run app.py
```

The process reads environment variables directly; it does not automatically load a `.env` file.

Choose **Amazon Bedrock Converse** in the sidebar. If inference or credentials fail, the narrative layer safely falls back; the deterministic decision is unchanged. Optional `BEDROCK_GUARDRAIL_ID` and `BEDROCK_GUARDRAIL_VERSION` values apply a configured Bedrock Guardrail.

[`agentcore_app.py`](agentcore_app.py) is an AgentCore SDK-compatible entrypoint. Deployment still requires creating a current AgentCore CLI project/configuration in the hackathon account, mapping the approved IAM role, and validating `agentcore dev` before any dry run or deployment. That account-specific step was not executed locally; see the validation report. Do not deploy from a personal account without cost and IAM review.

The local adapter contract can be reproduced without AWS credentials:

```bash
.venv/bin/pip install -r requirements-aws.txt
.venv/bin/python scripts/smoke_agentcore.py
```

It checks an invalid request returns HTTP `422` and a valid offline SUNX request returns HTTP `200`/`APPROVE`; it does not call Bedrock or deploy anything.

## Test and verify

```bash
.venv/bin/pytest
```

The automated suite covers:

- golden-path auto-approval;
- missing-data recovery and retry exhaustion;
- injection containment;
- hard-stop behavior;
- two-person overrides;
- blank-versus-zero semantics;
- reproducible fee math;
- audit-chain integrity and tamper detection;
- strict API/ingress typing, including boolean-as-number attacks;
- malformed plan profiles, absent load evidence and non-string identities;
- regulatory-reference labeling that makes no legal-compliance determination.

## Repository map

```text
app.py                         Streamlit decision cockpit
agentcore_app.py               Bedrock AgentCore runtime adapter
fiducia/
  agents.py                    Exactly five specialist implementations
  workflow.py                  LangGraph, conditional edges, retry and HITL nodes
  policy.py                    Deterministic policy and fee math
  prompts.py                   Explicit prompts and allowlisted tools
  llm.py                       Optional Bedrock Converse narrative adapter
  audit.py                     JSONL hash-chain writer/verifier
  validation.py                Strict external request and fail-closed ingress checks
config/policy_rules.json       Versioned illustrative policy pack
data/                          Synthetic intake and enrichment catalogs
tests/                         Safety, routing, math and audit tests
docs/
  SUBMISSION_REPORT.md         Judge-facing project report
  ARCHITECTURE_AND_GOVERNANCE.md
  BUSINESS_CASE.md
  RED_TEAM_AND_TEST_PLAN.md
  PITCH_SCRIPT.md
scripts/run_demo.py            CLI scenario runner
scripts/smoke_agentcore.py     Local SDK HTTP 200/422 contract smoke
scripts/generate_pitch_deck.py PowerPoint generator
```

## Submission assets

- [Executive submission report](docs/SUBMISSION_REPORT.md)
- [Architecture, prompts and governance](docs/ARCHITECTURE_AND_GOVERNANCE.md)
- [Business case, ROI and scale plan](docs/BUSINESS_CASE.md)
- [Failure, hallucination and adversarial test plan](docs/RED_TEAM_AND_TEST_PLAN.md)
- [Executed validation results and honest limitations](docs/VALIDATION_REPORT.md)
- [Exact three-minute pitch and judge Q&A](docs/PITCH_SCRIPT.md)
- [`Fiducia_Pitch_Deck.pptx`](Fiducia_Pitch_Deck.pptx) and [`Fiducia_Pitch_Deck.pdf`](Fiducia_Pitch_Deck.pdf)

## Responsible claims

Fiducia does **not** claim that the SEC sets one universal expense-ratio cap. Category caps in the demo are internal illustrative controls. The FINRA 2341 references are componentized and explicitly marked as requiring counsel/applicability validation. SEC materials explain how fees affect investors; they do not turn a configured sponsor threshold into law. See the [SEC fee bulletin](https://www.sec.gov/investor/alerts/ib_mutualfundfees.pdf) and [FINRA Rule 2341](https://www.finra.org/rules-guidance/rulebooks/finra-rules/2341).
