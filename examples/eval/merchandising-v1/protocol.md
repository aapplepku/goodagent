# Merchandising Evaluation V1

Registered before comparative rollouts. Synthetic simulator evidence only.
No generative model arm: the blocked runtime remains disabled.

## Design

Nine separately reported cases, two matched arms (no intervention and unmodified
merchandising-deterministic-v1). Development seeds 11 and 23; held-out seed 47.
All seeds and cases are retained, including errors and negative differences. No
tuning after comparative results. The held-out seed tests new draws, not new
mechanisms or independently authored merchant stores. Reproductions are not
additional cases. Three pairs per case imply very weak statistical precision.

Each arm uses the actual durable controller, tenant policy, exact approval,
executor, PostgreSQL receipts and shared MiniLM/Qdrant storefront. The evaluation
operator approves only proposals that pass current approval-required policy.
No-intervention has the same initial world, four observed warmup days, external
traffic and keyed draws, but does not execute agent proposals. Evaluation lasts
four further days, with one controller opportunity before each day. Insufficient
data instead has zero warmup and one evaluation day. All observation histories
come from real shared serving rollouts, never fabricated counters.

Traffic is exactly three channels of 400 base sessions each, each retaining the
simulator's keyed +/-3% daily variation, never bought by an action. Categories
and product-family queries follow the registered simulator mechanisms. Both arms
start from identical exogenous world definitions and seeds; UUIDs/tenant IDs do
not enter the exogenous draw keys. No demand elasticity is supplied to the planner.

## Cases

1. `overstock_exposure`: add four explicit authored boot-brand alternatives to
   make a finite five-slot shelf competitive; the last added product has excess
   stock. Report whether warmup actually establishes the intended exposure gap.
2. `poor_conversion`: all hiking-boot products have low latent quality (0.05),
   initialized only in the simulator. Planner receives observed outcomes only.
3. `active_promotion`: a pre-existing 10% boot promotion within legal limits and
   a $500 redemption cap. It lowers exact per-unit profit versus unchanged price;
   aggregate harm is not assumed. Report aggregate matched results and any wait.
4. `uncertain_price_response`: ordinary world, price/no-op only. No response
   estimate is fabricated; a wait is a valid result.
5. `irrelevant_high_margin`: unrelated headphones have cost 1 minor unit and
   excess stock. For charger PDPs they must never be admitted as alternatives or
   complements regardless of their profit margin.
6. `explicit_complements`: ordinary explicit charger/cable, boot/sock and
   tent/sleeping-bag pairs, PDP/no-op only. Alternatives remain same declared
   product type; incompatible products never become complements by similarity.
7. `no_discount_clearance`: excess-units objective, effective discount zero,
   promotion cap zero, create-discount prohibited; search/PDP/prices/no-op remain
   subject to exact economics. Target does not certify causal clearance.
8. `insufficient_data`: fresh zero-observation store and one day only; the initial
   coordinator cycle must wait rather than manufacture evidence.
9. `already_good`: all products have latent quality 0.95 and no excess-stock
   flag. This is a healthy synthetic input, not guaranteed optimal serving;
   report whether observations actually satisfy the intended condition and
   whether the controller still proposes an unnecessary experiment.

## Outcomes And Checks

Primary profit cases report contribution profit and profit per incoming eligible
session. Also report orders/session, net order value, per-product and per-category
sell-through, net realized unit prices, reference-basis redeemed promotion value,
search relevance, PDP explicit-relationship eligibility, exposure displacement
and substitute outcomes, action/rejection/wait counts, execution errors, hard
policy violations, unit/aggregate economic breaches, model calls/cost (zero).
Do not pool clearance and profit into an unexplained single score.

For each case, retain per-seed paired deltas and mean +/- t(0.975,2)=4.302652730
times sample standard error for three complete pairs. Intervals are descriptive
under synthetic independent seeds, not merchant generalization. If fewer than
three pairs complete, retain errors and do not silently impute a winning result.
Archive initial/final states, decisions, approvals/actions, serving batches,
redemption receipts and source hashes as compressed JSON evidence. Planner tools
must never receive the archived latent world. Read-only analysis may inspect
ground truth separately to grade outcomes and fixture conditions.
