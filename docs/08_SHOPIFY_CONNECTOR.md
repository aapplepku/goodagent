# Shopify Connector

## 1. Scope

The Shopify connector has four stages:

1. local development-store connection;
2. read-only data synchronization;
3. shadow-mode proposals;
4. approved bounded writes.

It does not, by itself, control paid acquisition. A real “acquire customers with a marketing budget” loop requires an ads connector in addition to Shopify.

## 2. Authentication modes

Support two modes behind one credential interface.

### A. Custom app token — development/self-hosted single store

The operator creates a custom app in a Shopify development store and supplies:

- shop domain;
- Admin API access token;
- selected scopes.

Store the token encrypted. This is the fastest path for local integration tests.

### B. OAuth — public/multi-tenant deployment

Implement a standard standalone OAuth install flow:

```text
merchant enters shop
  ↓
validate canonical *.myshopify.com host
  ↓
generate state/PKCE material
  ↓
redirect to Shopify authorization
  ↓
callback with code/state/hmac
  ↓
validate callback
  ↓
exchange code
  ↓
store encrypted offline token + expiry/refresh metadata
  ↓
register webhooks
  ↓
enqueue initial sync
```

Because public app token requirements continue to evolve, isolate token acquisition/refresh behind:

```python
class ShopifyCredentialProvider(Protocol):
    async def get_valid_access_token(self, integration_id: UUID) -> SecretStr: ...
    async def refresh_if_needed(self, integration_id: UUID) -> TokenMetadata: ...
```

Build refresh-token support from day one. Never expose tokens to frontend JavaScript, logs, graph state, or an LLM.

## 3. Initial scopes

Request only what the enabled features need.

Suggested staged scopes:

### Read-only shadow

- products/catalog read;
- inventory read;
- orders read;
- discounts read where needed.

### Approved writes

- product write for variant price updates;
- discount write for discount creation/deactivation.

Do not request customer write, order write, fulfillment, refund, theme write, or inventory write scopes in the MVP.

Order history may be limited by Shopify's default scope/window. Treat older-history access as an optional capability and do not make onboarding depend on it.

Access to protected customer data requires explicit review and minimization. The connector must function in a degraded aggregate mode when customer-level fields are unavailable.

## 4. Capability discovery

At installation, store a capability matrix:

```python
class ShopifyCapabilities(BaseModel):
    can_read_catalog: bool
    can_write_prices: bool
    can_read_inventory: bool
    can_read_orders: bool
    can_read_historical_orders: bool
    can_read_customer_level_data: bool
    can_read_discounts: bool
    can_write_discounts: bool
    web_pixel_installed: bool
    storefront_extension_enabled: bool
```

The agent may only generate action types whose required capabilities are true.

## 5. API client

Create a dedicated adapter:

```text
packages/backend/src/open_commerce/providers/shopify/
├── auth.py
├── client.py
├── graphql.py
├── rate_limit.py
├── capabilities.py
├── mappers.py
├── sync/
│   ├── catalog.py
│   ├── inventory.py
│   ├── orders.py
│   └── discounts.py
├── webhooks/
│   ├── routes.py
│   ├── verify.py
│   ├── handlers.py
│   └── register.py
├── actions/
│   ├── discounts.py
│   ├── prices.py
│   └── reconcile.py
└── tests/
```

Use a thin GraphQL client with:

- API-version configuration;
- request IDs;
- cost/throttle metadata;
- bounded retries;
- timeout;
- typed normalized errors;
- response validation;
- structured logs with no query variables containing sensitive data.

Do not let domain code depend on Shopify GraphQL types.

## 6. Initial synchronization

### Catalog

Use GraphQL bulk operations for the full import.

Fields:

- product and variant GIDs;
- titles, descriptions, vendor/brand, category, tags;
- options;
- prices and compare-at prices;
- status;
- media references;
- inventory item references;
- update timestamps.

Process JSONL as a stream. Do not load the entire catalog into memory.

### Inventory

Resolve current inventory by variant/location as needed. Store snapshots and an aggregate available quantity. Preserve location detail only when required.

### Orders

Sync the accessible recent window. Normalize:

- order ID/time;
- line items;
- quantities;
- gross/net amounts;
- discounts;
- refunds;
- currency;
- pseudonymous customer reference if legally and technically available;
- new-versus-returning indicator only when supportable.

Do not store names, addresses, emails, phones, notes, or raw customer payloads unless a later feature has a justified need and explicit authorization.

### Discounts

Import active discount metadata necessary to avoid collisions and understand stacking.

### Sync bookkeeping

For each resource:

- source cursor;
- high-water mark;
- started/completed time;
- row counts;
- failures/dead letters;
- remote/source version;
- last successful freshness status.

After full sync, compare source counts and run consistency checks.

## 7. Webhooks

Register app-specific subscriptions and process:

- app uninstalled;
- product create/update/delete;
- inventory level update;
- order create/update/cancel;
- refund create;
- relevant discount changes if available;
- mandatory compliance/data requests.

Webhook route rules:

1. read raw request body;
2. verify signature before JSON parsing;
3. enforce payload limit and content type;
4. deduplicate using webhook ID/topic/shop;
5. persist minimal receipt;
6. enqueue asynchronous processing;
7. return quickly;
8. reread authoritative remote data for material updates;
9. record processing status and dead-letter failures.

