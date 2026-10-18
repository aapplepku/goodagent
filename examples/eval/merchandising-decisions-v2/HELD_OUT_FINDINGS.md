# Registered held-out findings

All 36 arms completed from clean pre-outcome commit
`e11c226f60b0d1895726ae20887a6044a4d4f948`: four conditions, three seeds
(107, 131, 163), and no-intervention/frozen-v1/revised arms. There are twelve
matched independent condition/seed groups, not 36 independent planner comparisons.
The summarizer verifies every raw/source hash, identical initial world and
permissions, equal incoming sessions, all registered arms and no duplicates.
No controller error or generative model call was recorded. No runtime, fixture,
protocol or evaluator change occurred during or after this run.

The authoritative artifact is `results/held-out-first/summary.json.gz`:
SHA-256 `cc9c8c6df8548274a31785c23eb1dfe5825e4d5e13b3fb0ed6f60a5dd8608c3c`.
It binds raw manifest SHA-256
`705a1ba812d66403d4e80bd625700592e65e99e1fa50bf9612fe702f11e806a3`.
The adjacent manifest, registration and source archive retain all 36 raw files.
Each raw decision contains every candidate, not just its selected action.

## Contribution profit

All amounts below are USD over the same twelve evaluation days after six warmup
days. These are simulator outcomes, not projected demand or merchant lift.

| Condition | Seed | No intervention | Frozen v1 | Revised | Revised minus v1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| crowded_storage | 107 | 65126.26 | 65126.26 | 66180.79 | +1054.53 |
| crowded_storage | 131 | 61827.07 | 61827.07 | 62346.65 | +519.58 |
| crowded_storage | 163 | 65500.09 | 65500.09 | 65298.44 | -201.65 |
| compatible_outdoors | 107 | 65241.01 | 65241.01 | 66233.04 | +992.03 |
| compatible_outdoors | 131 | 61770.96 | 61770.96 | 62711.41 | +940.45 |
| compatible_outdoors | 163 | 65204.55 | 65204.55 | 64943.58 | -260.97 |
| offer_with_alternatives | 107 | 61639.31 | 61646.20 | 62521.25 | +875.05 |
| offer_with_alternatives | 131 | 58134.15 | 58014.48 | 59198.76 | +1184.28 |
| offer_with_alternatives | 163 | 60003.60 | 59983.62 | 60288.38 | +304.76 |
| satisfactory_stock | 107 | 74238.21 | 74230.48 | 73539.92 | -690.56 |
| satisfactory_stock | 131 | 69105.09 | 69174.33 | 71220.04 | +2045.71 |
| satisfactory_stock | 163 | 71761.44 | 71727.09 | 71963.31 | +236.22 |

| Condition | Mean revised minus v1 | Descriptive 95% paired t interval | Mean revised minus no-op | Mean v1 minus no-op |
| --- | ---: | --- | ---: | ---: |
| crowded_storage | +457.49 | [-1108.48, 2023.46] | +457.49 | 0.00 |
| compatible_outdoors | +557.17 | [-1204.08, 2318.42] | +557.17 | 0.00 |
| offer_with_alternatives | +788.03 | [-320.32, 1896.38] | +743.78 | -44.25 |
| satisfactory_stock | +530.46 | [-2926.62, 3987.54] | +539.51 | +9.05 |

Every revised profit interval includes zero. Three of twelve revised/v1 pairs
are adverse; the same three are adverse against no intervention. Development
also remains adverse in all three longer conditions. No aggregate across unlike
objectives is used to claim success. The machine-readable summary contains all
three paired comparisons and intervals for every reported metric.

## Objectives and attribution

For the clearance condition, revised excess units sold minus v1 average +105.33,
with descriptive interval [41.26, 169.41]. The adverse-profit seed 163 still sells
134 more excess units; inventory clearance and profit are not interchangeable.

For the search-only compatible condition, search-attributed purchases increase
by 789.33 on average, interval [650.19, 928.47]. Total orders instead change by
-5.33 on average, interval [-74.37, 63.70]. A complement keeps the original
search purchase while an alternative may replace it, so this metric partly
reflects surface attribution, not incremental new demand. Profit remains separate.

The profit-focused existing-offer and satisfactory-stock conditions also select
bounded experiments with unknown response, not a positive profit estimate. The
revised satisfactory-stock controller does not simply abstain: each seed executes
two PDP changes and four different price experiments. Its negative seed is a
limitation of the experiment-selection heuristic, not a scenario to rename or
retune after seeing the answer. The thin-history development case demonstrates
proper insufficient-data abstention separately.

## Selection, waiting and rejections

Each planner has 144 evaluation cycles; no-op has 144 days without execution.

| Result | Frozen v1 | Revised |
| --- | ---: | ---: |
| Executed price actions | 16 | 25 |
| Executed new promotions | 7 | 0 |
| Executed PDP policy changes | 0 | 23 |
| Executed search boosts / explicit stops | 0 / 0 | 0 / 0 |
| Planner waits | 115 | 96 |
| Selected proposals later denied | 6 | 0 |
| Days with no executed intervention | 121 (84.03%) | 96 (66.67%) |
| Completed measurements / pending | 16 / 7 | 24 / 24 |

V1 proposes thirteen promotions, six denied by existing policy. Revised policy
screening occurs before selection. It records 26,411 precompile-rejected rows,
292 policy-rejected rows and 233 otherwise-eligible alternatives deferred by the
one-intervention choice. There are 144 selected rows: 48 interventions and 96
explicit unchanged choices. These are repeated per-cycle diagnostic occurrences,
not independent experiments or 26,411 distinct products.

Examples of retained reasons include unsupported opportunity (23,948), price
already below observed peer median (7,524), prohibited family (7,128), larger
discount without response evidence (5,184), missing comparable cohort (1,584),
unidentified prior monetary response (441), and active-price reassessment (333).
Reason counts overlap. All 292 policy-rejected rows retain the parallel-active-
intervention limit and approval requirement in their complete policy result.
Approval-required is not itself an execution or proof of economic benefit.

Search exposure gaps were not supported, and new promotions lost to eligible
alternatives or were rejected. No selected search/new-promotion effectiveness or
selected observational-stop capability is claimed. Authored tests establish
those decision and safety paths, not autonomous success on this distribution.

## Replanning and safety

Twelve initial PDP changes use expected version zero; eleven later changes use
expected version two after expiry, prior measurement and fresh current-version
observations. Those eleven are explicitly repeated global-policy experiments,
not hidden as unique targets. No repeated price target or explicit stop/reversal
was selected in either planner arm. Recorded expiry restores future price/PDP
configuration separately; it is not a controller-selected stop or erased loss.

There are 404 recorded reassessment entries across repeated cycles: 229 classify
observations as insufficient and 175 find no descriptive stop signal. These are
not 404 independent economic outcomes. No constraint or observed-stop signal is
established by the evaluation. Conservative minimum-order gates can miss sparse
or zero-order harm; before/after remains noncausal and target-line monetary
comparisons do not identify whole-store substitution. Late measurements remain
pending and are not imputed clear. A clear durable guardrail is not positive lift.

All arms record zero known unit-floor breaches, combined-discount breaches,
hard-policy violations, negative aggregate-profit days and aggregate-margin-
below-unit-floor days. No safety-paused day was recorded. Those bounded checks
do not mean interventions cannot lose profit against the counterfactual.

## Inspect an adverse selected trajectory

Raw: `results/held-out-first/satisfactory_stock-107-revised.json.gz`. Cycles are
zero-based. Read `decisions[i].summary.merchandising_decision.candidates`, and
inspect approvals/execution/outcomes separately under `actions`.

- Cycle 0, run `1747d9dd-7d8f-5642-b193-c6757ba29a55`: PDP complements selected;
  all 193 other non-unchanged rows are precompile-rejected.
- Cycle 2, run `483fd4ae-42cf-5570-a4ba-e4688854656c`: tent variant 4 price
  experiment from 18900 to 17955 minor units. Its matched search evidence has
  496 exposures, 44 clicks and four orders; observed same-family peers have
  147 clicks and 18 orders, priced at 18300/18600. Stock is 289 units. Known
  unit profit falls from 8524 to 7606; predicted demand/store profit stay null.
- Cycle 4, run `529ef1a6-7047-5be9-9354-a4e932626481`: unchanged selected;
  three price and three promotion candidates are policy-rejected at the
  active-intervention limit. Reassessment lacks sufficient matched orders.
- Cycle 9, run `1a4fa17f-7c1f-5d78-9835-5405ac3b3af7`: PDP expected-version-two
  experiment selected, while two price and two promotion candidates are deferred.
- Cycle 11, run `37a1ea43-bea0-5046-bb6a-43ba5f1ca8fa`: unchanged selected;
  another price/promotion pair hits the active-intervention limit. Four price
  histories remain visible, including restored prices and insufficient evidence.

This controller-selected trajectory loses $690.56 versus v1 and $698.29 versus
no-op. It demonstrates inspectability and policy-bounded replanning, not reliable
profit improvement. [Development trajectories](TRAJECTORIES.md) retain additional
competing candidates, anchored PDP and insufficient-history decisions.

## Limits and reproduction

Only three registered seeds per condition, authored overlapping catalog/query
families, synthetic approval and keyed fixed traffic are tested. Intervals are
descriptive, not a causal or population-generalization claim. Replays are not new
held-out evidence. Policy and simulator economics remain unchanged.

**Historical private-history recipe:** this requires the exact frozen Git commit
and isolated-services setup in REPORT.md. The public source snapshot does not
include that original private Git object, so this command cannot reproduce the
historical run from the export alone. The exported result files remain available
for inspection; a new run on different source is not the original held-out run.

With the separately available frozen checkout:

```bash
uv run python -m scripts.run_merchandising_decisions \
  --split held_out --frozen-commit e11c226f60b0d1895726ae20887a6044a4d4f948 \
  --model-directory .opencommerce/merchandising/models/minilm \
  --output .opencommerce/decisions-held-out-reproduction
uv run python -m scripts.summarize_merchandising_decisions \
  .opencommerce/decisions-held-out-reproduction \
  --output .opencommerce/decisions-held-out-summary.json.gz --require-complete
```

The original runner exited zero and removed only its owned temporary evaluation
database. No prior demo/evidence database was reset. Browser/worker-health and
private-upload limitations remain in VALIDATION.md. This is deterministic
planning using a pinned local retrieval encoder, not generative-model validation;
Ollama remains disabled and its separate blocked findings are unchanged.
