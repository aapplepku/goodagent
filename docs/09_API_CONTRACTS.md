# API Contracts

## Reviewed catalog import

`ImportReview.review_fingerprint` identifies the persisted upload, store, import,
mapping, and currency. A valid pending review returns `sha256:` followed by 64
lowercase hexadecimal characters. Legacy closed reports may return null.

`POST /v1/merchant/imports/{import_id}/confirm` requires authenticated store
membership, `Idempotency-Key`, and this JSON body:

```json
{ "expected_review_fingerprint": "sha256:0000000000000000000000000000000000000000000000000000000000000000" }
```

The all-zero value above illustrates the format only; send the exact value from
the displayed review. Missing or malformed values return HTTP 422. A changed
review, cancelled import, or conflicting request key returns HTTP 409; expired
pending uploads return HTTP 410. Store and import mismatches cannot authorize confirmation. Comparison
and staging run under the existing tenant write lock. Conflicts do not erase the
upload or create an index job. Fetching the latest review does not confirm it.

Exact committed retries return the saved response. A different key with the same
accepted fingerprint does not stage a second index job. Closed legacy reports
remain readable; old id-only receipts and tokenless confirmation are not silently
upgraded. Deploy regenerated clients and API together, and refresh pending reviews
after upgrade. Import confirmation never enables store sharing.

## Store-operator conversation

The store-operator application retains the tenant-scoped `/manager` routes for
compatibility:

```text
POST   /v1/manager/workspace/bootstrap
GET    /v1/manager/workspace
POST   /v1/manager/workspace/reset
GET    /v1/manager/status
POST   /v1/manager/threads
GET    /v1/manager/threads
GET    /v1/manager/threads/{thread_id}
PATCH  /v1/manager/threads/{thread_id}
DELETE /v1/manager/threads/{thread_id}/messages
POST   /v1/manager/threads/{channel_id}/replies
GET    /v1/manager/threads/{channel_id}/messages/{root_message_id}/replies
POST   /v1/manager/threads/{thread_id}/messages
POST   /v1/manager/threads/{thread_id}/runs
GET    /v1/manager/runs/{run_id}
GET    /v1/manager/runs/{run_id}/events?after=0
POST   /v1/manager/runs/{run_id}/cancel
POST   /v1/manager/threads/{thread_id}/datasets/profile
GET    /v1/manager/memories
DELETE /v1/manager/memories/{memory_id}
GET    /v1/manager/commerce/overview
```

Bootstrap/create/update/clear/reply/message/profile/delete operations require
`Idempotency-Key`. Workspace bootstrap idempotently starts the finite interview and
creates only the selected starter-agent channels when onboarding completes; legacy
completed profiles retain the original defaults. Clearing a channel removes its
messages, replies, working memory, and periodic summaries while retaining tenant-level
long-term preferences and onboarding state. Reply roots must belong to the
same tenant and channel, and replies cannot nest. Thread responses keep working
memory separate from explicit long-term and immutable periodic memory. Agent steps
are safe summaries, not hidden reasoning. Complex discovery tools are explicitly
simulated and read-only in this slice. See [MANAGER_AGENT.md](MANAGER_AGENT.md).

Workspace reset accepts only `{ "confirmation": "RESET" }`. It clears manager-only
conversation, memory, onboarding, and browser-recoverable workspace state; catalog,
search, simulator, and shopper records are outside its deletion boundary. The
persisted `status_refresh_minutes` setting defaults to five, accepts 0-60, and can
be changed by a validated status-agent tool call.

Run creation returns 202 after persisting the user message. Creation and cancellation
require `Idempotency-Key`; repeated submissions reuse the run, and one active run per
conversation is enforced. Thread details include `active_run`. Events return an
ordered page, `next_cursor`, and current run status; poll with `after=next_cursor`.
No provider checkpoint, hidden reasoning, credentials, or recovery commands are
public. Cancellation/clear/reset fence future tools and completion. The legacy
message endpoint uses the same engine, returning a completed reply or a busy response
when background work continues. Index serving metadata distinguishes the latest job
from the previous usable projection during rebuilds.

