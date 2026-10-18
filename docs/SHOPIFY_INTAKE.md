# Read-only Shopify catalog intake

The adapter feeds the existing verified indexing pipeline. It never modifies Shopify
or migrates orders/customers. No test store has been supplied: verification is local
CSV and mocked GraphQL only. OAuth installation and scheduled sync are not implemented.

## CSV first

Upload a native Shopify export in store setup or operator chat. Choose currency when prompted;
ordinary exports lack reliable per-row currency. Supported: USD, EUR, GBP, CAD, AUD.
The importer groups handles, preserves variants, skips image-only rows, strips HTML,
and excludes draft/archived/unpublished products. First image becomes primary.
Currency participates in the fingerprint. Generic CSVs remain compatible.

Both legacy `Handle` / `Variant Price` headers and current `URL handle` / `Price`
headers are recognized. Setup review shows row-numbered warnings for excluded
draft, archived or unpublished products. A catalog with no published, priced
products cannot be confirmed. Missing prices on actual variants remain errors;
image-only continuation rows do not create extra variants. Confirmation stages
the reviewed products for indexing; it does not enable shopper sharing.

For mixed schemas, native publication fields (`Status`, `Published`, or
`Published on online store`) take precedence so adding a generic column cannot
bypass exclusions. Without those fields, explicit generic variant-ID or currency
columns retain generic normalization. The legacy `Handle` / `Variant Price` pair
always keeps Shopify semantics. Headers alone cannot establish export provenance;
check the product/variant preview before confirming a transformed CSV.

Store setup supports 20 MiB; the older chat attachment path supports 512 KiB.
Both retain limits of 10,000 rows and 64 columns. Missing quantity means unknown
availability, not unlimited stock. Browser image policies apply. Catalog text is
never an instruction.

## Prepared test-store connection

Obtain an authorized test-store Admin token with `read_products` and no write scopes.
Configure the ignored environment file, never chat or Git:

```dotenv
OPEN_COMMERCE_SHOPIFY_CATALOG_ENABLED=true
OPEN_COMMERCE_SHOPIFY_SHOP_DOMAIN=your-test-store.myshopify.com
OPEN_COMMERCE_SHOPIFY_ADMIN_ACCESS_TOKEN=<read-only-test-token>
```

Restart the runtime. In Data > Shopify, check connection then explicitly confirm import.
The operator can also inspect/import the configured source in chat. It is bound to the
local tenant; models cannot supply hosts, tokens, queries or write commands.

Fixed GraphQL queries use `2026-07`. Scopes, exact host, no redirects, time/response
limits and complete product pagination are checked. Over 200 variants on one product
rejects the whole import, not a partial catalog. Maximum 10,000 products. Only published
active products, prices and primary images are read; inventory is not synchronized.
Fetch/index failure leaves the previous usable catalog serving.

The internal `manager_csv` key remains the compatibility name for the active-upload
slot; Shopify metadata/fingerprint identifies its source, not a live commerce connector.
Operator APIs: `POST /v1/manager/connectors/shopify/check` and `/import` (idempotent).
Only safe status/counts are returned, never tokens or provider error bodies. No inventory,
order, payment, fulfillment or product writes. Do not use production credentials yet.

References: [product CSV](https://help.shopify.com/en/manual/products/import-export/using-csv),
[authorization](https://shopify.dev/docs/apps/build/authentication-authorization),
[scopes](https://shopify.dev/docs/apps/build/authentication-authorization/manage-access-scopes).
