# Merchandising decision policy v2

Private deterministic simulator work, not a real-model validation or a release.
Historical [v1 diagnosis](../examples/eval/merchandising-decisions-v2/V1_DIAGNOSIS.md)
and [development failures](../examples/eval/merchandising-decisions-v2/DEVELOPMENT_FINDINGS.md)
are retained. New evaluation uses the registered protocol and its pre-outcome
measurement-horizon amendment. Earlier evaluations are unchanged.

## Explicit stages

Complete recorded surface observations -> bounded candidates and exact known
economics -> typed compilation -> authoritative policy -> one selection or wait
-> existing approval/execution -> observation and replanning.

Every inspected family has a candidate ledger: permission, opportunity, sample
sufficiency, draft generation, precompile reasons, compiler result, policy result,
selection/defer reason and evidence. At most 64 drafts are compiled. Diagnostic
catalog bounds are 128 products and 64 offers; larger input waits explicitly.
Unchanged configuration is an explicit comparison, not an automatically executed
no-op. A candidate passing policy is not an approval or an execution.

There is no scalar optimization score. Constraint/observational stops rank first.
Clearance then prefers the supported candidate's excess inventory scope; other
goals prefer search gaps, then PDP gaps, then monetary experiments, with fewer
affected variants preferred within that order. A stable semantic key breaks exact
ties. Search objectives exclude monetary experiments even if permissions permit
them. Profit comparisons without identified response remain unknown; these
preferences are declared bounded experiment heuristics, not estimated profit.

## Observations and experiments

- The ordinary investigation window is the last four complete UTC days, with at
  least two recorded days and 200 sessions. Partial days do not count.
- Search compares exposure with observed peers of the same declared type and
  category. A target below half peer-average exposure may support a bounded 1.10
  boost. No prior target order is required for a zero-exposure gap. Serving still
  enforces relevance, shopper constraints, availability and exclusions. Active
  boosts and recently changed targets wait; repeats require fresh post-expiry
  peer observations, not the prior experiment's exposure window.
- PDP complement evidence is anchored: at least 100 visits on two complete days,
  fewer than 20 exposures of the explicitly compatible product beside that anchor,
  available eligible stock and an observed purchase. Other panels exposing that
  product are not falsely counted as exposure beside this anchor.
- A monetary experiment needs at least 200 product search exposures, 20 search
  clicks, post-click orders below 10%, and comparable same-family/exact-query peers
  with sufficient observations and at least 10% post-click orders. The effective
  price must not already be below peer median. These gates establish an observed
  symptom and comparable evidence, not price sensitivity or elasticity.
- New monetary proposals use finite known economic candidates. Larger discounts
  are deferred without response evidence; active offers/prices are reassessed
  first. Product-wide prior monetary history prevents another markdown or a
  follow-on offer on a different variant without response identification.

## Reassessment and replanning

Known deterministic bound violations are distinct from observed deterioration.
They do not require an observed economic-loss claim. Observational stop proposals
require two complete days, 200 exposures and 20 orders in each before/after
window, with common search queries. A decline above 25% in contribution profit per
exposure is a descriptive review signal, never a causal estimate. Smaller or
insufficient samples wait. This conservative rule can miss harmful sparse or
zero-order interventions; absence of a stop signal is not proof of benefit.

Price/offer comparisons use matched search batches and redeemed target lines,
excluding declines, future receipts and unrelated surfaces. They do not identify
store-wide substitution effects. PDP strategy reassessment instead measures whole
checkout profit per recorded PDP visit, including empty panels: alternatives may
replace the primary purchase while complements add a line. Counting only panel
line profit confounds that attribution change with deterioration. Its corrected
development diagnostic is retained, not overwritten.

PDP version greater than zero is not a veto. A new experiment requires adequate
prior outcomes and fresh observations under the current version. An adverse prior
complement result prevents switching back without justification; an active
complement configuration is not repeatedly proposed. Seven-day measurement
spacing remains, followed by fresh current-version evidence. The same serving
path consumes approved revisions with exact expected-version preconditions.

All proposals still require compiler and current policy acceptance. Existing
measurement/concurrency gates may defer an early price/PDP restoration proposal;
v2 does not bypass them. Exact reviewed rollback remains a separate safety action.
Default approval, duration, cumulative movement, margin, promotion caps,
idempotency, reconciliation and rollback metadata are unchanged. Restoring future
configuration never erases orders, discounts, cap use or losses.

## Evidence boundaries

Unit fixtures and the authored-observation durable version-4-to-5 approval test
are path coverage, not autonomous effectiveness. The three-arm evaluator records
actual planner-selected actions and competing candidates without action injection.
Frozen v1 substitutes only its preserved planner; shared execution/serving and
keyed incoming traffic are identical. The evaluator dispatches the existing
tenant-scoped measurement handler directly, so queue timing is not graded.

Profit, excess units and search-attributed purchases are reported separately.
Descriptive paired intervals use three registered held-out seeds per condition,
not repeated replays as independent cases. Synthetic query/fixture overlap and
before/after confounding limit generalization. A favorable score is not required.

No public endpoint or migration is added. Existing read-only model evidence gains
bounded, surface-matched observations; raw query text is excluded there. The
model interface remains untrusted proposal input, never write authority. Ollama
remains disabled, with no paid fallback or real generative-model calls.