## Shopper conversation

```text
POST   /v1/shopper/auth/register
POST   /v1/shopper/auth/login
POST   /v1/shopper/auth/logout
GET    /v1/shopper/me
GET    /v1/shopper/discovery
GET    /v1/shopper/conversations
GET    /v1/shopper/conversations/{conversation_id}
GET    /v1/shopper/memories
DELETE /v1/shopper/memories/{memory_id}
POST   /v1/shopper/chat
GET    /v1/shopper/cart
POST   /v1/shopper/cart/items
PATCH  /v1/shopper/cart/items/{line_id}
DELETE /v1/shopper/cart/items/{line_id}
POST   /v1/shopper/checkout/preview
POST   /v1/shopper/checkout/confirm
```

Discovery is authenticated and tenant-scoped. It exposes readiness and bounded
starter prompts from the active manager-owned catalog only; it does not expose
manager messages or memory. Shopper chat and memory deletion require
`Idempotency-Key`. Cart changes and checkout operations also require an
`Idempotency-Key`; prices, currency, account identity, tenant identity, and
inventory facts are always resolved server-side. Checkout preview binds the
exact cart version, current catalog versions, current prices, and local inventory
holds. Confirmation accepts only the finite local test methods `test_success`
and `test_decline`; it cannot accept card data or arbitrary provider tokens.

Protected shopper requests accept optional UUID header `X-Shopper-Account-Id`.
Updated first-party clients bind it to the account owning the displayed view,
including cart/checkout, memory/preferences, activity, data deletion and session
revocation. The server authenticates the cookie and resolves the store first, then
compares this expectation before account-specific work or receipt replay. A mismatch
returns HTTP 401 without selecting another identity or clearing the new session's
cookie. The header is not included in existing command fingerprints.

Explicit account discovery (`GET /v1/shopper/me`) and session recovery can omit
the header to discover a new authenticated identity. Guest upgrade/login initiated
inside an existing view must include its expected guest identity before importing
that guest's progress. Normal sign-out includes the displayed identity; explicit
authentication transitions must not automatically replay a prior account's action.
Legacy clients that omit the header retain cookie-based behavior and lack this
account-intent safeguard. Deploy the updated API and shopper client together.

`POST /v1/shopper/auth/guest` returns `created: boolean` alongside `account`.
`true` means the committed operation created a guest and issued a new session;
`false` means it reused the valid current session without issuing a new cookie.
Initial store entry may accept either result. Explicit fresh-start recovery must
accept only `created: true`, otherwise leave recovery visible and offer a session
check. A missing flag from an older server is not evidence of a fresh visit.

Self-service shopper requests require an authorized store context. Missing,
unknown, inactive or unpublished stores, and expired previews without a shared
catalog fallback, return HTTP 404 with `STORE_UNAVAILABLE`. This is a store-wide
access denial: clients must stop displaying cached store products after receiving
it and offer explicit retry. It is not a logout instruction. An individual missing
product retains its ordinary resource error, such as `STORE_REQUEST_BLOCKED`; a
temporary 503 is not publication revocation. Slugs supplied by clients select a
context for validation, never grant store or merchant permissions.

The operator commerce overview is read-only. It returns observed inventory,
computed active reservations and sellable quantity, locally created demo orders,
and test-payment state. There is no source-inventory adjustment, refund,
fulfillment, shipping-address, or real-payment route.

Protected merchant and manager requests also accept an optional pair of UUID
headers: `X-Merchant-Owner-Id` and `X-Merchant-Store-Id`. Both must be supplied
together. They bind an operation to the authenticated owner/store that produced
the displayed screen, not to a browser-selected tenant. The server validates the
current session and membership first, then rejects a mismatched pair with HTTP
401 before reads, mutations or receipt replay. A mismatch does not clear the
replacement session cookie. Incomplete, malformed or duplicate headers return
422. Existing command fingerprints do not change.

