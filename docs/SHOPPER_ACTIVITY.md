# Shopper activity and ad-hoc monitoring

The shopper app has **Shopping activity** in its sidebar. The operator app shows
**Shopper logs & monitors** in the Activity drawer. Both refresh while open; monitor
evaluation itself runs in the existing worker even when no browser is open.

## Data and privacy

Instrumented events: chat requests, hosted catalog-search calls, successful memory
saves and rejected save attempts, catalog browsing, cart changes, checkout previews, and
test-checkout confirmations.
Each has an event type, outcome, duration, timestamp, and result count when applicable.
The data dictionary reports available fields and observed per-type counts. Activity is
operational telemetry, not the imported engagement dataset and not a revenue source.
Memory-save duration covers validation and persistence; empty results are measured only on
successful hosted catalog-search tool calls. Deterministic fallback searches are not
included in that metric. Chat fallback is a separate outcome, counted with errors in
error-rate monitors. HTTP validation/domain failures after authentication are errors.

No chat text, raw query, preference content, payment details, usernames, or account IDs
are returned to the store view or the model. Rows are account/tenant scoped internally.
Shoppers can inspect and configure only their own activity; the operator can inspect
store-wide redacted events and configure store-wide monitors. Personal rules are not
listed in the store view. Self-service operator routes require authenticated store
membership; only the explicit legacy-demo profile uses the local operator context.
This is still an experimental application, not production security qualification.

Events are collected from now forward; there is no invented historical backfill.
Telemetry delivery is best effort so an outage cannot turn a completed cart command into
a retry. Collector failures enter the structured server log without request contents.
These are not complete financial/audit logs. Existing commerce audit records are unchanged.

Deleting shopping data removes personal events, rules, evaluations and their
configuration receipts. The existing account version advances in the same tenant
write transaction. API instrumentation and agent tools retain the server-captured
version from their original request and check it again inside the write transaction.
Stale tools fail without a verified-success claim; stale best-effort telemetry is
discarded. Expired, disabled or merged-away guest accounts cannot write personal
activity, even through older internal callers that omit the version argument.
Fresh requests after deletion can record activity for an active account. Store-wide
operator rules, guest-turn quota receipts, memory opt-out receipts and checkout
audits are not deleted by this operation. A deletion cannot recall model context
already sent or undo a transaction committed before it; it is not universal
cancellation of all accepted commerce requests. Internal extensions must pass the
captured account version to obtain the delayed-work fence, not just liveness checks.

## Chat examples

Shopper:
- "Show my recent shopping activity and what data you collect."
- "Create a log view named Empty searches for my searches with no results."
- "Monitor my search empty-result rate at 25 percent or higher over an hour, minimum
  5 searches, checking every 5 minutes."

Operator, in any agent channel:
- "Inspect shopper activity and suggest monitoring based on available events."
- "Monitor store chat error rate above 10 percent over an hour, minimum 20 chats,
  checking every 5 minutes."
- "Pause the Empty searches monitor."

The tools inspect the data dictionary and compile requests into validated named views.
The same name updates a rule. A null threshold means a log-only filtered view. Unsupported
fields need additional instrumentation; an LLM cannot install code, SQL, scripts, event
payload schemas, or arbitrary tracking. At most 5 personal rules per account, 20 store rules.
Use the drawer's pause/resume control or chat to update an existing rule.

## Monitor semantics

Supported metrics: event count, error/fallback percentage, search empty-result percentage,
and nearest-rank p95 duration in milliseconds. Threshold comparisons use `>=`. Rate
denominators cannot be prefiltered to errors or empty results. Empty-result rates exclude
failed searches; no successes means insufficient data, not a 100-percent empty rate.
Minimum samples default to 5. Windows range from 5 minutes to 30 days, intervals from
1 minute to 24 hours (default 5 minutes). Each evaluation is capped at 5,000 events;
overflow is explicitly insufficient data rather than a misleading sampled metric.

Rules, evaluations, definitions-at-evaluation, last and next check times persist in
PostgreSQL. The worker checks due rules on its maintenance loop, rotating across
active self-service stores in bounded batches; the legacy profile uses its local tenant.
Database locking prevents duplicate evaluation by multiple workers. Restart resumes due
rules, without replaying every missed historical interval. Paused and log-only rules are
not scheduled. An overdue next-check timestamp means the worker has not completed a new
evaluation; after a one-minute scheduling grace the UI labels it **check overdue**
instead of displaying the old healthy state. Results stay in-app: no email, SMS,
webhooks, push notifications, or automatic recovery actions.

Raw operational events and evaluation records are pruned after 30 days by the worker;
retention cleanup is delayed if the worker is stopped. Rule definitions remain until
updated or explicitly deleted, as do idempotent configuration receipts. Personal
rules and receipts are also erased with shopping-data deletion or guest retirement.
Frozen release-security evidence is
unrelated and is not pruned or modified.

## API and migration

Migration `0019_shopper_activity` adds `shopper_activity`, `activity_rules`, and
`activity_checks`; it does not change existing catalog, accounts, or memory.

```text
GET  /v1/shopper/activity
POST /v1/shopper/activity/rules
GET  /v1/manager/activity
POST /v1/manager/activity/rules
```

Writes require `Idempotency-Key`. Shopper routes require the account session cookie;
operator routes resolve authenticated membership (or the explicit legacy context).
The model never supplies an
account or tenant identifier. `inspect_shopping_activity` and `configure_activity_monitor`
are available through the respective scoped agent runtimes. Generated SDK methods are
`shopperActivity`, `configureShopperActivity`, `managerActivity`, and `configureManagerActivity`.
