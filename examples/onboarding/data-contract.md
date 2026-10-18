# Commerce data contract

Use this template for schema discussion. Do not include credentials, customer PII,
or raw production rows.

## Ownership

- Tenant/store:
- Data owner:
- Source system:
- Refresh expectation:
- Retention expectation:

## Catalog source

- Source kind: CSV / Snowflake / object storage
- Account and warehouse, if applicable:
- Database, schema, and table/view:
- Read-only role:
- Stable product key:
- Stable variant key:
- Incremental watermark column:

| Source column | Type | Canonical field | Nullable | Meaning / update behavior |
| --- | --- | --- | --- | --- |
|  |  | `product_id` | no |  |
|  |  | `title` | no |  |
|  |  | `description` | yes |  |
|  |  | `category` | yes |  |
|  |  | `variant_id` | yes |  |
|  |  | `sku` | yes |  |
|  |  | `price` | yes |  |
|  |  | `currency` | yes |  |
|  |  | `inventory_quantity` | yes | Read-only input |
|  |  | `image_url` | yes |  |
|  |  | `updated_at` | yes |  |

## Engagement source (optional)

- Decision: provide / skip
- Consent basis:
- Pseudonymous identity strategy:
- Retention window:
- Database, schema, and table/view:
- Incremental watermark column:

| Source column | Type | Canonical field | Nullable | Meaning / update behavior |
| --- | --- | --- | --- | --- |
|  |  | `event_id` | yes | Deduplication key |
|  |  | `event_type` | no |  |
|  |  | `occurred_at` | no | UTC |
|  |  | `product_id` | no | Catalog join key |
|  |  | `anonymous_id` | yes | Pseudonymous only |
|  |  | `session_id` | yes | Pseudonymous only |
|  |  | `query_id` | yes |  |
|  |  | `position` | yes |  |

## Data-quality rules

- Expected row volume:
- Maximum acceptable duplicate rate:
- Required-field completeness:
- Allowed event types:
- Price/currency validation:
- Product deletion or tombstone behavior:
- Late-arriving event window:

## Approval

- Reviewer:
- Review date:
- Notes:
