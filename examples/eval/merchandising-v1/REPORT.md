# Merchandising Comparison V1

Private simulator evidence, not real-merchant lift or model-planning validation.
[Protocol](protocol.md), [derived summary and trajectory](summary.json),
[original runs](results/registered-first-pass/manifest.json),
[infrastructure recovery](results/infrastructure-recovery/manifest.json).
Recompute the summary with `python scripts/summarize_merchandising.py --check`.

## Design And Provenance
Nine authored cases, seeds 11/23 for development and 47 held out as a random draw;
the catalog families and case mechanisms themselves were not held out. Each pair
uses the same starting world, fixed external channels and keyed shopping opportunities.
There are 54 completed arms, 27 matched pairs, no generative model calls, and no
traffic purchasing. Four observed warmup days precede four evaluation days, except
the insufficient-data case, which starts empty and runs one day.

A local Compose rebuild mistakenly restarted PostgreSQL/Qdrant during the first
pass. All original errors remain. Recovery retains successful arms and reruns only
missing/interrupted arms with identical runtime/fixture hashes; its driver changed
only to orchestrate recovery. These are not additional independent cases. Both
source archives and every compressed rollout have verified hashes. The later PDP
API cold-index bypass does not change simulator serving or these comparisons.

## Results
Mean paired contribution-profit differences in USD, controller minus no intervention.
Intervals are descriptive Student-t 95% intervals with only three draws (df=2),
not calibrated merchant/generalization uncertainty. No pooled cross-objective score.

| Registered case | Mean difference | Descriptive interval |
| --- | ---: | ---: |
| Overstock exposure | -6.63 | [-114.73, 101.47] |
| Poor conversion | -2.65 | [-96.55, 91.25] |
| Active promotion | +6.86 | [-58.98, 72.71] |
| Uncertain price response | +6.86 | [-58.98, 72.71] |
| Irrelevant high margin | +35.46 | [-153.41, 224.33] |
| Explicit complements | 0.00 | [0.00, 0.00] |
| No-discount clearance | 0.00 | [0.00, 0.00] |
| Insufficient data | 0.00 | [0.00, 0.00] |
| Already good | +25.07 | [-165.52, 215.67] |

The summary includes per-arm profit/session, conversion, orders, units, order value,
net realized prices, promotion redemption, search relevance, PDP eligibility and
paired differences/intervals. Full product/category sell-through, exposure changes,
substitute outcomes and exact daily/line-level economics remain in the manifests
and raw states. Discounts are not deducted twice from net revenue. Redemption value
is a reference-basis accounting charge, not incremental profit lost.

Across 99 deterministic cycles: 36 proposals/executions (34 price, two promotion),
63 waits, zero compiler rejections and zero recorded controller errors. Independent
grading found zero hard-policy, known-unit-floor or combined-discount breaches in
these runs. This does not establish universal safety or favorable economics.
Model inference cost/calls are zero; hardware, energy and operator time are unmeasured.

## Coverage And Failure Cases
- Neither a registered case name nor a high latent quality setting proves the
  intended observable condition occurred. Warmup flags and product IDs are retained.
- No run met the coordinator's observed exposure-gap predicate. The overstock case
  therefore did not exercise a controller-selected search intervention.
- Complement and no-discount runs waited throughout. No search/PDP policy was
  selected in the comparison. Successful typed workflow fixtures are separate
  mechanism evidence, not evidence of competent diagnosis or lift.
- The already-good setup still contained four/five low-conversion products after
  warmup. The heuristic intervened, so this is not a demonstrated correct no-change
  decision for a uniformly good store. Insufficient-data runs did wait.
- The active-promotion setup did not trigger promotion disable. It is not proof
  that the planner detects counterfactual promotion harm. Known-cost violation
  disabling has focused tests; causal promotion harm remains unidentified.
- Unfavorable pairs remain: overstock seed 11 lost $49.55 and poor-conversion seed
  11 lost $37.61. All nonzero-case descriptive intervals span zero.
- These fixtures do not establish calibrated elasticity, an optimal price, causal
  merchant lift, or generalizable retrieval/recommendation quality.

## Recorded Trajectory
The summary projects the unfavorable overstock seed-11 controller run, including
exact action hashes, operator approvals, policy decisions, provider receipts,
reconciliation, measurement plans, exposed-product batches, referenced order lines,
bounded subsequent observations and measured product/store economics.

Its first action reduces food-container variant `merch_food_containers_3:v1` from
$40 to $38 for two virtual days, price version 0 to 1. The frozen reference stays
$40. At approval time, the planner explicitly records unknown demand response and
no predicted store profit. Actual shared serving exposes affected products; the
projection contains 36 affected-product serving batches and 83 referenced order
receipts. A second bounded price experiment follows the observation wait.
Store contribution profit is $13,514.46 versus $13,564.01 without intervention.
The small known unit calculation is not a promise of store-profit improvement.

The `workflows/` fixtures separately retain actual hash/MiniLM price and PDP policy
approval, injected crash after provider commit, fresh-pool retry, serving, one day
of purchases, and rollback. The explicit-complement fixture serves version 1,
records version-1 PDP purchases, then restores alternatives at version 2. Those
proposals are test inputs, not model output or controller-discovered opportunities.
