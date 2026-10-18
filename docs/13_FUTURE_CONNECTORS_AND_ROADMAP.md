# Future Connectors and Roadmap

## 1. Sequence principle

Add connectors based on the closed-loop use case, not logo count.

The first production objective “acquire new customers with a budget” needs:

```text
store/order data
+ shopper behavior
+ promotion controls
+ paid-channel controls
```

Therefore an ads connector creates more product value after Shopify than a second catalog connector.

Recommended sequence:

1. simulator;
2. Shopify;
3. Google Ads;
4. project search/storefront extension;
5. WooCommerce;
6. Meta Ads;
7. TikTok Shop and TikTok Ads;
8. Klaviyo/email;
9. BigCommerce;
10. Amazon Seller or other marketplaces only after demand.

## 2. Canonical capability model

```python
class Capability(str, Enum):
    READ_CATALOG = "read_catalog"
    WRITE_PRODUCT_CONTENT = "write_product_content"
    WRITE_PRICE = "write_price"
    READ_INVENTORY = "read_inventory"
    WRITE_INVENTORY = "write_inventory"
    READ_ORDERS = "read_orders"
    READ_CUSTOMER_COHORTS = "read_customer_cohorts"
    READ_DISCOUNTS = "read_discounts"
    WRITE_DISCOUNTS = "write_discounts"
    READ_BEHAVIOR_EVENTS = "read_behavior_events"
    WRITE_MERCHANDISING = "write_merchandising"
    READ_CAMPAIGNS = "read_campaigns"
    WRITE_CAMPAIGN_BUDGET = "write_campaign_budget"
    WRITE_CAMPAIGN_STATUS = "write_campaign_status"
```

Providers declare capabilities dynamically based on scopes and account status.

Goals, detectors, and actions declare required capabilities. Missing capability produces a visible degraded state, never an invented approximation.

## 3. Provider protocols

### Commerce

```python
class CommerceProvider(Protocol):
    async def capabilities(self) -> CapabilitySet: ...
    async def sync_catalog(self, cursor: str | None) -> SyncPage: ...
    async def sync_orders(self, window: TimeWindow, cursor: str | None) -> SyncPage: ...
    async def sync_inventory(self, cursor: str | None) -> SyncPage: ...
    async def create_discount(self, command: CreateDiscountCommand) -> ProviderResult: ...
    async def disable_discount(self, command: DisableDiscountCommand) -> ProviderResult: ...
    async def set_variant_prices(self, command: SetVariantPricesCommand) -> ProviderResult: ...
    async def reconcile(self, execution: ExecutionRef) -> ReconciliationResult: ...
```

### Ads

```python
class AdsProvider(Protocol):
    async def capabilities(self) -> CapabilitySet: ...
    async def sync_campaigns(self, window: TimeWindow) -> list[CampaignSnapshot]: ...
    async def sync_spend(self, window: TimeWindow) -> list[SpendFact]: ...
    async def set_budget(self, command: SetCampaignBudgetCommand) -> ProviderResult: ...
    async def set_status(self, command: SetCampaignStatusCommand) -> ProviderResult: ...
    async def reconcile(self, execution: ExecutionRef) -> ReconciliationResult: ...
```

### Messaging/lifecycle

```python
class LifecycleProvider(Protocol):
    async def draft_campaign(...) -> DraftResult: ...
    async def schedule_campaign(...) -> ProviderResult: ...
```

Sending remains approval-gated until consent/suppression/preview controls mature.

## 4. Google Ads connector

Why third:

- makes the acquisition-budget objective real;
- exposes campaign budgets and performance;
- creates closed-loop spend allocation.

MVP scope:

- read campaigns, budget, cost, clicks, conversions;
- map campaign/account/currency;
- update existing campaign budget only;
- no creative generation;
- no audience targeting;
- no new campaign creation;
- no conversion-action configuration.

Safety:

- budget increases approval required;
- percentage and absolute daily caps;
- account-level remaining goal budget;
- reporting delay buffer;
- minimum conversions;
- no automatic change to shared budget unless all dependent campaigns are understood;
- exact rollback amount;
- provider reconciliation.

Attribution:

- display Google Ads reported conversion and store order attribution separately;
- do not silently merge different definitions;
- configure the optimization metric source.

## 5. WooCommerce connector

Advantages:

- open merchant-controlled storefront;
- REST API supports catalog/orders;
- easier community adoption;
- project search widget can fully replace/control storefront discovery.

Challenges:

- version/plugin variability;
- arbitrary hosting reliability;
- SSRF/network risks;
- auth modes;
- data schema customization.

MVP:

- consumer key/secret;
- products/variations/orders/coupons;
- webhooks;
- price/coupon writes;
- no arbitrary plugin execution;
- strict base URL security.

Use the same contract suite as Shopify.

## 6. Meta Ads connector

Scope after Google Ads:

- read campaign/ad set performance;
- update existing daily/lifetime budgets within provider constraints;
- pause/resume;
- no autonomous targeting/creative in first version.

Be explicit about attribution windows and delayed/conversion-modeled data.

## 7. TikTok Shop connector

TikTok Shop is a marketplace/store connector, distinct from TikTok Ads.

Potential capabilities:

- products;
- inventory;
- orders;
- promotions;
- fulfillment/finance reads.

Important boundary:

- the runtime cannot replace TikTok's marketplace search/recommendation ranking;
- it can influence catalog quality, price, promotion, inventory, and ads through allowed APIs.

Implementation concerns:

- app registration/review;
- seller authorization;
- request signing;
- regional API differences;
- scope approval;
- webhook verification;
- policy/compliance.

Start read-only and build against sandbox/development facilities where available.

