# Development diagnostics

These are inspected development/regression outcomes, never independent held-out
observations. Original raw results and source snapshots remain unchanged.

## PDP attribution defect in the first revised diagnostic

`results/development-pdp-diagnostic-first` ran compatible_panels seed 71, revised
arm only. The controller selected one complements revision through real approval
and execution, then waited eleven cycles. Contribution profit was 6292929 minor
units; no controller errors or recorded hard-policy violations. This single-arm
run cannot measure lift. The seven-day durable whole-store guardrail was clear.

The new planner's reassessment incorrectly compared PDP-only line profit: an
alternative replaces the primary purchase, whereas a complement records only the
add-on on that surface. Omission of the primary checkout produced an erroneous
poor-performance classification and prevented a later complement experiment.
The correction measures whole redeemed checkout profit per recorded PDP visit,
including empty panels. Simulator checkouts follow one PDP visit; primary and
optional add-on receipts are counted once. Filters without a checkout attribution
link are rejected. This remains descriptive, not causal, and is not a general
production attribution model.

Read-only recomputation on the same retained receipts gives before: 4555 PDP
visits, 563 checkouts, 1883713 contribution-profit minor units in four days;
after: 8076 visits, 1054 checkouts, 3623011 minor units in seven days. There is no
25% deterioration signal with the compatible denominator. This is not proof of
benefit. Subsequent executions are explicitly post-fix regression observations,
not additional independent cases or a replacement for this failed diagnostic.

## Thin history

`results/development-thin-first` contains the three registered arms. Each recorded
519726 contribution-profit minor units with no intervention or controller error.
Each planner waited in its sole cycle. This case supports insufficient-data
abstention, not effectiveness or a causal comparison.

## First complete development condition

In `results/development-three-arm`, crowded_boots seed 71 records no-op and frozen
v1 contribution profit 6459158 minor units, revised 6250124: revised is worse by
209034 minor units. It sells 111 more excess units and records 891 more
search-attributed purchases, separate metrics rather than offsets to that loss.
The revision executes complements at expected versions zero and two, with expiry,
the existing measurement window and new version-two observations between them.
Search candidates are considered, but the explicitly excess boot has no observed
exposure gap. This adverse case is retained without tuning for a favorable score.

## Active noncheapest variant review

A separate authored regression exposed a missing reassessment row when the active
price revision belongs to a noncheapest variant. New experiment generation chooses
one bounded variant, but reassessment must independently inspect existing revised
variants. The first failing test is retained locally as `noncheapest-first.xml`.
This is a path defect, not an autonomous evaluation result. The running development
source was not edited midway. After completion, reassessment was separated from
new-experiment variant selection and now inspects every recorded price revision.
The focused regression passes; existing authoritative bounds were not relaxed.
An oversized-catalog regression also found a missing explicit unchanged row. That
fail-closed path now records unchanged plus actual family permissions, without
traversing the oversized input. Neither correction changes thresholds or fixture
outcomes to obtain a favorable score. These narrow fixes follow the retained
development source snapshot and precede the held-out freeze.

## Complete development comparison

Use `results/development-three-arm/summary-reviewed.json.gz`. The first generated
`summary.json.gz` is retained but grouped distinct price variants together when
counting repeats; the reviewed summary keys price targets by variant. It also
distinguishes no-execution days from planner waits and denied proposals. No raw
outcomes changed. The reporting correction has a regression against this archive.

| Condition, seed 71 | No-op profit | Frozen v1 profit | Revised profit | Revised minus v1 |
| --- | ---: | ---: | ---: | ---: |
| crowded_boots | 6459158 | 6459158 | 6250124 | -209034 |
| compatible_panels | 6371754 | 6371754 | 6350930 | -20824 |
| bounded_offer | 6285618 | 6272114 | 6247555 | -24559 |
| thin_history | 519726 | 519726 | 519726 | 0 |

All amounts are USD minor units. This is one development seed per condition;
there is no inferential interval or cross-objective aggregate score. Initial
world/permission hashes and incoming sessions match across all three arms.
The revised arm executes six PDP revisions and four distinct price experiments;
no search or new promotion is selected. It has 27/37 no-execution cycles. Frozen
v1 executes five price experiments; three selected promotion proposals are denied,
so its no-execution count is 32/37, not its 29 planner waits.

The four revised price targets are actually controller-selected, approved and
executed through the durable path. Later ledgers distinguish insufficient
observations from no descriptive stop signal and retain active/expired revision
history. No observed stop is selected in these development cases. Authored tests
cover poor-performance and deterministic-constraint stops separately. Seven-day
measurements complete where the horizon permits; late experiments still have
pending measurements, not assumed success. All raw hard-policy/unit-floor/combined
discount violation lists are empty; this does not turn adverse profit into benefit.

Search-attributed purchases rise substantially after switching from alternatives
to complements, partly because the primary search purchase is no longer replaced
by an alternative line. This attribution-sensitive metric is not equivalent to
more incoming shoppers or causal sales lift. Whole checkout and profit outcomes
remain separately reported.
