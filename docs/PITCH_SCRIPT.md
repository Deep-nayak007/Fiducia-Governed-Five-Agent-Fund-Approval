# Fiducia — 3-Minute Pitch and Demo Runbook

## One-line positioning

**Fiducia is an evidence-bound, five-agent approval pipeline that turns a mutual-fund or ETF submission into a review-ready recommendation—with policy tests, fee math, human gates, and an audit trail built in.**

## Five-slide story

| Slide | Message | Visual |
|---|---|---|
| 1. Inbox speed is not decision speed | Manual handoffs create delay; a single ungrounded AI answer creates risk | Five-role email chain collapsing into one case ID |
| 2. Meet Fiducia | Five bounded agents, one controlled graph | Analyst → Compliance → Governance → Finance → Sponsor, with retry and HITL branches |
| 3. Live proof | Complete case flows; a missing field triggers bounded repair and revalidation | Product UI only—no architecture text during demo |
| 4. Autonomy with accountability | Evidence, deterministic controls, versioned rules, tamper-evident events | Four control icons and one audit record |
| 5. Start narrow, scale safely | Shadow pilot → assisted production → scoped reuse | Adoption staircase plus one transparent ROI equation |

Keep architecture detail in a backup slide. The main deck should support the demo, not compete with it.

## Exact 3-minute spoken script

The script is intentionally compact enough to leave time for clicks and pauses. Rehearse to the checkpoints; do not add unplanned architecture detail.

### 0:00–0:45 — The problem

> A fund can be analytically sound and still spend days trapped in inboxes. Experts re-key facts, reconstruct fees, check plan fit, and rebuild the final story. Asking one large model for an answer is not the solution: a fluent recommendation without evidence is not a control.
>
> Meet **Fiducia**: a five-agent approval pipeline for mutual funds and ETFs. It turns a submission into a review-ready recommendation with the record hash, policy version, deterministic checks, and every exception visible to the right human.

**Checkpoint:** At 0:45, say “right human” and switch from slide 1 to the live product.

### 0:45–1:45 — The solution and live demo

> Here is SUNX, a complete synthetic index fund. I press **Run** once. The Analyst normalizes the structured submission and validates required fields, ranges, freshness, fee components, and untrusted text. LangGraph routes the five stages. Python owns every calculation, rule, and gate; Bedrock is optional and only explains computed findings.
>
> Watch Compliance test versioned controls, Governance evaluate plan fit, and Finance compare fees, breakpoints, and benchmarks. The interface shows structured rationale and tool events—not private chain-of-thought.
>
> Next I run DATA. Its Sharpe ratio is blank. Fiducia checks composite identity, queries only the approved catalog, restores that field, and reruns the Analyst—retry one of two. All five specialists then pass their deterministic gates, so the Sponsor returns a green **APPROVE** with no human touch. The Agent workspace shows the tool ledger; the Audit tab verifies the tamper-evident chain. Exceptions still route to the governed human checkpoint, which I keep ready in SPECX for Q&A.

Presenter guardrail: leave **Lock seeded identity** enabled and click **Restore scenario defaults** before the live DATA run. Confirm its asset class reads **US Equity Index**. A changed identity correctly blocks enrichment and routes to human review, but that is the adversarial—not the rehearsed self-correction—path.

**Checkpoint:** At 1:45, the green DATA decision and verified audit evidence are visible and the cursor is still.

### 1:45–2:30 — Enterprise value and governance

> The current demo serializes each specialist so every transition is visible. The enterprise target keeps isolated durable case state, then scales independent specialists behind queues after safety testing.
>
> The value is faster decisions, recovered expert capacity, less rework, and a reconstructable control trail. Missing evidence, conflicts, unreconciled numbers, injection signals, or high risk fail closed to a qualified human.

**Checkpoint:** At 2:30, move to the adoption staircase; do not pause for the ROI slide.

### 2:30–3:00 — ROI and roadmap

