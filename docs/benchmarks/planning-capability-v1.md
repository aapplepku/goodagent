# Planning Capability v1 Protocol

The ex-ante numeric recipe is in [fixture-rules.json](../../examples/eval/capability-v1/fixture-rules.json).
It clarifies shared prior actions and a four-day warmup for the unsuccessful-prior
case. Evaluation remains ten days; warmup counts and spending are reported
separately and never reset. The cumulative goal target includes already-observed
warmup progress, preserving the registered ten-day incremental target. These rules
were registered before capability case execution or held-out model calls.

Registered before candidate prompt tuning. This is a new simulator capability
evaluation, not a replacement for frozen controller-v2 or proof of merchant lift.
The machine-readable contract is [protocol.json](../../examples/eval/capability-v1/protocol.json)
and all ten decision situations are in [cases.json](../../examples/eval/capability-v1/cases.json).
No candidate results exist at registration time.

## Cases And Splits

Use every situation with development seed 11 and held-out seed 101, not favorable
selected seeds. Development is for debugging only. Freeze prompt/schema hashes
before the held-out run. A rerun is reproduction, not another independent case.
Report setup failures and unavailable evidence rather than silently dropping cases.

Count targets use only initial observable seven-day history, a fixed case factor
and the ten-day horizon. Profit is a supported maximization objective without an
invented count target. Physical infeasibility uses known remaining stock, never
held-out future demand. No target is chosen from future arm outcomes.

Fixtures are ex-ante scenario interventions, not favorable output patches:
thin-margin inventory, low stock, an explicitly scheduled campaign decay,
pending measurement and a shared prior intervention followed by adverse observed
conditions. The runner must retain setup/assumption checks. A nominally adverse
fixture that does not produce informative observable differences is reported as
uninformative, never resampled until it produces a preferred decision.

## Comparability

No-intervention, existing deterministic and model-backed arms share initial state,
available actions, policy, exact operator approval regime and business budgets.
The operator approves each policy-eligible proposal, not only attractive model
actions. No-intervention receives the same monitoring constraints but proposes
nothing. Deterministic behavior is not retuned to handicap or favor any arm.

Cycles occur at virtual days 0, 4 and 8; ten days allow pending and completed
measurement windows to appear in subsequent context. Policies may pause an arm.
Report pauses, unexecuted proposals, failures and missing observations explicitly.

The legacy engine uses sequential within-day random draws. Capability-v1 uses a
separately selected keyed exogenous-draw path: seed/day/channel/campaign/potential
session/product/purpose. Different traffic counts, product ordering, stockouts,
clicks or purchases must not consume another potential customer's random stream.
Tests must compare those keys across differing action sequences, not just rerun a
fixed action sequence. Unshared customers after traffic changes are a modeled
intervention effect, not independent evidence. Legacy RNG/goldens remain unchanged.

## Model Boundary

The planner sees only the structured goal, observable synthetic history and typed
read-only investigation results. Do not transmit seed, evaluator case/arm labels,
target-generation rules, hidden demand coefficients, scheduled future shocks or
counterfactual output. Record missing per-campaign/category attribution honestly.
The evaluator must not convert unavailable measurements into model evidence.

Permit investigation, typed proposal, clarification, waiting or no action. Do not
provide an evaluator answer key to the prompt or reward the proposed method for
matching a hardcoded preferred action. Decision-quality review covers evidence
use and constraint compliance alongside actual economics, including a worse model.

## Reporting

Report every case, arm, seed and setup check; objective/attainment, CAC, contribution
economics, ad spend/discount costs, proposed/rejected/executed/repeated actions,
no-action decisions, guardrail breaches versus hard-policy violations, infeasibility,
ambiguity and inference requests/tokens/latency/cost. Unknown cost remains unknown;
local zero API charge does not mean zero hardware/electricity cost.

Compute paired case/seed differences, descriptive mean/median/range and missingness.
Ten held-out situations with one seed each cannot establish population confidence
or real-merchant causal lift. Simulator behavior, model identity, prompt/schema
hashes, inference limits and all failure cases accompany the raw results.

Live results require an actual approved model. Mock/replay traces remain labeled
test evidence. If unavailable, report LIVE_MODEL_VALIDATION_BLOCKED and do not
manufacture a model-backed comparison from fixtures.