## 8. TikTok Ads connector

Separate package from TikTok Shop.

Initial goal:

- read campaign performance;
- adjust existing budget/status;
- strict daily caps;
- delayed-spend buffer;
- approval required.

Do not combine Shop and Ads credentials or capabilities into one opaque integration.

## 9. Email/lifecycle connector

Klaviyo or equivalent can support:

- draft new-customer offer campaign;
- segment preview;
- estimated audience;
- schedule/send with approval;
- suppression/consent checks;
- performance sync.

First version drafts only. Sending messages has brand, legal, and consent risks.

## 10. Inventory and replenishment

Future read/decision capabilities:

- demand forecast;
- days of supply;
- stockout risk;
- overstock detection;
- reorder proposal.

Do not add autonomous purchase orders early. Supplier commitments, lead times, minimum quantities, cash flow, and cancellation terms make this high risk.

Inventory quantity writes remain excluded until there is a compelling, bounded use case.

## 11. Pricing intelligence roadmap

### Stage 0 — recommendations

- estimate price sensitivity;
- propose bounded changes;
- approval only.

### Stage 1 — controlled experiments

- eligible product scope;
- randomization or safe switchback;
- margin floor;
- short horizon;
- monitoring;
- rollback.

### Stage 2 — learned elasticity

- hierarchical elasticity by category/product;
- uncertainty;
- seasonality;
- promotion interaction;
- out-of-distribution checks.

### Stage 3 — constrained optimizer

```text
maximize expected contribution/revenue/objective
subject to:
  margin floor
  max price change
  inventory
  fairness/policy
  action budget
  customer experience
```

Do not use individualized sensitive-trait pricing.

## 12. Search/recommendation ML roadmap

1. hybrid retrieval and simple reranking;
2. product co-visitation;
3. session-aware features;
4. product-level learning-to-rank;
5. personalized retrieval/ranking;
6. multi-objective ranker;
7. online experimentation;
8. contextual bandit for bounded merchandising actions.

Maintain a stable model-serving contract so the agent runtime does not depend on a specific model family.

## 13. Controller learning roadmap

MVP uses rules + conservative impact priors.

Then:

- action outcome table;
- hierarchical Bayesian priors;
- contextual action-value models;
- off-policy evaluation;
- contextual bandits for reversible low-risk actions;
- constrained reinforcement learning only much later and only in simulator/shadow before production.

The LLM is not the reinforcement-learning policy.

## 14. Workflow durability roadmap

MVP uses LangGraph persistence plus a Redis worker.

When jobs span days, many external callbacks, or complex retries:

- evaluate Temporal or another durable workflow engine;
- keep domain/action protocols unchanged;
- move scheduling/execution durability without rewriting business logic.

Do not introduce two workflow engines in v0.1.

## 15. Agent interoperability

Potential later interfaces:

- MCP server exposing safe read tools and proposal creation;
- UCP-compatible commerce operations where applicable;
- webhook/event API;
- TypeScript/Python SDKs.

An external agent may ask this runtime to search or propose an action. It must not bypass policy/execution gates.

Example MCP tools:

```text
get_goal_status
get_store_summary
search_products
list_opportunities
propose_discount
list_pending_approvals
```

No raw `execute_arbitrary_shopify_graphql` tool.

## 16. Plugin ecosystem

Extension points:

```text
connectors/
detectors/
impact_estimators/
action_compilers/
policy_rules/
search_retrievers/
rerankers/
simulator_scenarios/
UI panels/
```

Each plugin declares:

- API compatibility;
- capabilities;
- permissions;
- secrets;
- network access;
- action types;
- tests;
- maintainer.

Begin in-tree. External dynamic plugins come only after a secure package model.

## 17. Roadmap by release

### v0.1 — Agent-in-a-box demo

- simulator;
- goal/policy;
- autonomous simulated actions;
- trace UI;
- hybrid search;
- benchmark;
- Docker Compose.

### v0.2 — Shopify shadow

- custom-token and/or OAuth path;
- bulk sync/webhooks;
- normalized metrics;
- shadow proposals;
- storefront search playground.

### v0.3 — Approved Shopify writes

- discounts;
- bounded small price update with approval;
- reconciliation/rollback;
- audit;
- live dev-store tests.

### v0.4 — Real acquisition controller

- Google Ads read;
- budget proposals/writes with approval;
- cross-source metrics;
- delayed-spend safety;
- closed-loop acquisition goal.

### v0.5 — Bounded autopilot

- low-risk search boosts;
- discount disable/limited creation policy;
- campaign decreases/small adjustments if explicitly enabled;
- monitor/rollback.

### v0.6 — Ecosystem

- WooCommerce;
- provider SDK;
- plugin templates;
- community scenarios;
- hosted preview.

### v1.0

- hardened multi-tenant deployment;
- stable API/action schemas;
- migration/backup docs;
- security review;
- production reference deployments;
- governance and release policy.

## 18. What not to build yet

- unrestricted AI CEO;
- browser automation against merchant admin panels;
- arbitrary action scripting;
- autonomous refunds/fulfillment;
- autonomous supplier purchasing;
- custom foundation model;
- many chatty agents;
- eight shallow connectors;
- Kubernetes requirement;
- enterprise SSO before real users;
- fully individualized dynamic pricing;
- deep-learning ranker before events exist.

## 19. Definition of roadmap success

Each connector must unlock a tested goal or action, not just import data.

The project is succeeding when:

- external contributors can implement a provider from contracts;
- one goal can operate across multiple providers without provider-specific planner code;
- capability gaps are explicit;
- no connector weakens policy guarantees;
- real outcomes can be traced to exact actions and data sources.