> Using explicitly illustrative assumptions, the business-case model estimates **2.20 million dollars** of annual value against **1.25 million dollars** of first-year cost: **76 percent ROI**. This is not a TIAA forecast; shadow mode replaces every assumption.
>
> Adoption is modular: baseline one product, run in shadow, require human approval, then widen only proven low-risk scopes. Fiducia automates preparation, testing, and routing—not accountability.
>
> **Fiducia: faster decisions, visible controls, proof attached.**

**Stop:** Finish on the product name at 3:00. Do not add “thank you” if the clock is red.

## Live demo choreography

### Preloaded cases

- **SUNX — golden path:** complete synthetic index mutual fund. Expected result: `APPROVE`, no human checkpoint.
- **DATA — self-correction:** synthetic ETF with a blank Sharpe ratio. Expected result: one approved-catalog repair, green `APPROVE`, no human checkpoint.
- **Optional INJX — adversarial path:** injection text inside an evidence note. Expected result: scanner `BLOCKED`, `ESCALATE`, then human checkpoint.
- **Optional SPECX — hard-stop path:** multiple deterministic failures. Expected result: `REJECT` recommendation and governed human checkpoint.

Do not use a hard compliance failure as the only demo. A missing-data correction better proves self-correction; the hard-stop case can sit ready for Q&A.

### Operator sequence

| Pitch time | Operator action | What the audience must see | Spoken cue |
|---:|---|---|---|
| 0:40 | Product tab already focused; `SUNX` selected | Submission form and one `Run` button | “Meet Fiducia” |
| 0:47 | Click `Run` exactly once | Analyst node becomes active | “I press Run once” |
| 0:55 | Open the `Agent workspace` tab | Structured metrics, checks and tool statuses | “validates required fields…” |
| 1:03 | Return to graph | Compliance, Governance and Finance complete as bounded stages | “three bounded domains” |
| 1:12 | Select the pre-seeded `DATA` case and run | Blank Sharpe ratio and retry count `1/2` | “deliberate gap” |
| 1:23 | Watch the approved-catalog repair event | Same case ID; Analyst reruns with one restored field | “repairs that field” |
| 1:32 | Read the Decision packet | Green `APPROVE`, risk `0/100`, confidence `94%` | “Sponsor returns…” |
| 1:36 | Open `Audit & controls` | Verified chain, event table and policy hash | “Audit tab verifies…” |
| 1:42 | Return to cockpit | Green approval plus repaired-field banner | “no human touch” |
| 1:45 | Hands off mouse | Stable visual behind enterprise-value narration | “Fiducia scales…” |

### What not to show

- Raw chain-of-thought or a scrolling wall of model tokens. Show decision summaries, evidence, structured tool calls, and control events.
- Live source browsing, live document upload, AWS console navigation, terminals, deployment logs, or secrets.
- More than two cases in the core three minutes.
- An “AI confidence” gauge as proof of correctness. Evidence coverage and validation status are the controls.
- A universal “SEC expense-ratio cap.” Thresholds must be presented as configurable illustrative policy, not a fabricated universal rule.

## Demo fallback ladder

Prepare all levels and make each look intentional.

1. **Primary — validated local offline mode:** the full graph, policies, retries, audit and HITL run without network or AWS credentials.
2. **Optional enhancement — prevalidated Bedrock mode:** use only if the event account is warm and already tested; Bedrock changes narrative text, not outcomes.
3. **Fallback A — recorded local video:** cursor movement and narration match the operator sequence above; no audio dependency.
4. **Fallback B — deck slide 3 plus annotated screenshots:** show intake, retry, recommendation and audit integrity without implying a live run.

### Switch rule

If no first state transition appears within **five seconds**, say: “To respect the clock, I’ll show the validated local result for this exact synthetic case,” and switch to the video or slide. Do not troubleshoot on stage.

### Exact fallback narration

> This is the validated local run of the same synthetic case. The control behavior is unchanged: the field remains blank until an identity-matched catalog record supplies it, the retry is bounded, and the exception pauses for a human.

