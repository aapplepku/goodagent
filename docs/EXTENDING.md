# Extending The Runtime

Design guide, not authorization to implement a live provider. Read
[architecture](ARCHITECTURE.md) and [contribution policy](../CONTRIBUTING.md) first.

## Extend The Store Agents

The owner and shopper agents are the primary self-hosted product. The simulator
controller is a separate regression subsystem, described later in this guide.
Internal Python imports remain under `open_commerce`; public branding does not
rename modules, configuration keys or existing database identities.

Backend paths below start at `packages/backend/src/open_commerce/`.

| Change | Start here | Boundary to preserve |
| --- | --- | --- |
| Owner tool | `manager_agent/model_agent.py`, `registry.py`, `workspace_tools.py` | Validated input/output, server-provided tenant, durable receipts for mutations |
| Store operations | `manager_agent/operations.py`, `operations_models.py` | Bounded observations and drafts; no live commerce writes |
| Shopper product tool | `shopper_agent/product_tools.py`, `model_agent.py` | Authorized published/preview catalog, observed IDs, authoritative variants and integer-minor-unit prices |
| Shopping memory | `shopper_agent/memory_tools.py`, `service.py` | Account scope, grounded preference, committed-save receipt, opt-out and guest expiry |
| Model adapter | `manager_agent/model_provider.py`, `providers/openai_manager.py`, `runtime_services.py` | Typed provider contract, tool-call continuity, redaction and shared usage budgets |
| Background owner run | `manager_agent/runs.py`, `run_hooks.py`, `worker/jobs.py` | Tenant ownership, leases, cancellation fencing and completed-tool receipt reuse |
| Owner or shopper screen | `apps/web/src/` or `apps/shopper/src/` at the repository root | Separate sessions, generated contracts, recoverable pending/error states |

### Add A Read-Only Tool

1. Define strict Pydantic arguments and a bounded result. Reject unknown fields,
   oversized lists and unsupported values; do not accept identity or permissions
   chosen by the model. Use `core/tool_schema.py` for compatible tool schemas.
2. Implement the operation in the appropriate application service. Obtain tenant,
   account and catalog scope from authenticated server context. Every query remains
   tenant-scoped, even when the model supplies a valid-looking product identifier.
3. For owner tools, add the definition and argument mapping to
   `manager_agent/model_agent.py`; `_tool_registry()` associates the contract,
   permission category, verification requirement and handler. **Registry permission
   labels are metadata, not authorization enforcement:** the handler/service must
   check access and runtime restrictions before doing work.
4. For shopper tools, use `shopper_agent/product_tools.py` and the finite dispatch
   in `shopper_agent/model_agent.py`. Do not expose the owner registry or commerce
   mutation methods to the shopper model. Use authoritative lookup and comparison
   services rather than model-generated prices or variant options.
5. Return only the bounded facts the model needs. Treat catalog descriptions and
   tool results as untrusted data; omit credentials, raw uploaded rows and private
   customer details. Describe failed, pending and verified outcomes separately.
6. Add tests for valid input, invalid model arguments, cross-store/account IDs,
   upstream failure and result validation. Exercise the normal agent loop, not
   just the handler. A conversational success claim is not execution evidence.

For a local mutation, additionally follow the existing durable-run path: validate
preconditions, enforce the policy decision, derive an idempotency key, checkpoint
the request/result, record an audit trail and recovery metadata, and verify the
effect. Test duplicate delivery, cancellation and restart. Adding a tool must not
silently grant catalog publication, model activation, live payment or inventory
write authority. New external systems belong behind typed provider interfaces.

Useful regression starting points are `test_manager_model_agent.py`,
`test_manager_runtime_tools.py`, `test_shopper_product_tools.py` and
`test_shopper_memory_tools.py` under `packages/backend/tests/unit/`. Durable and
cross-account scenarios live in `tests/integration/`. Model-backed evaluations are
opt-in and budgeted; [the demonstration guide](FIRST_STORE_DEMO.md) distinguishes
structural assertions from human review of the generated answer.

