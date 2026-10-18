# Private Model Planning Capability Report

September 6, 2026. **Negative development result; LIVE_MODEL_VALIDATION_BLOCKED
for further and held-out model validation. Not a release or merge recommendation.**

## 1. Branch And Review

Feature branch: `feature/model-backed-goal-planning`.
Base: `prep/public-preview` at `fc13a4bf29db06051f550fbe7dfc2b2d6a9bb820`.
Implementation commit: `10ac385b002fc24e388c9a8187e7d237e201feaa`, DCO-signed by
Han Chen <hc414t@gmail.com>, pushed to the private feature branch.
[Draft stacked PR #2](https://github.com/aapplepku/opencommerce/pull/2) targets
the exact preparation base. This report-only follow-up does not alter tested
product code. Its final HEAD is in delivery/PR metadata, avoiding a document that
purports to contain its own commit hash. PR #1 remains open/draft/unmerged.
Main and RC remain `c2617412d0d926946c0b532c9ea7250cc89eb21d`; the annotated
RC tag object remains `d95722d260252d6cc81f0471082c4f9939db02a8`.
No protected branch, tag, review requirement or publication setting was changed.

## 2. Implemented And Missing

Implemented: explicit deterministic/model-backed selection; finite reviewed goal
interpretation and typed review; semantic revisions and stale approval/proposal
invalidation; one real loopback Ollama integration; independent inference
reservations and immutable journal; bounded checkpointed read-only investigation;
strict proposals through existing compiler/policy/approval/budget/durable executor;
mode/provenance/usage UI and generated contracts; ten-case, three-arm paired
evaluation; adversarial, restart, migration and browser tests.

New behavior is concentrated in `controller/goal_*`, `durable_goals.py`,
`model_*`, `ollama.py`, `inference.py`, capability evaluation/fixture modules,
goal/inference persistence, API/SDK, worker deadlines and the existing demo UI.
The full file inventory and execution plan are retained in the private development
record. The public [model-planning guide](MODEL_PLANNING.md) describes this
historical simulator capability, configuration and safety boundaries.

Missing real-model demonstrations: successful reviewed natural-language extraction,
tool investigation, appropriate intervention, action-to-measurement trace,
clarification of infeasibility, and useful outcome-aware revision. Those software
paths have replay tests, not real-model qualification. No new live connectors,
paid provider, production authentication, learned retrieval or orchestration
framework was added. Existing deterministic and hash-based retrieval labels remain.

## 3. Actual Model

Ollama 0.33.3, local ARM64 macOS, Qwen3 4B Q4_K_M, pinned model digest
`sha256:359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
Temperature 0, seed 17, context 32,768, output cap 1,024, thinking disabled,
non-streaming. Literal loopback, cloud disabled, no credentials/paid calls.
The daemon is now stopped and not security-qualified. No binary or model weights
are distributed. Full hashes, prompt/schema versions and environment are in the
[development report](benchmarks/planning-capability-v1-results.md).

## 4. Real Trace

The [complete acquisition-gap trajectory](benchmarks/planning-capability-v1-results.md#one-complete-real-model-trajectory)
retains reviewed goal revision 2, three durable runs/inferences, observation/evidence
hashes, bounded prompts, raw responses, usage and ten days of simulator outcomes.
All three decisions were no_action. Zero approvals, executions, receipts,
reconciliations or intervention measurements occurred. Empty generic pipeline
stages are not represented as a successful model-driven commerce intervention.

## 5. Interpretation Examples

These are verified **finite deterministic parser** examples, not claimed model
successes. Each ready draft still requires explicit typed review and exact hash.

| Input | Result |
| --- | --- |
| Acquire 321 new customers in 17 days with a $1234.56 budget. Daily budget $12.50. CAC <= $19.25; margin >= 31%; discount <= 7.5%. | All values preserved; typed money/constraints, ready for review |
| Acquire 500 new customers in 20 days; budget: $900. No discounts. | Discount ceiling zero and discount action excluded |
| Acquire 500 new customers in 20 days; budget: $900. Only search boosts. | Only search-boost actions allowed |
| Clear 230 excess inventory units in 14 days; budget: $600 | Scoped measurable units-sold target 230 |
| Prioritize contribution profit in 14 days; budget: $600 | Profit maximization; no invented count target |
| Acquire 100 new customers in 30 days | Clarification required: missing budget; no activatable review hash |
| Acquire 100 new customers in 30 days; budget: $100. No discounts; discounts <= 10%. | Conflicting constraints require clarification |
| Maximize lifetime value in 30 days with a $100 budget | Unsupported objective; no acquisition substitution |

Both actual model interpretation attempts omitted total budget and invented source
text; independent validation returned clarification_required with no draft. The
second smoke independently activated an operator-reviewed typed fixture, explicitly
labeled as such. No deterministic response was presented as model interpretation.

## 6. Comparison

All ten registered development situations, seed 11, three arms completed their
trajectories. Model: 30 no-action decisions, zero tool calls/proposals/executions.
Its outcomes and economics exactly matched no intervention. All arms met 8/9
numeric targets. Deterministic: 25 proposals, eight rejections, 17 executions,
one repeated action and three retained runtime errors. Full per-case objectives,
spend, profit and paired differences are in the
[results](benchmarks/planning-capability-v1-results.md) and hashed raw archive.
No mixed-unit pooled effect, calibrated interval or merchant causal lift is claimed.

## 7. Unfavorable Results

The model made incorrect numeric comparisons and unsupported on-track claims,
including in infeasibility contexts; no-action is not evidence of competent
restraint. Several registered count targets became easy under future simulated
traffic, limiting decision difficulty. Deterministic day-0 errors affect three
cases: two ValueErrors and one IntegrityError. They were retained, not omitted or
treated as clean comparisons. Root causes remain follow-up work; only exception
types and runtime records, not full stack traces, were retained by the evaluator.
No cases, targets, prompts or expected answers were retuned to produce a win.

## 8. Safety And Regression

Local `make check` passed: lint; strict Python/TypeScript checks; 435 backend
unit/contract tests; 62 web tests; eight SDK tests; frozen simulator goldens;
search and controller smoke; 66 real-dependency integration tests; generated
OpenAPI/client and legal/path checks. The opt-in live-model integration is the
one intentional skip in ordinary tests, not a credential-free model success.
Four isolated Compose outage/recovery checks and all six production browser tests
passed. Desktop/mobile screenshots were inspected; the browser suite covers
reviewed revisions, explicit model failure, saved goals, approvals, worker
execution, measurements, search and reset on the real local stack.

New focused coverage includes goal values/prohibitions/ambiguity, unsupported
metrics, prompt injection, malformed output, invented IDs/cost/margin, stale
observations, inference budgets and unknown dispatch, restart replay, tool/iteration
caps, goal revision invalidation, exact approvals, duplicate execution and measured
outcome context. Ordinary model fixtures explicitly identify replay provenance.

Default application image review: 863 raw records, including 15 CRITICAL and 253
HIGH; all 268 HIGH/CRITICAL have matching unexpired applicability records and
zero unresolved applicable findings in that scoped deployment. Fresh images,
runtime proof, source/dependency scans and SBOMs are retained. Thirty-five
reference-only scanner changes were explicitly reviewed; the strict gate was not
relaxed. The optional model runtime has 74 raw records, including one CRITICAL
and 42 HIGH, all 43 conservatively BLOCK. This is not a zero-vulnerability claim.
[Full security assessment and archive locations](MODEL_PLANNING_SECURITY.md).

## 9. Cost, Latency And Limits

Development comparison: 30 calls; 86,461 input / 4,755 output tokens; 453,837
conservative reserved tokens; 411,620 ms aggregate inference latency, median
12,981.5 ms and range 8,957-22,752 ms. Initial smoke attempts add four calls,
6,053 input / 1,074 output, 41,728 reserved tokens and 73,161 ms, separately
counted and not new independent evaluation cases. Provider fees were $0;
electricity/hardware/download/operator costs are unmeasured.

Each planning cycle permits four requests, three read-only tools, two proposals
per final decision, 16,000 input-message bytes and 1,024 output tokens per request,
60 seconds per request, no automatic retries. Separate conservative limits are
40 requests/720,000 tokens per goal and 150 requests/2,700,000 tokens per UTC
tenant day. Unknown dispatched work consumes its reservation and is not reissued.
Limits and settlement are independent of merchant budgets. The worker deadline
and recovery lease cover the bounded cycle. No paid-provider fallback exists.

## 10. Usefulness Conclusion

**No evidence of useful model-backed planning in this tested configuration.**
The infrastructure connects a real model to bounded simulator observations, but
the observed model adds latency without improving on no intervention. This is a
valid negative development result, not successful agent capability qualification.
Replay safety coverage cannot establish real decision quality.

## 11. Blockers And Operation

Further/held-out model evaluation is LIVE_MODEL_VALIDATION_BLOCKED until a patched,
rescanned operator-approved runtime or substantive per-record applicability review
resolves the 43 blocked records. Native-library/model parsing coverage remains
incomplete. All assessments have a hard October 5, 2026 review date. Baseline
errors and limited case difficulty also prevent stronger comparative claims.

Use the private feature branch with model mode disabled for normal review.
Apply migrations `0006_goal_revisions` and `0007_inference_journal` only to the
chosen development database. The default Compose stack remains no-key and does
not start/download a model. Do not migrate frozen evidence databases in place.
For future model operation, follow [explicit opt-in and limits](MODEL_PLANNING.md)
only after resolving the runtime security blocker. Independent PR review and
exact-commit hosted qualification remain separate from these local results.

No merge, tag, Release, registry/image publication, visibility change, live
commerce capability or change to Apache-2.0/DCO was performed for this milestone.