## Jury Q&A — likely questions and exact responses

Keep the first response under 25 seconds. Offer the backup slide only if the judge asks for more detail.

### 1. “Why five agents instead of one prompt or model?”

> The five roles create explicit handoffs, fixed tool contracts, and independently testable outputs. The prototype serializes them for visible audit transitions; the enterprise contracts are parallelizable. We never treat five votes as truth—deterministic validation sits outside the model loop.

### 2. “How do you prevent hallucinations?”

> We cannot claim a model never hallucinates, so model prose has no decision authority. Required-field checks, record and policy hashes, deterministic calculations, fixed controls, and fail-closed conflict routing own the outcome. The prominent decision summary is deterministic.

### 3. “Is this autonomous decision-making, and who carries fiduciary accountability?”

> Fiducia autonomously prepares, tests, routes, retries, and recommends within a bounded policy. Final authority is configurable and remains with the organization’s approved human decision owner for material or ambiguous cases. We are not claiming the model replaces fiduciary, legal, or compliance accountability.

### 4. “What is actually agentic here rather than a fixed workflow?”

> Each role autonomously executes its prescribed checks and fixed tools, while LangGraph conditionally routes missing-data and human-review branches. The bounded design is deliberate: in regulated decisions, unpredictability is not our definition of intelligence.

### 5. “What happens when two regulations or policies conflict?”

> The demo preserves seeded source conflicts and fails closed to a human. Product, jurisdiction, authority, and effective-date precedence are production rule-registry requirements owned by Compliance and Legal; we do not pretend that layer is already deployed.

### 6. “What expense-ratio cap are you enforcing?”

> We do not invent a universal regulatory cap. The demo applies a versioned, illustrative internal category policy to synthetic product and plan fields, while FINRA-reference checks are labeled `WITHIN_CONFIGURED_REFERENCE`, not legal compliance. Production would require Compliance-approved product, share-class, channel, jurisdiction, and effective-date applicability before evaluating a regulatory rule.

### 7. “How does this scale?”

> Today’s build is an isolated, in-process serialized graph. In the enterprise target, durable case state, idempotency keys, queue-backed workers, and parallel specialist contracts scale horizontally. We would size and load-test that target from measured arrivals—not extrapolate from a stage demo.

### 8. “Where did the ROI number come from?”

> It is a transparent illustration, not a TIAA estimate. The formula is case volume times baseline touch hours times loaded cost times measured reduction, plus avoided rework, minus implementation and run cost. The base illustration produces 76 percent first-year ROI, but shadow mode must replace every assumption before an investment decision.

### 9. “What if the source system or Bedrock is unavailable?”

> In this build, Bedrock uses short client timeouts and narrative failure falls back to deterministic text without changing the decision; audit or core-workflow failure prevents finalization. Circuit breakers, durable queues, and checkpoint/resume remain production deployment gates, not hidden demo claims.

### 10. “How will you validate accuracy before production?”

> We build an SME-labeled set covering normal, boundary, missing-data, adversarial, rule-conflict, and time-versioned cases. We measure hard-stop recall, unsupported claims, numeric reconciliation, evidence coverage, and human concordance. Then we run shadow mode, canary releases, drift monitoring, and one-click policy/model rollback.

### 11. “How do you secure confidential financial or participant data?”

> The hackathon uses synthetic data. An enterprise deployment would minimize and classify data, encrypt it, isolate network paths, redact where possible, assign a least-privilege identity to each agent, restrict tools and egress, log access, and enforce retention. Participant-specific suitability is out of scope unless approved data and controls exist.

### 12. “Can a human override the system?”

> Yes, but not invisibly. The demo requires reviewer ID, rationale, attestation, and a distinct second ID for `REJECT` to `APPROVE`, while preserving the original recommendation in the audit. Authenticated SSO/RBAC and evidence-bound authorization are mandatory before production.

### 13. “What makes this defensible if models become commodities?”

