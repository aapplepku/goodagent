# Current Local Architecture

Start with the [canonical controller and trust-boundary architecture](ARCHITECTURE.md).
This companion focuses on deployment, transactions and operational interfaces.

The diagram describes the simulator implementation, not the future connector roadmap.

```text
Browser workspace
       |
       | same-origin, bounded JSON requests
       v
Next.js runtime proxy -----> FastAPI application
                                |
                                v
                     PostgreSQL authoritative records
                       ^         |              |
                       |         | durable jobs | catalog state
                       |         v              v
                Controller <--- Worker       Qdrant index
                       ^         ^              |
                       |         | Redis        | rebuildable retrieval
                       |         | delivery     v
                       |                   Search service
                       |
  observe -> detect -> deterministic planner -> typed intent
       -> compiler -> policy -> approval -> durable executor
                                            |
                                 simulator effect + receipt
                                            |
                               reconcile -> measured outcome
```

PostgreSQL stores goals, runs, observations, opportunities, intents, compiled
actions, estimates, policy decisions, exact-hash approvals, attempts, request
receipts, budget accounts/ledger, simulator state/commands, interventions,
measurement jobs, outcomes, audit, traces and kill-switch policy. Workflow jobs
carry identifiers; process-local objects are reloaded views, not authoritative state.

The local implementation uses explicit database-backed workflow nodes and ARQ
delivery. It does not claim to use LangGraph or a LangGraph PostgreSQL checkpointer.
The original numbered architecture documents contain that earlier design option.

## Consistency boundaries

Tenant-scoped transactions and PostgreSQL advisory locks order state changes.
Budget row locks and idempotent ledger operations protect reservations and actual
settlement. Request keys replay stored responses; mismatched payload reuse fails.

Execution has three boundaries: prepare an attempt/reservation, commit a simulator
effect with its receipt, then reconcile/finalize the action. An interrupted prepared
attempt rechecks policy/target state; an existing effect is reconciled, not blindly
dispatched again. Simulator state and receipts share a database transaction. A
future remote provider would not share this atomicity and needs its own fault evidence.

Redis coordinates delivery and worker health. Pending and expired leased jobs are
rediscovered in PostgreSQL. The worker is explicitly assigned one local tenant;
this is not an implemented hosted multi-tenant scheduler.

Qdrant stores versioned tenant/instance/catalog search projections, not business
truth. Results recheck current authoritative catalog facts, relevance and hard
constraints. Dense vectors use deterministic signed hashing, not a downloaded
neural embedding model. Sparse retrieval is term-frequency/IDF style, not full BM25.

## Provider boundary

Domain actions and policy do not import HTTP, UI, Qdrant or commerce SDKs. Typed
provider interfaces live in `open_commerce.core.providers`. Only the simulator
adapter is executable in this release. Its advertised capabilities include
simulated discounts, bounded prices, campaign budgets and internal search exposure.
The planner does not currently propose every supported typed action category.

There are no credential stores, OAuth routes, merchant webhooks, Shopify writes,
advertising integrations, payments, fulfillment, refunds or inventory-quantity
writes. Future connector notes specify design constraints only. Adding a connector
requires a separate scope decision, capability contracts, safety review and fault tests.

## API and client

`openapi/openapi.json` is generated from FastAPI. `packages/sdk-typescript` combines
generated schemas with an `openapi-fetch` typed convenience client. The browser
does not receive the internal service URL or provider credentials.

Important route groups are `/v1/goals`, `/v1/runs`, `/v1/actions`, `/v1/policy`,
`/v1/simulator`, `/v1/search`, `/v1/catalog` and `/health`. Mutation requests require
an idempotency key where declared by the schema. Approval requires the exact action
hash. `/v1/runs/{run_id}/events` returns persisted SSE events and accepts Last-Event-ID
for resumption; it is a finite event page, not an indefinitely subscribed stream.

Errors use the documented safe envelope and request ID. The API is local-demo
operator access, not bearer-token or session authentication. Tenant IDs are process
settings, not caller-selectable authorization headers.
