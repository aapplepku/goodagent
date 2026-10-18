# Product charter

## 1. Product definition

The project is an **open-source autonomous commerce optimization runtime**.

A merchant defines:

- an objective;
- a time horizon;
- a budget;
- business constraints;
- an action allowlist;
- an autonomy level;
- an evaluation cadence.

The runtime then performs a bounded loop:

```text
observe → diagnose → generate candidates → estimate impact
→ enforce policy → approve/execute → monitor → learn → repeat
```

The project should feel like an operating system for commerce decisions, not a chatbot with write access.

## 2. Core user promise

> Connect a store, state a measurable goal, define the boundaries, and receive a transparent stream of actions that move the store toward the goal without violating those boundaries.

Example:

```yaml
objective:
  metric: new_customers
  direction: maximize
  horizon_days: 30

budget:
  acquisition_and_promotion_usd: 10000

constraints:
  max_cac_usd: 40
  min_contribution_margin_pct: 25
  max_discount_pct: 15
  max_base_price_change_pct: 5

autonomy:
  search_merchandising: bounded_auto
  discounts: approval_required
  base_prices: approval_required
  ads: disabled
```

Important semantics:

- In the simulator, `acquisition_and_promotion` may include simulated ad spend.
- In a Shopify-only production installation, an acquisition budget initially means discount/promotion spend and on-site levers.
- It must not be represented as full paid-media budget control until an AdsProvider is connected.

## 3. Primary audiences

### GitHub and developer audience

- agent developers;
- search and recommender-system engineers;
- ML engineers;
- commerce platform engineers;
- researchers evaluating agentic decision systems;
- developers who want a realistic agent environment.

They need a zero-credential simulator, strong traces, benchmarks, clean interfaces, and easy local installation.

### Merchant and commercial audience

- Shopify merchants;
- small and medium retailers;
- marketplaces;
- commerce agencies;
- commerce SaaS vendors.

They need measurable outcomes, safety, approvals, reversibility, and low operational burden.

These audiences overlap but are not identical. The simulator and evaluation framework attract developers; the managed deployment and connectors create commercial value.

## 4. The launch demo

The demo must be understandable without explaining BM25, embeddings, LLM orchestration, or causal inference.

The user chooses a seeded store and enters:

> Acquire 200 new customers in 30 days with a $10,000 budget. Keep CAC under $40, contribution margin above 25%, and discounts below 15%.

The trace should visibly show:

1. current business state;
2. binding constraints;
3. diagnosed opportunities;
4. candidate actions;
5. estimated impact and uncertainty;
6. policy rejections;
7. approved or automatically executed actions;
8. daily KPI movement;
9. actions rolled back or stopped;
10. final goal outcome.

## 5. Product modes

### `DEMO`

- Synthetic commerce environment.
- Full bounded autonomy is allowed.
- No credentials or external writes.
- Reproducible with a seed.

### `SHADOW`

- Reads real store data.
- Generates plans and action proposals.
- No writes.
- Best first mode for every new integration.

### `APPROVAL_REQUIRED`

- Every external write pauses for explicit approval.
- The proposal includes effect estimate, risk, preconditions, and rollback.

### `BOUNDED_AUTO`

- Only actions explicitly allowlisted by policy may execute.
- Every action remains logged and reversible where the provider supports reversal.
- A global kill switch stops scheduling and execution.

There is no unrestricted mode in the MVP.

## 6. Initial objective templates

### A. Acquire new customers

Primary metric:
- first-time purchasers, measured from supported order/customer facts.

Constraints:
- promotion budget;
- max estimated CAC;
- minimum contribution margin;
- max discount;
- inventory availability.

Initial actuators:
- discount code/automatic discount;
- on-site search exposure;
- recommendation exposure;
- simulated ad budget in demo mode.

### B. Clear excess inventory

Primary metric:
- units sold or inventory days reduced for selected SKUs.

Constraints:
- minimum margin;
- max discount;
- no promotion below inventory safety floor;
- relevance floor for search/recommendation boosts.

Actuators:
- search boost;
- recommendation boost;
- bundle proposal;
- discount;
- price proposal.

### C. Improve search conversion

Primary metric:
- search-to-product-view, search-to-cart, or search-to-purchase conversion.

Constraints:
- relevance and diversity floors;
- latency budget;
- no excessive business boosting.

Actuators:
- hybrid retrieval parameters;
- synonym/attribute enrichment;
- ranker weights;
- product boost rules;
- query rewrite policy.

## 7. Safety principles

1. **Deterministic enforcement beats prompt instructions.**
2. **Observe before acting.**
3. **No write without a typed action.**
4. **No action without evidence and preconditions.**
5. **No budget math inside free-form LLM text.**
6. **No inventory count manipulation.**
7. **No use of protected traits for pricing or eligibility.**
8. **No secrets or PII in model prompts.**
9. **No silent action.**
10. **A no-op is a valid and often preferred decision.**

## 8. Non-goals for the first public release

Do not build these before the core loop works:

- autonomous refunds, returns, fulfillment, or payment operations;
- tax, legal, or regulatory decisions;
- supplier negotiation;
- inventory quantity writes;
- unrestricted ad campaign creation;
- personalized base pricing;
- customer-specific price discrimination;
- complete email/SMS campaign execution;
- custom deep-learning training pipelines;
- multi-region high availability;
- enterprise SSO;
- dozens of commerce connectors;
- a plugin marketplace;
- a full data warehouse;
- a generic multi-agent framework.

## 9. Success metrics for the project

### Developer adoption

- clone-to-demo under ten minutes;
- no external API key required for basic demo;
- benchmark command runs locally;
- trace makes every decision inspectable;
- third-party strategy or connector can be added without editing core modules.

### Product quality

- policy violations are deterministically blocked;
- writes are idempotent;
- failed writes do not corrupt action state;
- rollback works for supported actions;
- stale data blocks execution;
- simulation is reproducible;
- all external effects have audit records.

### Early commercial validation

- five real Shopify development stores complete read-only sync;
- three merchants review useful proposals;
- one merchant executes an approved discount action;
- one merchant installs the optional search widget;
- at least one measured outcome is attributable to a controlled intervention.