> The durable asset is not the model. It is the versioned policy and evidence graph, labeled evaluation suite, workflow integrations, authority matrix, and audit/control layer. The model can be replaced behind a governed gateway without rewriting the decision process.

### 14. “Could all five agents make the same mistake?”

> Yes. Shared evidence or a shared model creates correlated risk, so agent consensus is not validation. The prototype adds component reconciliation, composite-identity repair checks, deterministic calculations, adversarial tests, and human gates outside the agents. Production adds independent sources, blind evaluation, and ongoing human sampling.

### 15. “How is the AWS stack being used?”

> The tested build uses LangGraph typed state and conditional routing, with Bedrock Converse as an optional narrative adapter. An AgentCore-compatible entrypoint is supplied but not deployed locally. Identity, durable state, queues, WORM storage, and monitoring are the explicitly labeled production target.

### 16. “What would you do first after the hackathon?”

> Select one narrow fund-review path, map its authority and rules with reviewers, baseline cycle and touch time, and create a labeled test set. Then run six to twelve weeks in shadow mode. The first decision is whether evidence supports expansion—not whether we can maximize automation.

## One-page presentation checklist

### Content lock — day before

- [ ] Team agrees on one sentence: “Fiducia produces evidence-backed recommendations; it does not replace accountable decision owners.”
- [ ] All thresholds, policies, funds, and ROI figures are labeled **synthetic** or **illustrative**.
- [ ] No claim refers to TIAA internal workflow, cost, volume, controls, or expected savings.
- [ ] Main deck is five slides; architecture, controls, ROI math, data schema, and test results are backup slides.
- [ ] Numbers reconcile everywhere: `$2.20M` gross illustrative value, `$1.25M` first-year cost, `$0.95M` net value, `75.8%` ROI.
- [ ] SUNX, DATA, the backup video, and screenshots all use the same identifiers and expected outcomes.
- [ ] Demo contains no secrets, personal data, proprietary data, or unapproved logos.

### Technical readiness — 60 minutes before

- [ ] Open only the deck and product tabs; close Slack, email, terminal, notifications, password manager, and AWS console.
- [ ] Use synthetic seed data; confirm system clock/timezone and audit timestamps render clearly.
- [ ] Run SUNX and DATA once; verify switching scenarios clears the prior displayed result.
- [ ] Pre-warm the service; verify credentials, quotas, model access, network, display scaling, power, and screen sharing.
- [ ] Put the local video, deck, and four screenshots on the presentation machine and backup machine.
- [ ] Zoom/browser at readable size; hide bookmarks and developer panels; silence OS notifications.
- [ ] Start a local three-minute timer that only the timekeeper can see.

### Team roles

- [ ] **Speaker:** owns the story and never troubleshoots.
- [ ] **Demo driver:** performs only the rehearsed clicks.
- [ ] **Backup operator/timekeeper:** switches fallback at five seconds and signals 1:45, 2:30, and 2:50.
- [ ] **Q&A lead:** answers first, then directs one technical follow-up to the relevant teammate.
- [ ] If the team has three members, combine demo driver and Q&A lead—not speaker and backup operator.

### Final rehearsal

- [ ] Run once normally, once with Wi-Fi disabled, and once with an intentional slow first transition.
- [ ] Hit checkpoints: “right human” at 0:45; modal visible at 1:45; roadmap at 2:30; final line at 3:00.
- [ ] Speaker can state the ROI caveat and hallucination answer without looking at notes.
- [ ] Every teammate can answer: why five agents, what triggers HITL, what fails closed, and what is illustrative.
- [ ] Agree on one pause after each judge question; no teammate interrupts another.

### On-stage reset

- [ ] Select SUNX; position the product at top; set the deck to slide 1; backup video is one shortcut away.
- [ ] Confirm screen share shows the intended window and no presenter notes.
- [ ] Take one breath, start with the problem, and click only after saying “I press Run once.”
- [ ] If live state does not change in five seconds, use the exact fallback sentence and continue.
- [ ] End on: **“Fiducia: faster decisions, visible controls, proof attached.”**