## Historical Simulator Extensions

All backend paths below start at `packages/backend/src/open_commerce/`.

| Change | Start here | Evidence required |
| --- | --- | --- |
| Goal or domain model | `core/goals.py`, `core/actions.py`, `core/enums.py` | Pydantic validation, money/time units, tenant scope and serialization tests |
| Controller decision | `controller/detectors.py`, `planner.py`, `objectives.py`, `portfolio.py` | Goal-sensitive cases, missing evidence, infeasibility and unchanged full benchmarks or justified new version |
| Action type | Domain action union -> `controller/compiler.py` -> `policy.py` -> `durable_executor.py` | Negative compilation/policy, exact-hash approval, changed facts, duplicate dispatch, interrupted receipt/reconciliation and rollback tests |
| Provider | `core/providers.py`; `simulator/provider.py` and `simulator/durable.py` show current adapters | Capability contract, tenant-scoped reads, typed commands, idempotency and actual remote fault semantics |
| Search backend | `search/models.py` protocols, `qdrant_index.py`, `durable.py` composition | Tenant/instance/version isolation, stale payloads, hard filters, relevance gate and all five benchmark modes |
| Simulator scenario | `simulator/scenarios.py`, `models.py`, `catalog.py`, `demand.py` | Explicit seed/version, physical limits, deterministic goldens and all evaluation arms |
| UI/API | `api/`, repository-root `apps/web/src/` and `apps/shopper/src/`, generated SDK | OpenAPI freshness, strict types, actual Compose browser tests and error states |

Do not call adapters directly from a planner or route to bypass the executor.
An action is not finished when a happy-path provider call works: preparation,
reservation, approval, retries, reconciliation, measurement and rollback are part
of the contract. Never add an inventory-quantity write in the MVP.

## Existing Interfaces

`CommerceProvider` and `AdsProvider` are actual protocols in `core/providers.py`.
They contain typed commands/results and reconciliation. The current commerce
reads are `sync_catalog(cursor)` and `get_store_snapshot(as_of)`, with
`create_discount`, `disable_discount` and `set_variant_prices` commands.
Ads has `get_campaigns` and `set_campaign_budget`; only simulator campaigns exist.
Provider instances carry tenant context; write command envelopes include tenant
and idempotency identity. Do not invent a caller-selectable tenant header.

The actual retrieval interface is named `ProductSearchIndex`, alongside
`EmbeddingProvider` and `Reranker` in `search/models.py`. Wire a new implementation
through an explicit composition decision; the current durable service constructs
the Qdrant adapter and is not a plug-and-play connector marketplace.

## Conceptual Future Interfaces

These are capability sketches, **not importable APIs or implemented connectors**:

```text
CommerceProvider:
  read_products(tenant_id, cursor)
  read_orders(tenant_id, cursor)
  read_inventory(tenant_id, cursor)       # read only
  set_price(typed_command)               # executor only, future live adapter
  create_discount(typed_command)         # executor only

AdsProvider:
  read_campaigns(tenant_id, as_of)
  read_spend(tenant_id, window)
  set_campaign_budget(typed_command)     # future live adapter

SearchProvider:
  search(tenant_id, catalog_version, query, hard_filters, ranking_mode)

RecommendationProvider:
  recommend(tenant_id, catalog_version, anchors, hard_filters)
```

A standalone `RecommendationProvider` is not implemented; current similar/popular
recommendations belong to `DurableSearchService`. This sketch makes boundaries
discussable without adding speculative code. Future Shopify shadow mode starts
with reads and normalized observations, not OAuth/writes hidden inside this goal.

## Test A Change

Use the pinned development setup in [CONTRIBUTING](../CONTRIBUTING.md).
Run a focused test first, then `make check`, browser smoke for UI and isolated
recovery tests for durable behavior. Generated files are not hand-maintained:
`make openapi`, followed by `make check-openapi`. Submit a DCO-signed private
review branch. No release, registry upload or merge is part of this workflow.