An uninstall webhook immediately disables credentials, schedules secret deletion, stops new runs, and preserves only legally permitted audit data.

## 8. Behavioral events and storefront surface

To optimize this project's own search/recommendations, add:

- a consent-aware Web Pixel extension for standard shopper events;
- a theme app extension/app embed for the search/chat/product-discovery UI.

Events of interest:

- search submitted;
- product viewed;
- product added to cart;
- checkout started;
- checkout completed;
- project-specific impression/click events.

The theme extension must be explicitly activated by the merchant. Avoid direct theme-file mutation.

Search boosts change only results returned by the project's search API and rendered by its extension. Do not imply control of Shopify's internal/native marketplace ranking.

## 9. Discount writes

Initial supported commands:

```python
class ShopifyCreateDiscountCommand(BaseModel):
    action_id: UUID
    title: str
    code: str | None
    percentage: Decimal | None
    fixed_amount_minor: int | None
    starts_at: datetime
    ends_at: datetime
    product_ids: list[str] | None
    minimum_subtotal_minor: int | None
    combines_with: DiscountCombinationPolicy
```

Execution flow:

1. reread active discounts and target products;
2. validate code/title collision;
3. re-evaluate margin and budget;
4. invoke the appropriate code or automatic discount mutation;
5. store returned Shopify GID;
6. reread the discount;
7. mark reconciled;
8. schedule activation/expiration monitoring.

Rollback disables or deletes the exact remote discount, based on its state and API semantics.

First-order-only eligibility can require additional customer/segment capabilities. Do not claim it is enforced unless the connector can prove it.

## 10. Price writes

Use Shopify's supported bulk variant update mutation for small bounded batches.

Command:

```python
class ShopifySetVariantPricesCommand(BaseModel):
    action_id: UUID
    product_id: str
    changes: list[VariantPriceChange]
```

Each change includes:

- variant ID;
- expected current price;
- proposed price;
- currency;
- optional compare-at price treatment;
- exact rollback price.

Flow:

1. fetch current product/variants;
2. ensure expected prices match;
3. ensure variant set and currency match;
4. enforce price/margin/delta policies;
5. execute one bounded mutation;
6. inspect user errors;
7. reread all variants;
8. classify success, partial failure, or uncertain result;
9. automatically stop on partial mismatch and require reconciliation.

MVP policy:

- approval required;
- no more than 10 variants per action;
- no price change without known cost when margin policy requires it;
- no automatic base-price action;
- no compare-at price manipulation designed to create deceptive discounts.

## 11. Idempotency and reconciliation

Shopify GraphQL mutations do not remove the need for application-level idempotency.

For creation actions:

- create a deterministic app-owned marker/title/metafield where appropriate;
- search for an existing remote object before retry;
- store provider object ID immediately;
- treat timeout-after-send as uncertain;
- reconcile before retrying.

For updates:

- compare expected before state;
- record exact response;
- reread after state;
- do not retry if the desired state is already present.

## 12. Rate limits and backpressure

The client must:

- inspect GraphQL cost metadata;
- throttle based on currently available capacity;
- limit per-shop concurrency;
- back off on throttling;
- prioritize webhooks/reconciliation above low-priority analytics syncs;
- expose queue lag and sync lag metrics.

Bulk initial imports and live incremental processing use separate queues.

## 13. Data mapping

Keep source identifiers and normalized identifiers:

```text
integration_id
source_type = shopify
source_shop
source_gid
normalized_entity_id
source_updated_at
synced_at
source_payload_hash
```

Mapping must be idempotent and resilient to product/variant deletion.

Money:

- Shopify decimals → `Decimal`;
- database/API boundary → integer minor units plus currency;
- never use binary float.

## 14. Local development

Provide:

```bash
make shopify-dev-setup
make shopify-sync
make shopify-shadow-run
```

Document:

- creating a Shopify development store;
- generating custom app credentials;
- selecting minimal scopes;
- filling `.env.local`;
- adding seeded products/orders;
- using a tunnel for webhook testing;
- removing the integration and credentials.

Never commit credentials or paste them into issue templates.

## 15. Integration tests

Use three layers:

1. mapper/unit tests with fixtures;
2. HTTP contract tests using a mock Shopify GraphQL server;
3. opt-in live tests against a development store.

Live tests must:

- use clearly prefixed test products and discounts;
- never run against a production shop;
- require `ALLOW_LIVE_SHOPIFY_TESTS=true`;
- default to read-only;
- clean up created discounts;
- restore changed prices;
- emit a test audit report.

## 16. Definition of done

### Shadow connector

- secure token storage;
- capability discovery;
- bulk catalog sync;
- recent order/inventory/discount sync;
- verified/deduplicated webhooks;
- freshness dashboard;
- goal run can consume Shopify snapshot;
- no write path can execute in shadow mode.

### Approved writes

- approved discount can be created and reconciled;
- rollback can disable it;
- approved small price update can execute and restore prior values;
- stale/precondition mismatch blocks execution;
- timeout ambiguity triggers reconciliation;
- app uninstall disables the integration;
- every action has a complete audit chain.
