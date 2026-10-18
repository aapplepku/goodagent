# Data onboarding

New stores use [Products -> Preview -> Ready to share](SELF_SERVICE_SETUP.md), with
20 MiB staged CSV uploads, editable mapping and explicit catalog publication.
The smaller chat upload described below remains a compatibility path; its catalogs
cannot bypass the reviewed self-service publication gate.

The explicit legacy demo starts with a guided business and data interview. The tenant-level
onboarding draft is shared across manager channels and contains only bounded profile
answers and non-secret source metadata.

## Manager flow

### Browse the published catalog

Open **Browse catalog** in the operator sidebar (`/manager/catalog`) or the
shopper sidebar (`/catalog`, sign-in required). Both pages read the same verified
active upload as search, with product images, title/brand/ID filtering, categories,
alphabetical sorting and bounded pagination. Index completion publishes the browse
catalog automatically; no separate page-build step is required. Pages check for
updates every five seconds while open. The operator page includes the filename,
source fingerprint, publication time and catalog ID.

Pending or failed uploads are reported separately from the published catalog.
The previous verified catalog remains browsable until replacement verification
succeeds. Without a published upload, neither page substitutes simulator products.
Shopper homepage suggestions also retain the published catalog during replacement.
Cart actions stay explicit and revalidate current price, stock and reservations.

The bundled Amazon Berkeley Objects sample has **48 listings**. The fictional
sample and the Amazon sample are different datasets; a count of 48 does not mean
an Amazon upload failed. ABO titles/images are sourced; sample prices, inventory
and engagement are synthetic. The browser displays file-provided source notes as
data, not independently verified claims.

`GET /v1/manager/catalog` requires the local operator/owner role;
`GET /v1/shopper/catalog` requires a valid shopper session. Both accept `q`
(title/brand/product-ID substring, at most 200 characters), `category` (exact leaf
category), `sort` (`title` or `title_desc`), `offset`, and `limit` (1-48, default 24).
They return published catalog identity, separate latest indexing state, categories,
filtered count and products. Pages outside the current result range return page one.
No migration, model invocation or additional external write is involved.
The included ABO thumbnails are local, with matching SHA-256 checks on both apps.
The existing browser security policy blocks other image origins; arbitrary remote
image URLs are not fetched by the server and may display as unavailable until
their assets are mirrored through a separately reviewed intake process.

### Setup

1. Name the workspace and briefly describe the business.
2. Name the primary outcome and priority shopper surfaces.
3. Provide a catalog source or explicitly choose **No data yet**.
4. Provide pseudonymous engagement events or explicitly skip them.
5. Choose draft-only or approval-required operation.
6. Review and edit the collected answers, then confirm the workspace.

The UI presents eight prompts because the workspace name and business summary are
separate, as are the catalog and engagement decisions. Less urgent details use safe,
editable defaults: mixed manager role, manual full refresh, balanced responses,
conversion/search-success metrics, and relevance/availability/privacy guardrails.

The manager asks one material question at a time from a finite typed registry. A
configured model may choose the next eligible field and phrase an acknowledgement;
the application validates its selection and falls back deterministically. Raw
answers and uploaded rows are not provided to that question-selection call. It can
collect a CSV profile or non-secret Snowflake/object-storage identifiers. It must
never ask for a password, private key, access token, raw customer record, email,
phone number, or address.

Choosing **No data yet** completes onboarding in limited exploration mode. Search,
recommendation, and buy-it-again channels can discuss and draft objectives, but the
workspace cannot claim catalog indexing, model training, measurement, or activation.

## Catalog CSV

Use **Attach catalog CSV** beside the manager chat input, or use the Data panel.
The richer [Amazon Berkeley Objects catalog](../apps/web/public/abo-catalog.csv)
is the recommended image-backed demo file. It contains 48 CC BY 4.0 source
listings across grocery, home, office, apparel, pet, beauty, and other categories.
Prices, inventory, ranking fields, ratings, and the matching
[engagement export](../apps/web/public/abo-engagement.csv) are deterministic
synthetic demo values. The engagement rows are pseudonymous and contain no Amazon
customer or review data. Full provenance, attribution, license, and rebuild details
are in the [dataset bundle](../examples/datasets/amazon-berkeley-objects/README.md).
The smaller fictional [catalog](../apps/web/public/sample-catalog.csv) and
[engagement export](../apps/web/public/sample-engagement.csv) remain available for
quick tests. Shopify also publishes an official
[sample product CSV](https://help.shopify.com/csv/product_template.csv).

The onboarding upload accepts UTF-8 CSV up to 512 KiB, 64 columns, and 10,000
rows. Every file is profiled transiently and retains:

- filename, byte and row counts;
- column names and detected canonical mappings;
- missing required fields and structural warnings;
- a SHA-256 content fingerprint and profile timestamp.

For a valid catalog, bounded normalized product, variant, price, availability, and
ranking-signal fields are also persisted in PostgreSQL. The raw CSV is discarded
and is never sent to the conversation model. A durable background job reconstructs
the search documents and writes their tenant/catalog-version projection to Qdrant.
The new catalog becomes active only when the indexed product count matches; until
then, the previous ready catalog continues serving. Engagement uploads now retain
allowlisted events for [local ranking](ENGAGEMENT_RANKING.md), not raw CSV or queries.
Old profile-only uploads require re-uploading. Native Shopify exports use the
currency prompt and variant-aware [importer](SHOPIFY_INTAKE.md).

Minimum catalog fields:

| Canonical field | Required | Purpose |
| --- | --- | --- |
| `product_id` | yes | Stable product identity; `handle` and `URL handle` are recognized aliases |
| `title` | yes | Shopper-visible product name |
| `description` | recommended | Semantic retrieval text |
| `category` | recommended | Filtering and diversity |
| `variant_id`, `sku` | recommended | Variant identity and diagnostics |
| `price`, `currency` | recommended | Eligibility and merchandising analysis |
| `inventory_quantity` | recommended | Availability filtering; no quantity writes are enabled |
| `image_url` | optional | Shopper presentation; the runtime does not fetch arbitrary URLs |
| `updated_at` | recommended | Incremental-load watermark |

Catalog text is untrusted data. Normalization and indexing treat it as content,
never instructions, and the text is not included in manager-model context.

## Engagement events

Engagement is optional. It improves popularity measurement, ranking evaluation,
and later consent-compatible personalization. A useful event export contains:

| Canonical field | Required | Purpose |
| --- | --- | --- |
| `event_type` | yes | For example `search`, `product_view`, `add_to_cart`, or `purchase` |
| `occurred_at` | yes | UTC event time |
| `product_id` | yes | Catalog join key |
| `event_id` | recommended | Deduplication |
| `anonymous_id` or `session_id` | recommended | Pseudonymous behavior grouping |
| `query_id`, `position` | optional | Search attribution and offline evaluation |

Files with direct-identifier headers such as email, phone, name, address, or IP
address are rejected. Pseudonymous identifiers can still be personal data and
require an appropriate consent, retention, and deletion design.

## Mapping document

For nonstandard schemas, start from
[`examples/onboarding/data-contract.md`](../examples/onboarding/data-contract.md).
Provide column names, types, meanings, update behavior, sample values that contain
no customer or production data, and the intended canonical mapping. A repository
Markdown document is preferable to pasting raw records into chat. A future document
attachment tool can validate this contract directly; the current draft records only
its safe filename.

## Snowflake design

The current manager records these non-secret fields only: account identifier,
warehouse, database, schema, table or view, read-only role, cadence, and optional
watermark column. It does not establish a connection.

For a production connector:

- authenticate a service identity with OAuth or a rotated key pair held in an
  encrypted secret manager, never chat or onboarding JSON;
- grant the connector role `USAGE` only on the selected warehouse, database, and
  schema, plus `SELECT` on allowlisted views/tables;
- expose a stable view with only necessary columns instead of broad warehouse
  access;
- use `updated_at` or Snowflake change tracking for incremental reads, while keeping
  the authoritative cursor in PostgreSQL;
- set statement timeouts, row/byte limits, query tags, and cost controls;
- test the connection separately before any schedule can become active.

Snowflake documents [application authentication](https://docs.snowflake.com/en/developer-guide/sql-api/authenticating),
[OAuth](https://docs.snowflake.com/en/user-guide/oauth-snowflake-overview),
[access-control privileges](https://docs.snowflake.com/en/user-guide/security-access-control-privileges),
and the read-only [`CHANGES` alternative](https://docs.snowflake.com/en/user-guide/streams-intro).

## Scheduling design

The saved cadence is currently an inactive draft. The worker indexes an explicitly
uploaded catalog snapshot, but it does not poll Snowflake, object storage, or local
CSV files in this slice.

The intended worker path is:

```text
find due tenant source
  -> acquire tenant/source lease
  -> create idempotent sync job for the logical window
  -> read a bounded page with a read-only connector
  -> stage and validate canonical records
  -> atomically promote a version
  -> rebuild the tenant-scoped search projection
  -> commit cursor, quality report, and audit event
```

Retries reuse an idempotency key derived from tenant, source, resource, and logical
window. The cursor advances only after durable promotion. PostgreSQL remains the
source of truth; Redis delivers work and Qdrant remains reconstructable.

A practical starting policy is hourly catalog incrementals plus a daily full
reconciliation. Engagement can load hourly or every six hours depending on event
volume. File uploads are snapshots and cannot refresh automatically until placed in
versioned object storage or replaced by a warehouse connector.

## Current limitations

- no credential capture or connection test;
- no production Snowflake or object-storage adapter;
- no scheduled worker job or incremental cursor;
- no raw-file retention;
- no engagement-event import beyond structural profiling;
- no automatic source refresh, model training, ranking activation, or production
  relevance claim.

Those operations must remain visibly inactive until their provider, policy,
idempotency, audit, and recovery paths are implemented and qualified.
