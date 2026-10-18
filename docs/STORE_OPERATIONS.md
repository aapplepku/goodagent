# Everyday store operations

The operator agent now has six read-only business-report tools in every channel.
They read this store's persisted records, not a fictional dashboard. Use an
OpenAI-backed manager conversation for flexible tool selection; the deterministic
interpreter does not provide these new conversational reports.

## Start here

Open the manager and ask:

- "What needs my attention today? Give me the top three priorities."
- "Check my catalog for missing images, descriptions, duplicate SKUs and pricing issues."
- "Which variants are low on stock? Treat five units or fewer as low."
- "Are any stock observations older than two days?"
- "Review checkout problems and demo orders from the last seven days."
- "Compare shopper activity over the last 24 hours with the previous 24 hours."
- "Is this store ready to share? Are shoppers seeing the newest catalog?"

Follow up naturally: "Test search for those products", "Explain the stock issue",
or "Monitor search empty-result rate at 20 percent over an hour, minimum five
searches, checking every five minutes." The last example uses the existing durable
in-app monitor. Asking for a daily review does not schedule future reviews.
Short follow-ups retain the existing channel and reply memory.

## Small-business review

The everyday priorities below are based on established merchant workflows, not
speculative agent capabilities. Order/payment troubleshooting and customer service
are core daily work in [WooCommerce's order-management guide](https://woocommerce.com/document/managing-orders/).
Product, stock, order and performance reporting need explicit definitions and time
windows, as documented in [WooCommerce Analytics](https://woocommerce.com/document/woocommerce-analytics/).
Checkout recovery requires distinguishing genuine payment failures from unfinished
shopping, as described in [Shopify's abandoned-checkout guide](https://help.shopify.com/en/manual/orders/abandoned-checkouts).
Sources reviewed September 13, 2026.

| Merchant action | Agent support now | Boundary / next step |
| --- | --- | --- |
| Morning check and priorities | New daily brief with catalog, stock, checkout, activity and setup evidence | On demand, not an unattended operating schedule |
| Maintain product information | New audit identifies concrete product/variant IDs and quality flags | Correct source CSV, review, preview and explicitly publish replacement |
| Check stock and replenishment risks | New variant report uses latest observed stock minus active local holds; marks stale/unknown | Verify in source system; no inventory writes, demand forecast or purchase orders |
| Review orders and failed payments | New complete, time-windowed demo aggregates; currencies kept separate | Commerce panel for local detail; no refunds, real payment capture or fulfillment |
| Identify inactive carts | New count of nonempty carts unchanged for at least 24 hours | Not proof of abandonment; no customer targeting or recovery emails |
| Check store performance | New current/prior-window event counts and measured empty-search rate | Not revenue, unique-shopper conversion, attribution or ranking lift |
| Test product discovery | Existing catalog search, recommendations and candidate comparisons | Retrieval tests are not proof of relevance quality |
| Improve ranking | Existing engagement inspection and actual popularity/logistic training | Explicit evaluated-model activation remains in the Model panel |
| Plan merchandising or product copy | Model can draft review text grounded in returned facts and conversation | No invented product claims, discounts, certifications or publishing |
| Handle customer questions | Model can explain supported workflows or draft generic response text | No customer PII, contact lookup, messages sent, shipping promises or ticket integration |
| Watch failures | Existing named activity views, monitors, pause/resume and service status | Finite event fields, in-app notifications; no arbitrary tracking or external sends |
| Prepare or update a shared store | New persisted readiness report distinguishes indexed and shared versions | Preview, acknowledgements and publication remain explicit owner controls |
| Import from another platform | Existing reviewed generic/Shopify CSV intake | OAuth, automatic platform refresh and PIM connectors are not added here |

These gaps remain deliberate: supplier purchasing, fulfillment, returns/refunds,
tax/shipping configuration, paid marketing, customer outreach, and accounting
exports require real provider integrations, permissions and audited write flows.
The agent must describe these as unavailable, not simulate completed actions.

## Report definitions

- `review_store_day`: combines six sections and up to eight prioritized next
  actions, with up to three catalog and stock examples. Each section has its own
  observation time; it is not an atomic financial report.
- `audit_catalog_quality`: checks the latest indexed active catalog for empty
  descriptions, missing/failed images, missing categories, no variants, missing or
  duplicate SKUs, nonpositive prices, prices below known cost, and compare-at prices
  not above the selling price. Zero prices can be intentional. Missing costs are
  not guessed. Issue counts overlap and identify affected records per issue.
- `review_inventory_risks`: defaults to five units and 24-hour freshness. Future
  observations are ignored; only unexpired active reservations reduce availability.
  Missing observations remain unknown. Local demo purchases do not decrement source
  quantities, so the report cannot promise a warehouse balance or stockout date.
- `review_checkout_operations`: complete aggregates, not the Commerce panel's
  latest-50-row sample. Orders/payments use creation time and current status in the
  requested rolling UTC window. Paid demo totals are separate by currency. Cart
  counts are current snapshots. Processing older than 15 minutes is flagged across
  all ages. Commerce records lack preview/sample provenance, so all local test
  commerce is explicitly included, even when activity excludes test sessions.
- `review_shopper_performance`: current and previous equal rolling UTC windows,
  1-720 hours. Preview/sample events are excluded unless explicitly included.
  Empty-result percent requires at least five successful instrumented searches with
  recorded result counts; failed searches and missing counts are not denominators.
  No raw queries, account IDs, contact data, or customer text is returned.
  Previous-window retention coverage is explicit; even a fully retained window
  does not prove instrumentation was present throughout. Telemetry is best effort.
- `inspect_store_readiness`: persisted preview/checklist evidence, latest indexing
  state and indexed/shared catalog IDs. No new model ping, preview grant, or share
  mutation occurs. Legacy stores without setup records report unknown sharing
  readiness. AI check timestamps are historical, not continuous health verification.

Catalog inspection is capped at 10,000 products and 50,000 variants. Total counts
remain database aggregates; checked counts and incomplete coverage are explicit.
Individual audit/stock examples are limited to 1-25 (default ten). Raw descriptions,
attributes, filenames and image URLs are not model context; the audit receives
booleans and returns redacted, bounded product labels and IDs. Product labels are
untrusted data, not model instructions.

## Safety and operation

No new endpoints, migrations, credentials or packages are required. The existing
authenticated manager run routes deliver tool events and responses. Only the
server provides tenant identity. Tool arguments reject store/account IDs, SQL,
commands, paths and unsupported fields. All new tools are read-only and cannot
call commerce mutators. Existing budgets, cancellation and run isolation apply.

Restart the API and worker using the same local launcher/configuration to load the
new tools. Do not reset the store or replace its environment file. No catalog,
sharing state, customer record or historical release evidence changes on upgrade.

Validation includes pure report tests, scripted model tool/result continuity,
real PostgreSQL tenant and publication isolation, latest stock/hold handling,
time boundaries, test-traffic exclusion and totals beyond the old sample limit.
The historical release-security source-hash mismatch remains a separate gate;
this change does not refresh that qualification or claim production readiness.
