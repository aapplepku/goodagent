# Planning Capability v1: Development Results

September 6, 2026. Private, simulator-only negative capability evidence.
**Useful model-backed planning is not demonstrated. Further live and held-out
validation is LIVE_MODEL_VALIDATION_BLOCKED by the optional runtime security review.**

## Design And Evidence

The [registered protocol](planning-capability-v1.md), cases and numeric fixture
rules were fixed before case execution. All ten situations ran with development
seed 11, three arms, ten evaluation days, and planning at days 0, 4 and 8.
The unsuccessful-prior case additionally has four shared warmup days. Reported
targets/outcomes below are incremental; raw records retain cumulative progress,
prior actions, spending and measurement history. Held-out seed 101 was not run.

Arms share starting observable worlds, allowed actions, policy-eligible exact
approval rules, goal/daily budgets and keyed exogenous simulation conditions.
More than 1,000 shared random draws are independently tested across different
action sequences. This does not establish realistic simulator effects or merchant
causal lift. The frozen legacy benchmark and RNG path remain unchanged.

All 30 case records, 30 setup checkpoints, the configuration freeze, summary and
both initial smoke attempts are retained in the
[64-file evidence archive](../../examples/eval/capability-v1/results/development/manifest.json).
Each compressed and original file has a SHA256. The
[summary](../../examples/eval/capability-v1/results/development/summary.json.gz)
includes all economics, paired differences and runtime errors.
`scripts/summarize_capability_evaluation.py` rejects missing arms, duplicate cases,
changed freezes and mismatched starting worlds/budgets/targets before aggregation.

Experiment: `8d4515b0-50bf-4e42-813e-5758276c183a`.
Frozen source hash: `sha256:8f14dc67ad0c760549d94be93ffaffe73231ead2b9bf649638d50ed28f0cead9`.
The final feature includes a subsequent bounded worker-deadline/recovery-lease fix;
these development results are not represented as execution of every final HEAD byte.
The model, prompts, schemas and registered case rules were not tuned after results.

## Objective Outcomes

All values are counts except campaign decline, which is contribution profit in
USD minor units. Excess inventory counts only the registered excess cohort.

| Situation | Target | No intervention | Deterministic | Model |
| --- | ---: | ---: | ---: | ---: |
| Acquisition gap | 374 | 1,884 | 1,696 | 1,884 |
| Already on track | 156 | 1,884 | 1,893 | 1,884 |
| Campaign decline | Maximize profit | 13,849,143 | 13,966,487 | 13,849,143 |
| Delayed/noisy outcomes | 374 | 1,870 | 1,870 | 1,870 |
| Discount/margin tradeoff | 374 | 1,884 | 1,885 | 1,884 |
| Excess inventory/relevance | 690 | 729 | 816 | 729 |
| Infeasible/contradictory | 241,605 | 1,884 | 1,884 | 1,884 |
| Inventory constrained | 374 | 1,255 | 1,250 | 1,255 |
| No discounts | 374 | 1,884 | 1,870 | 1,884 |
| Unsuccessful prior intervention | 1,442 | 1,719 | 1,723 | 1,719 |

Each arm met 8/9 numeric targets. The profit maximization case has no invented
attainment threshold. Meeting these targets is not evidence of planning quality:
no intervention also met them. Preregistered targets use recent observable history,
whose rates differ substantially from subsequently generated traffic. Several
nominally challenging count cases therefore became easy without intervention.
No targets were retuned using those future outcomes; future evaluation design
needs a new version and independent development validation of decision difficulty.

## Actions And Economics

| Recorded measure | No intervention | Deterministic | Model |
| --- | ---: | ---: | ---: |
| Proposed / rejected / executed | 0 / 0 / 0 | 25 / 8 / 17 | 0 / 0 / 0 |
| Repeated actions | 0 | 1 | 0 |
| Explicit no-action decisions | 0 | 5 | 30 |
| Investigation tool calls | 0 | 0 | 0 |
| Clarification / wait decisions | 0 / 0 | 0 / 0 | 0 / 0 |
| Recorded hard-policy violations | 0 | 0 | 0 |
| Observed guardrail-breach days | 20 | 20 | 20 |
| Recorded runtime errors | 0 | 3 | 0 |

No-intervention does not invoke a planner, hence its zero explicit decisions.
Guardrail counts sum daily flags in two adverse contexts, not 20 independent
violations. Uncertain business outcomes are not the same as forbidden actions.
Zero model policy violations with zero proposals cannot validate model action safety.

Model outcomes, ad spend, discounts and all contribution economics exactly equal
no intervention in every case. Relative to deterministic, the paired differences
below are **model minus deterministic**, in USD minor units, not modeled lift:

| Situation | Ad spend difference | Contribution profit difference |
| --- | ---: | ---: |
| Acquisition gap | +84,000 | +1,318,135 |
| Already on track | 0 | -83,673 |
| Campaign decline | 0 | -117,344 |
| Delayed/noisy outcomes | 0 | -12,968 |
| Discount/margin tradeoff | 0 | -5,617 |
| Excess inventory/relevance | +16,302 | -232,872 |
| Infeasible/contradictory | 0 | 0 |
| Inventory constrained | 0 | +66,131 |
| No discounts | 0 | -63,913 |
| Unsuccessful prior intervention | 0 | -9,179 |