The owner client captures the pair for SDK calls, manual requests and CSV uploads;
all descendants share that immutable session binding. A protected 401 hides the
old workspace and stops its requests. **Check session** or sign-in explicitly
discovers the current identity, without replaying old edits, uploads, reset or
sharing operations. Initial authentication/discovery remains unbound. Older
clients that omit the pair remain compatible but lack this intent safeguard.
Deploy the updated API and owner client together; no database migration is needed.
The explicit legacy-demo profile retains its local operator behavior.

## Current release-candidate contract

`openapi/openapi.json` is the executable local-demo contract. It includes the
simulator, manager/shopper agents, and local cart/test-checkout surface. The
broader design examples below are not a list of implemented live integrations or
production authentication. This release exposes no live-provider routes and
moves no real money.

API errors, including framework 404/405 and validation 422 responses, use the
documented `ErrorEnvelope`. The readiness endpoint deliberately returns its typed
dependency report on 503. Catalog listings report `index_status: not_checked` and
`active_action_count: null` when those facts have not been queried; listing a
product does not establish that Qdrant is healthy or current.

Search-rule inspection accepts `goal_context_id`. Direct rule creation/deletion
and HTTP controller evaluation are absent. Search writes go through compiled
controller actions; benchmarks run from the CLI.

`openapi-typescript` generates the SDK's complete `paths`, operations and component
types. `openapi-fetch` checks the convenience facade's request bodies, path/query
parameters, headers and inferred responses against them. There is no handwritten
copy of response schemas. Type generation is not runtime validation of arbitrary
JSON; the server validates responses with Pydantic. The client omits cookies and
rejects redirects. `make check-openapi` checks both artifacts without overwriting
stale files; `make openapi` deliberately regenerates them. The generator's
[Node API](https://openapi-ts.dev/node) and
[typed request interface](https://openapi-ts.dev/openapi-fetch/) document this tooling.

## 1. API principles

The backend exposes a versioned REST API with OpenAPI generation.

Rules:

- prefix all public endpoints with `/v1`;
- JSON request and response bodies;
- UTC ISO-8601 timestamps;
- integer minor units plus ISO currency for money;
- UUIDs for internal IDs;
- source IDs remain opaque strings;
- cursor pagination, not page numbers, for growing collections;
- `Idempotency-Key` required for user-triggered mutating operations;
- tenant identity comes from authenticated claims, never an arbitrary production header;
- development mode may support a fixed tenant explicitly;
- generate TypeScript types/client from OpenAPI;
- never return secrets, raw tokens, or unsafe provider payloads.

## 2. Common envelopes

### Error

```json
{
  "error": {
    "type": "policy_denied",
    "code": "MAX_DISCOUNT_EXCEEDED",
    "message": "The proposed discount exceeds the configured 15% limit.",
    "details": {
      "proposed_rate": "0.20",
      "maximum_rate": "0.15"
    },
    "request_id": "req_01J...",
    "retryable": false
  }
}
```

Error types:

- `validation_error`
- `authentication_error`
- `authorization_error`
- `not_found`
- `conflict`
- `precondition_failed`
- `policy_denied`
- `provider_error`
- `rate_limited`
- `temporarily_unavailable`
- `internal_error`

Do not expose stack traces or provider credentials.

### Cursor page

```json
{
  "items": [],
  "next_cursor": null
}
```

### Money

```json
{
  "amount_minor": 1299,
  "currency": "USD"
}
```

## 3. Authentication and tenancy

MVP supports:

- local demo mode with no external exposure;
- production OIDC/JWT mode;
- Shopify OAuth integration authorization as a separate concern.

Claims:

```json
{
  "sub": "user-id",
  "tenant_id": "tenant-uuid",
  "roles": ["owner"],
  "iss": "configured-issuer",
  "aud": "open-commerce-api"
}
```

The backend resolves tenant/roles into a `RequestContext`. Repository methods do not accept tenant ID from untrusted request bodies.

Role checks:

- viewer: read dashboards/traces;
- operator: create goals, approve R2 actions;
- owner: change policies, integrations, approve R3 actions;
- admin: deployment operations.

## 4. Health and metadata

```text
GET /health/live
GET /health/ready
GET /v1/meta
GET /v1/capabilities
```

`/health/ready` checks required dependencies without leaking details.

`/v1/meta`:

```json
{
  "version": "0.1.0",
  "commit": "abc123",
  "mode": "self_hosted",
  "api_version": "v1"
}
```

## 5. Integrations

```text
GET    /v1/integrations
GET    /v1/integrations/{integration_id}
DELETE /v1/integrations/{integration_id}
POST   /v1/integrations/{integration_id}/test
POST   /v1/integrations/{integration_id}/sync
GET    /v1/integrations/{integration_id}/syncs
```

Create simulator instance through simulator endpoints. Shopify:

```text
POST /v1/integrations/shopify/custom-token
POST /v1/integrations/shopify/oauth/start
GET  /v1/integrations/shopify/oauth/callback
POST /v1/integrations/shopify/{id}/register-webhooks
```

Custom-token request:

```json
{
  "shop_domain": "example.myshopify.com",
  "access_token": "secret",
  "requested_mode": "shadow"
}
```

The response never echoes the token.

Integration response:

```json
{
  "id": "uuid",
  "provider": "shopify",
  "display_name": "Example Store",
  "status": "active",
  "mode": "shadow",
  "capabilities": {
    "read_catalog": true,
    "write_prices": false,
    "write_discounts": false
  },
  "last_sync_at": "2026-09-03T22:00:00Z",
  "freshness": {
    "catalog": "fresh",
    "orders": "stale"
  }
}
```

Deletion means revoke/erase credentials and disable future activity. Preserve only required non-secret audit records.

## 6. Goals

```text
POST   /v1/goals
GET    /v1/goals
GET    /v1/goals/{goal_id}
PATCH  /v1/goals/{goal_id}
POST   /v1/goals/{goal_id}/activate
POST   /v1/goals/{goal_id}/pause
POST   /v1/goals/{goal_id}/archive
POST   /v1/goals/{goal_id}/run
GET    /v1/goals/{goal_id}/progress
```

Create request:

```json
{
  "name": "Acquire new customers",
  "objective": {
    "metric": "new_customers",
    "direction": "maximize",
    "target": "200"
  },
  "horizon": {
    "start_at": "2026-09-01T00:00:00Z",
    "end_at": "2026-09-30T23:59:59Z"
  },
  "budgets": [
    {
      "kind": "total_acquisition_and_promotion",
      "amount_minor": 1000000,
      "currency": "USD"
    }
  ],
  "constraints": [
    { "metric": "cac", "operator": "lte", "value": "40" },
    {
      "metric": "contribution_margin_rate",
      "operator": "gte",
      "value": "0.25"
    },
    { "metric": "discount_rate", "operator": "lte", "value": "0.15" }
  ],
  "autonomy": {
    "default_mode": "approval_required",
    "per_action": {
      "set_search_boost": "bounded_auto",
      "set_variant_price": "approval_required"
    }
  },
  "allowed_action_types": [
    "create_discount",
    "disable_discount",
    "set_search_boost",
    "set_campaign_budget"
  ],
  "schedule": {
    "cadence": "daily",
    "timezone": "America/New_York"
  }
}
```

The API validates:

- objective/constraint compatibility;
- metric support;
- provider capabilities;
- date horizon;
- currency consistency;
- action allowlist;
- autonomy not broader than tenant policy.

Natural-language drafting is separate:

```text
POST /v1/goals/draft
```

Request:

```json
{
  "text": "Acquire 200 new customers in 30 days with $10,000 and CAC under $40. Keep margin above 25% and discounts under 15%."
}
```

Response is a **draft** plus ambiguities/warnings. A human must explicitly create the goal.

## 7. Runs and traces

```text
GET  /v1/runs
GET  /v1/runs/{run_id}
GET  /v1/runs/{run_id}/trace
GET  /v1/runs/{run_id}/events
POST /v1/runs/{run_id}/cancel
POST /v1/runs/{run_id}/resume
```

Run response:

```json
{
  "id": "uuid",
  "goal_id": "uuid",
  "status": "awaiting_approval",
  "trigger": "scheduled",
  "started_at": "2026-09-03T12:00:00Z",
  "completed_at": null,
  "observation_snapshot_id": "uuid",
  "counts": {
    "opportunities": 4,
    "proposals": 3,
    "allowed": 1,
    "approval_required": 1,
    "denied": 1
  },
  "warnings": []
}
```

Trace response uses ordered steps:

```json
{
  "run_id": "uuid",
  "steps": [
    {
      "sequence": 1,
      "type": "observation",
      "status": "completed",
      "started_at": "...",
      "completed_at": "...",
      "summary": "Paid social CAC exceeded the goal ceiling.",
      "entity_refs": ["snapshot:uuid"],
      "safe_details": {}
    }
  ]
}
```

For live updates, `GET /v1/runs/{id}/events` is server-sent events. Event IDs are resumable with `Last-Event-ID`.

## 8. Actions and approvals

```text
GET  /v1/actions
GET  /v1/actions/{action_id}
POST /v1/actions/{action_id}/approve
POST /v1/actions/{action_id}/reject
POST /v1/actions/{action_id}/execute
POST /v1/actions/{action_id}/cancel
POST /v1/actions/{action_id}/rollback
GET  /v1/actions/{action_id}/audit
```

Action detail:

```json
{
  "id": "uuid",
  "type": "create_discount",
  "status": "awaiting_approval",
  "risk_tier": "r2_reversible_material",
  "summary": "Create a 10% discount for selected products for 72 hours.",
  "targets": [{ "type": "product_scope", "id": "scope-uuid" }],
  "before": {},
  "after": {
    "rate": "0.10",
    "duration_hours": 72
  },
  "expected_impact": {
    "metric": "new_customers",
    "point": "14",
    "lower": "5",
    "upper": "24",
    "method": "discount_elasticity_prior_v1"
  },
  "budget": {
    "estimated_cost_minor": 18000,
    "currency": "USD"
  },
  "policy": {
    "outcome": "require_approval",
    "reason_codes": ["RISK_TIER_REQUIRES_APPROVAL"]
  },
  "rollback": {
    "available": true,
    "summary": "Disable the created discount."
  },
  "expires_at": "2026-09-04T12:00:00Z",
  "version_hash": "sha256:..."
}
```

Approval request:

```json
{
  "version_hash": "sha256:...",
  "comment": "Approved for the weekend test."
}
```

Require an `Idempotency-Key`.

Execution endpoint is primarily for an approved action and operator-triggered retry after safe reconciliation. It cannot bypass policy.

Rollback creates a new linked action and returns `202 Accepted`.

## 9. Policies and kill switches

```text
GET  /v1/policy
PUT  /v1/policy
POST /v1/policy/validate
GET  /v1/policy/history
POST /v1/kill-switch/enable
POST /v1/kill-switch/disable
GET  /v1/kill-switch
```

Policy updates are versioned and require owner role. Existing approved proposals are invalidated when a relevant policy becomes stricter.

Kill-switch enable:

```json
{
  "scope": "tenant",
  "reason": "Unexpected discount behavior"
}
```

Enabling does not require confirmation beyond authenticated owner/operator permissions; it is designed for immediate safety. Disabling requires owner role and reason.

## 10. Store analytics

```text
GET /v1/metrics/summary
GET /v1/metrics/series
GET /v1/metrics/definitions
GET /v1/catalog/products
GET /v1/catalog/products/{product_id}
GET /v1/catalog/inventory
GET /v1/interventions
```

Series query:

```text
GET /v1/metrics/series?metric=new_customers&start=...&end=...&grain=day
```

Response states:

- definition/version;
- timezone;
- attribution model;
- freshness;
- values;
- completeness warnings.

## 11. Search and recommendations

```text
POST /v1/search
POST /v1/search/parse
POST /v1/search/evaluate
POST /v1/recommendations
POST /v1/events/batch
GET  /v1/search/rules
POST /v1/search/rules
DELETE /v1/search/rules/{rule_id}
```

Search request:

```json
{
  "query": "waterproof trail shoes under $150, no heavy insulation",
  "session_id": "anon-session",
  "filters": { "in_stock": true },
  "top_k": 20,
  "debug": false
}
```

Search response:

```json
{
  "query_id": "uuid",
  "interpretation": {
    "normalized_query": "waterproof trail shoes",
    "required_filters": {
      "max_price_minor": 15000,
      "in_stock": true
    },
    "excluded_attributes": {
      "insulation": ["heavy"]
    }
  },
  "results": [
    {
      "product_id": "p-1",
      "title": "Trail Runner GTX",
      "price": { "amount_minor": 12900, "currency": "USD" },
      "image_url": "...",
      "url": "...",
      "highlights": ["waterproof", "trail"],
      "score": "0.81"
    }
  ],
  "clarification": null,
  "relaxed_preferences": [],
  "ranking_version": "rank-v1"
}
```

Only authorized operator debug requests receive score decomposition.

Event batch:

```json
{
  "events": [
    {
      "event_id": "client-generated-id",
      "occurred_at": "...",
      "session_id": "anon-session",
      "type": "product_impression",
      "query_id": "uuid",
      "product_id": "p-1",
      "position": 1,
      "surface": "search"
    }
  ]
}
```

Cap batch size and deduplicate event IDs.

## 12. Simulator

```text
GET  /v1/simulator/scenarios
POST /v1/simulator/instances
GET  /v1/simulator/instances/{id}
POST /v1/simulator/instances/{id}/advance
POST /v1/simulator/instances/{id}/run-until
POST /v1/simulator/instances/{id}/reset
GET  /v1/simulator/instances/{id}/compare-baseline
```

Advance request:

```json
{
  "hours": 24,
  "run_agent_after_advance": true
}
```

Large run-until operations return a job ID and stream progress.

## 13. Webhooks

Shopify webhooks are provider-specific routes:

```text
POST /webhooks/shopify
```

Do not place them under tenant-authenticated `/v1`. Authenticate with the provider signature.

The internal normalized event ingestion endpoint is not publicly writable unless protected by a service credential.

## 14. Versioning and compatibility

- additive response fields are permitted;
- enum additions may affect strict clients, so document them;
- breaking changes create `/v2`;
- event schemas carry `schema_version`;
- action types carry versioned payloads;
- provider adapters declare supported API versions;
- database migrations are backward-compatible within one minor release when practical.

## 15. OpenAPI and SDK

CI must:

1. generate OpenAPI JSON;
2. compare it against the committed schema;
3. generate a TypeScript client;
4. fail on uncommitted changes;
5. run contract tests against the generated client.

Place:

```text
openapi/openapi.json
packages/sdk-typescript/
```

A Python client can follow after the core API stabilizes.

## 16. API acceptance criteria

- all mutating endpoints enforce role and idempotency;
- tenant ID cannot be selected in a production request body;
- money never uses JSON floating point;
- approval is bound to action version hash;
- kill switch endpoint blocks writes immediately;
- SSE can resume;
- OpenAPI generation is deterministic;
- generated TypeScript types compile;
- error codes are stable and documented;
- provider errors are normalized and redacted.
