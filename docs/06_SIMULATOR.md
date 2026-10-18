# Commerce Simulator

## 1. Why simulator-first

Most developers do not own a store. The simulator is the zero-setup path that makes the project useful and shareable.

It must demonstrate the complete control loop:

```text
set goal → observe → act → simulate demand → measure → adapt
```

The simulator is also the safest test environment for autonomy and the contract test for every provider interface.

## 2. User experience

A user runs:

```bash
docker compose up --build
```

Then:

1. opens `http://localhost:3000`;
2. chooses a scenario;
3. sees a seeded catalog and 30 days of history;
4. enters or selects a goal;
5. starts the agent;
6. advances one day or runs the full horizon;
7. inspects each action, policy decision, and KPI change;
8. resets with the same or a new seed.

A demo run must be reproducible from:

```text
scenario_version + random_seed + goal + policy + code/model versions
```

## 3. Simulator provider interfaces

The simulator implements the same interfaces used by real providers:

```python
class CommerceProvider(Protocol):
    async def capabilities(self) -> CapabilitySet: ...
    async def sync_catalog(self, cursor: str | None) -> SyncPage: ...
    async def get_store_snapshot(self, as_of: datetime) -> StoreSnapshot: ...
    async def create_discount(self, command: CreateDiscountCommand) -> ProviderResult: ...
    async def disable_discount(self, command: DisableDiscountCommand) -> ProviderResult: ...
    async def set_variant_prices(self, command: SetVariantPricesCommand) -> ProviderResult: ...

class AdsProvider(Protocol):
    async def get_campaigns(self, as_of: datetime) -> list[CampaignSnapshot]: ...
    async def set_campaign_budget(self, command: SetCampaignBudgetCommand) -> ProviderResult: ...

class BehavioralEventProvider(Protocol):
    async def events(self, start: datetime, end: datetime) -> AsyncIterator[BehavioralEvent]: ...
```

It also implements a virtual clock and demand-generation service.

## 4. Seeded domain

Start with a compact but rich catalog:

- 1,000 products;
- 5 categories: apparel, footwear, outdoor, electronics, home;
- 1–5 variants per product;
- price, unit cost, margin, inventory, age, brand, attributes;
- dense text suitable for semantic search;
- category-specific attribute schemas;
- 10% cold-start products;
- 10% excess inventory;
- 5% low-stock products.

Customer segments:

- new bargain seeker;
- new quality seeker;
- returning loyal customer;
- category enthusiast;
- gift shopper;
- low-intent browser.

Traffic channels:

- organic/direct;
- paid search;
- paid social;
- email;
- project search widget/recommendation surface.

Campaigns:

- three acquisition campaigns with different reach, baseline CAC, audience quality, and diminishing returns.

## 5. Demand model

The simulator should be realistic enough to create trade-offs but simple enough to inspect.

For session `s` and product `p`:

```text
relevance(s,p)
  = semantic_intent_match
  + category_affinity
  + attribute_match
  + search_position_effect

utility(s,p)
  = relevance(s,p)
  + quality_preference × product_quality
  - price_sensitivity × log(effective_price / reference_price)
  + promotion_lift
  + personalization_affinity
  + seasonality
  + noise
```

Impression-to-click:

```text
P(click) = sigmoid(click_intercept + utility + position_bias)
```

Click-to-purchase:

```text
P(purchase | click)
  = sigmoid(
      conversion_intercept
      + utility
      + trust
      + availability
      - shipping_friction
  )
```

Use deterministic pseudorandom draws from a seeded generator.

### Discount effect

A discount:

- lowers effective price;
- increases conversion according to segment elasticity;
- reduces unit contribution;
- consumes promotion budget only when redeemed;
- may create a short-term urgency lift;
- may reduce future baseline willingness to pay in advanced scenarios, but omit this from v0.1.

### Price effect

Price changes alter demand with category- and segment-level elasticity. Base-price writes remain approval-gated in real mode but can execute within simulator bounds.

### Search boost effect

A search boost changes candidate exposure only after a relevance floor. It must not surface unrelated inventory.

### Ads budget effect

For campaign `c`:

```text
sessions_c(budget)
  = max_reach_c × (1 - exp(-budget / scale_c))
```

Customer quality may decline at higher spend:

```text
conversion_quality_c(budget)
  = baseline_quality_c - saturation_penalty_c × utilization
```

This gives the controller a real allocation problem rather than a linear “spend more” response.

## 6. Unit economics

Track per order:

- gross revenue;
- discount cost;
- cost of goods sold;
- payment/variable fee;
- ad-attributed acquisition cost;
- contribution profit.

Definitions:

```text
contribution_profit
  = revenue
  - discounts
  - COGS
  - variable_fees
  - attributed_ad_spend

CAC = acquisition_spend / new_customers
contribution_margin_rate = contribution_profit / gross_revenue
```

The UI and docs must state exact definitions.

## 7. Time model

A `VirtualClock` owns simulator time.

Operations:

```python
await simulator.advance(hours=24)
await simulator.run_until(goal.horizon.end_at)
await simulator.reset(seed=42)
```

Each simulated day:

1. campaign budget creates sessions;
2. users issue queries/browse;
3. retrieval/ranking determines exposure;
4. clicks, carts, and orders are sampled;
5. inventory decrements;
6. spend and promotion costs accrue;
7. webhooks/events are emitted;
8. metrics are materialized;
9. due intervention evaluations run;
10. the next agent planning cycle is enqueued.

Advancing virtual time must not depend on wall-clock sleeps.

## 8. Initial scenarios

### Scenario A: Acquire new customers

Initial state:

- $10,000 total acquisition/promotion budget;
- paid social has efficient low-volume traffic;
- paid search has moderate efficiency and headroom;
- a third channel is overspending;
- new visitor conversion is weak;
- selected products have enough margin for a small welcome discount.

Goal:

```text
Acquire 200 new customers in 30 days.
CAC <= $40.
Contribution margin >= 25%.
Discount <= 15%.
```

Expected controller behavior:

- reduce budget on the inefficient campaign;
- increase budget on a scalable campaign within limits;
- propose/launch a small welcome discount;
- monitor CAC and margin;
- roll back or reduce the discount if margin breaches;
- avoid spending the full budget if the CAC constraint cannot be maintained.

### Scenario B: Clear excess inventory

Initial state:

- one product family has 150+ days of supply and healthy margin;
- one related family is low stock;
- product relevance is high but exposure is low.

Goal:

```text
Reduce excess inventory units by 25%.
Maintain contribution margin >= 30%.
Promotion budget <= $5,000.
```

Expected behavior:

1. apply a bounded search boost;
2. create a bundle/discount proposal;
3. avoid boosting low-stock substitutes;
4. escalate discount only after observing weak sell-through.

For v0.1, bundle creation may be represented as a promotion scope rather than a full bundle product.

### Scenario C: Improve search conversion

Initial state:

- dense-only retrieval misses exact SKU/brand queries;
- lexical-only retrieval misses use-case queries;
- some high-margin products are irrelevant to target queries.

Goal:

```text
Increase search-attributed purchases by 15%.
Do not reduce relevance NDCG by more than 2%.
```

Expected behavior:

- choose hybrid search;
- create query-level boosts only above relevance floor;
- reject an aggressive margin-only boost;
- show benchmark and business outcomes.

## 9. Simulator APIs

```text
POST /v1/simulator/scenarios/{scenario_id}/instances
POST /v1/simulator/instances/{id}/advance
POST /v1/simulator/instances/{id}/run-until
POST /v1/simulator/instances/{id}/reset
GET  /v1/simulator/instances/{id}/state
GET  /v1/simulator/instances/{id}/metrics
```

Example:

```json
{
  "seed": 42,
  "start_at": "2026-09-01T00:00:00Z",
  "speed": "manual"
}
```

## 10. Implementation modules

```text
packages/backend/src/open_commerce/simulator/
├── clock.py
├── scenario.py
├── catalog_factory.py
├── customer_factory.py
├── campaign_factory.py
├── demand.py
├── economics.py
├── event_emitter.py
├── provider.py
├── state_store.py
└── scenarios/
    ├── acquisition_v1.py
    ├── excess_inventory_v1.py
    └── search_conversion_v1.py
```

Keep scenario data files versioned under `examples/scenarios/`.

## 11. Determinism

Rules:

- use one root seed and named sub-generators;
- never use global random state;
- sort entity IDs before random draws;
- persist scenario version and generator version;
- avoid non-deterministic parallel reduction;
- snapshots for the same inputs must match exactly, except generated UUIDs when explicitly excluded.

Add a golden test that hashes the 30-day metrics for seed `42`.

### Release qualification engine version

The hardened engine identifies itself as `simulator.2`, independently of scenario/catalog version `2026-09-04.1`. Customer identity is sampled before the purchase decision from a named random stream. Campaign traffic is funded by actual allowed spend; promotion cost is charged only on eligible redemption. Goal-bound advances settle those actual costs in PostgreSQL. Total/daily caps and engine version are included in the state hash. Reset generation is a separate execution precondition, so resetting an unowned instance to the same seed still reproduces the same world hash.

Old-engine state is retained for inspection but cannot be advanced under a new engine. Create a fresh goal for an upgraded or reset goal-owned run; in-place reset cannot erase its approvals, commands or budget history. Unowned simulator instances may be reset. Baseline comparisons apply the same total/daily caps and do not copy interventions. CAC and other rate deltas are differences between rates, not ratios of count differences.

`python scripts/update-simulator-goldens.py` regenerates every seed-42 reference and its raw totals in the packaged `golden_reference.json`. Review the engine change before running this explicit reference update. `python -m open_commerce.cli simulator golden` only verifies the committed reference. Updating a reference is not evidence that policy or release qualification passes.

## 12. Simulator UI

Show:

- virtual date and play/pause/step controls;
- goal progress;
- budget reserved/committed/remaining;
- KPI charts;
- current prices, discounts, campaigns, inventory;
- active interventions;
- action trace;
- rejected actions and policy reasons;
- “compare with no-agent baseline” toggle;
- reset seed.

A viral demo needs a clear side-by-side result:

```text
No-agent baseline     Agent
new customers: 142    207
CAC: $46.10           $38.30
margin: 28.2%         26.7%
budget used: $8,420   $9,810
```

Do not hard-code a guaranteed win. The controller should fail visibly when the goal is infeasible.

## 13. Contract testing

Run the same provider contract suite against:

- simulator;
- fake in-memory provider;
- Shopify sandbox adapter where safe.

Contract tests cover:

- capability reporting;
- pagination;
- idempotent discount creation;
- safe price updates;
- precondition failures;
- ambiguous response reconciliation;
- webhook/event emission;
- provider error normalization.

## 14. Definition of done

- one command launches the full simulator;
- all three scenarios are selectable;
- seed `42` is reproducible;
- the acquisition scenario runs at least five planning cycles;
- policy-denied actions appear in the trace;
- bounded actions alter future demand;
- budget and margin constraints are deterministically enforced;
- kill switch stops subsequent writes;
- no real integration credentials are required;
- a no-agent baseline can be rerun for comparison.