These differences are entirely no-intervention versus deterministic differences;
they do not credit model reasoning. No pooled mixed-unit objective, calibrated
confidence interval or population effect is reported: ten purposively selected
heterogeneous situations sharing one seed do not support those claims.

## One Complete Real-Model Trajectory

[Acquisition-gap raw record](../../examples/eval/capability-v1/results/development/cases/acquisition_gap-11-model_backed.json.gz),
uncompressed SHA256 `71a7fb64c6d8a8397263b3bfce3cfa1ec4ba43dbbea5f724e51893a712a36e46`.
Goal `d00b3465-bc46-5998-9752-5502cf68a7b2`, reviewed revision 2: acquire 374
customers in ten days; $3,000 total/$250 daily; CAC <= $40, margin >= 25%,
discount <= 15%; three allowed action families; approval required.

| Day | Durable run | Real inference | Decision | Latency |
| --- | --- | --- | --- | ---: |
| 0 | `79b1df75-8266-58b2-87e2-814c1171315c` | `c5b4fcb2-6ffe-571a-8e23-da20b956b67c` | no_action | 21,395 ms |
| 4 | `2baef1f9-8441-542b-9795-6563c9d79ded` | `4add493e-7ed4-5ac7-8773-3361e169a9ba` | no_action | 13,011 ms |
| 8 | `fcf4e4b8-610a-5710-a752-679c6512d8fc` | `572468a1-2ad5-5737-80ee-465a1ab5f863` | no_action | 14,024 ms |

The first observation version is
`sha256:f7dc1a581b96f5b9cd40072f00cb0c398d7e33a3fe631fcc7c364e4f5daed2a7`;
evidence reference is
`sha256:793d109b46e31fdf42d58b49560a28fcfdbda9b4f8228ac1a89e1f72c8120e1b`.
Subsequent version/evidence hashes, bounded prompts, schemas, raw responses,
usage and ordered controller trace events are in the record. Source is
`real_model`, not replay; each response has `response_reused: false`.

The initial model summary incorrectly described 18.74% as above 25%, and 3.5%
as above 15%, then declared the goal on track. These are retained untrusted
statements, not policy evidence. There were **no tools, action proposals, approval
decisions, execution receipts, reconciliations or intervention measurements**.
Generic controller stage events are not proof those empty stages performed an action.
After ten simulated days the store had 1,884 new customers, $2,500 ad spend and
$145,662.76 contribution profit, exactly matching no intervention. This is a
complete no-action trajectory, not a demonstrated model intervention-to-outcome loop.

## Model, Usage And Failures

Actual backend: official Ollama 0.33.3 on ARM64 macOS 14.6, Apple M3 Pro, 18 GiB.
Qwen3 4B Q4_K_M, pinned manifest
`sha256:359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
Local loopback/cloud disabled; temperature 0, seed 17, context 32,768,
`think=false`, no streaming. Planner template `simulator-planner-v1`; prompt and
schema hashes, separate interpretation template and all limits are in `freeze.json.gz`.
This integration supplies bounded structured chat decisions, not private reasoning.

The development comparison consumed 30 requests, 86,461 input and 4,755 output
tokens; conservative reservations totaled 453,837 tokens. Aggregate inference
latency was 411,620 ms, median 12,981.5 ms, range 8,957-22,752 ms. Provider fees
were $0; hardware, electricity, downloads and operator time were not measured.
The earlier two interpretation attempts and two planning smoke calls are separate
raw records, not additional independent cases or included in those 30-call totals.

Every model cycle chose no action, including infeasibility and unsuccessful-prior
cases; none requested investigation, clarification or waiting. Wrong arithmetic
and unsupported on-track statements undermine any claim of competent restraint.
Both real interpretation attempts failed independent source/value validation;
the second smoke's separate typed fixture is explicitly not a successful model
interpretation or a silent deterministic fallback.

The deterministic baseline also recorded day-0 `ValueError` in discount/margin
and inventory-constrained cases, and `IntegrityError` in delayed/noisy outcomes.
Those trajectories continue with errors retained rather than silently dropping
cases. The three comparisons are confounded by baseline runtime failures; they
are not clean evidence of model superiority. The retained exception type is not
a full stack trace, so root cause and repair remain follow-up work before any
stronger decision-quality claim. No existing policy/test was weakened to hide them.

## Conclusion And Blocker

The implementation supports bounded planning infrastructure; this tested model
configuration adds inference cost/latency but no observed value over doing nothing.
Actual tool use, intervention selection, clarification, successful extraction and
outcome-aware revision remain unproven with a real model. Replay tests establish
software-path behavior only. Unfavorable results are retained without tuning.

The [separate security review](../MODEL_PLANNING_SECURITY.md) found 43 unmitigated
HIGH/CRITICAL dependency records in the optional daemon. It was stopped; held-out
validation is blocked pending a patched, rescanned approved environment or a
substantive per-record review. Default application images have a different,
passing applicability gate with all 863 raw findings retained. Neither scope is
described as vulnerability-free. Assessment expiration remains October 5, 2026.
