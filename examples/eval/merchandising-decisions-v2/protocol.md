# Merchandising decisions v2: registered comparison

Registered 2026-09-07 UTC before revised planner implementation or any new
held-out outcomes. This is synthetic domain-decision evidence, not real-model
validation. Original merchandising-v1 and search evidence remain unchanged.
Every previously inspected case/seed, including v1 seed 47, is development or
regression evidence for this milestone, not fresh held-out evidence.

## Arms and controls

Three arms: no intervention, frozen merchandising-deterministic-v1 copied
byte-for-byte from commit 5962b51571a10b84c787a6d8a06aa3b884ce4275 into
scripts/merchandising_v1_frozen.py, and revised deterministic controller.
The frozen planner retains its original thresholds, ordering, global cooldown,
version-zero restriction and economic candidate helper. Shared compiler, policy,
serving, accounting and exogenous mechanisms are identical across action arms.
Any necessary change to shared mechanisms must be reported as a comparability
limitation, never silently called a frozen full-system result.

Both action arms use the real durable pipeline and the same operator approval
rule: approve only exact current proposals that require approval and pass policy.
No manual action insertion, shadow bypass or special per-arm permission. No-op
sees the same initial catalog/traffic and can have pre-existing interventions.
The actual controller never receives case names, future data, latent demand
settings, seeds as decision features, or counterfactual-arm outcomes.

Existing keyed exogenous randomness and fixed external channels are retained.
No change to shopper response functions, randomness keys or reference accounting.
Use the pinned local MiniLM encoder/shared Qdrant and PDP serving in all arms;
this is retrieval, not a generative model call. No Ollama or paid service.

## Development diagnostics

Before broader rollout, reproduce original v1 cases from retained initial states,
then small controller-selected trajectories for search consideration, explicit PDP
consideration, monetary reassessment and sufficient/insufficient waiting.
Authored observation fixtures used for unit/path coverage must be labeled, not
mixed into effectiveness results. Development rollout seed 71, four conditions:

1. `crowded_boots`: eight boots total with distinctive brands, all relevant to
   the existing boot query; boot 8 has 600 units/variant and excess flag. Others
   have 180 units/variant. Objective: excess inventory units; no discounts.
2. `compatible_panels`: ordinary explicit compatibility catalog, all products
   300 units/variant; only search, PDP and no-op allowed; objective search orders.
3. `bounded_offer`: one existing 5% charger promotion, $300 offer/global cap,
   starts on warmup day 2 and lasts to horizon. Charger quality 0.10 is evaluator
   setup only. All merchandising families allowed; objective contribution profit.
4. `thin_history`: ordinary world, no warmup, one evaluation day; profit goal.

Three channels each have 600 base sessions/day. Except thin_history, warmup is
six days and evaluation is six days, one cycle/day, horizon 16 days. Diagnostics
may reveal no action; do not lower thresholds merely to manufacture an action.

## Fresh held-out conditions

Seeds 107, 131 and 163 are registered here but must not be run or inspected until
the revised rules/tests and development behavior are frozen in a DCO commit.
Four different conditions use the same durations/traffic/permissions across arms:

1. `crowded_storage`: nine food-container products, distinctive brands; container
   9 has 700 units/variant and excess flag, others 200. Excess-unit objective,
   no discounts, effective-discount ceiling and promotion cap zero.
2. `compatible_outdoors`: explicit tent/sleeping-bag and boot/sock relationships;
   all outdoor products 400 units/variant, other categories 160. Search/PDP/no-op
   only, search-purchase objective. All ordinary compatibility remains explicit.
3. `offer_with_alternatives`: existing 10% headphone promotion starting warmup day
   2, $300 cap, horizon-bounded. Headphone quality 0.20 and peers unchanged.
   All merchandising families; profit objective. No assumed harm/elasticity.
4. `satisfactory_stock`: ordinary catalog with quality 0.90, no excess flag,
   300 units/variant. All families and profit objective. This label does not
   certify satisfactory observations or require an action-free outcome.

All held-out conditions use six warmup and six evaluation days, horizon 16 days,
three fixed channels of 600 sessions/day with existing keyed daily variation.
No tuning to held-out outcomes. Bugs exposed there require preserved failure,
separately documented correction and labeled replay, not replacement or a new
independent case. Partial failures remain visible; no winning imputation.

## Reporting and integrity

Retain initial worlds/observed states, final state, complete candidate ledgers,
compiled/policy/approval/execution records, serving/order references, daily
observations, source/driver/protocol hashes and exact arm-selection mechanism.
Record all rejected/deferred reasons, unchanged choices, repeated targets and
reversals, runtime errors and data sufficiency. Freeze registration hashes before
running; refuse overwrites and mid-run source changes. Reproductions count zero
additional cases. Match incoming sessions and setup hashes excluding tenant/IDs.

Report objective metrics separately: contribution profit/per incoming session,
excess units for clearance, and search-attributed purchases/per incoming session
for search goals. Report orders, revenue, unit economics, redeemed discounts,
serving compatibility/relevance/displacement, aggregate guardrail breaches,
hard-policy violations, model calls/cost (zero), and adverse cases for each arm.
Pair revised-minus-no-op, frozen-minus-no-op and revised-minus-frozen by identical
condition/seed. For three complete held-out seeds report mean and descriptive
95% t interval using t(0.975,2)=4.302652730; no population-generalization claim.
Development seed 71 has no inferential interval. No cross-objective aggregate
score or favorable-result completion requirement. Unknown profit effects stay
unknown; before/after observations are not causal attribution.
