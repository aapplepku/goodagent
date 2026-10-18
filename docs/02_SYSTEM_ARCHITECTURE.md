# System Architecture

## 1. Architectural principle

Use a modular monolith plus worker, not premature microservices.

```text
Browser / CLI / Shopify extensions
                ↓
          FastAPI control plane
                ↓
     Application services and agent graph
        ┌───────┼─────────┐
        ↓       ↓         ↓
     Policy   Search   Optimization
        └───────┼─────────┘
                ↓
          Typed provider ports
       ┌────────┼──────────┐
       ↓        ↓          ↓
   Simulator  Shopify   Future Ads/Woo
```

PostgreSQL is authoritative. Qdrant is reconstructable search state. Redis is queue/lock/cache infrastructure, never the sole durable record of an action.

## 2. Deployable components

### `api`

FastAPI owns:

- REST/OpenAPI;
- authentication/authorization;
- goals, policies, runs, actions, approvals;
- search and event APIs;
- integration onboarding callbacks;
- provider webhook ingress;
- server-sent run events;
- health/readiness.

Routes are thin. They call application services and never contain policy or provider-specific business logic.

### `worker`

The Python worker owns:

- connector sync;
- embedding/index jobs;
- metric materialization;
- agent graph execution;
- action execution/reconciliation;
- outcome monitoring;
- periodic schedules.

Long-running work does not run inline in API requests.

### `web`

Next.js owns:

- simulator experience;
- goal wizard;
- operations dashboard;
- run trace;
- approvals;
- policy editor;
- search playground;
- integration onboarding.

It consumes generated API types and does not calculate authoritative budgets/policies.

### Shopify extensions

Later:

- theme app extension/app embed for project search/shopping UI;
- Web Pixel extension for consent-aware behavioral events.

### Infrastructure

- PostgreSQL: system of record and graph checkpoints;
- Redis: jobs, locks, short cache, SSE fan-out;
- Qdrant: dense+sparse product index;
- optional object storage later for large artifacts.

## 3. Backend package structure

Use one installable Python backend package to reduce workspace complexity while enforcing module boundaries.

```text
packages/backend/
├── pyproject.toml
└── src/open_commerce/
    ├── core/
    │   ├── money.py
    │   ├── metrics.py
    │   ├── goals.py
    │   ├── actions.py
    │   ├── policy_types.py
    │   ├── providers.py
    │   ├── events.py
    │   └── errors.py
    ├── application/
    │   ├── services/
    │   ├── commands/
    │   ├── queries/
    │   └── unit_of_work.py
    ├── persistence/
    │   ├── db.py
    │   ├── models/
    │   ├── repositories/
    │   └── migrations/
    ├── agent/
    │   ├── graph.py
    │   ├── state.py
    │   ├── nodes/
    │   └── prompts/
    ├── policy/
    │   ├── engine.py
    │   ├── rules/
    │   └── presets/
    ├── optimization/
    │   ├── opportunities/
    │   ├── compilers/
    │   ├── estimators/
    │   └── portfolio/
    ├── search/
    │   ├── documents.py
    │   ├── indexing/
    │   ├── query_understanding/
    │   ├── retrieval/
    │   ├── reranking/
    │   ├── recommendations/
    │   └── evaluation/
    ├── providers/
    │   ├── registry.py
    │   ├── simulator/
    │   └── shopify/
    ├── simulator/
    │   ├── clock.py
    │   ├── scenario.py
    │   ├── demand.py
    │   ├── economics.py
    │   └── scenarios/
    ├── llm/
    │   ├── protocol.py
    │   ├── deterministic.py
    │   └── adapters/
    ├── telemetry/
    ├── security/
    └── testing/
```

Deployable entrypoints:

```text
apps/api/
apps/worker/
apps/web/
packages/sdk-typescript/
extensions/
```

## 4. Full repository layout

```text
.
├── README.md
├── AGENTS.md
├── PLANS.md
├── Makefile
├── pyproject.toml
├── uv.lock
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── docker-compose.yml
├── .env.example
├── apps/
│   ├── api/
│   ├── worker/
│   └── web/
├── packages/
│   ├── backend/
│   └── sdk-typescript/
├── extensions/
│   ├── shopify-storefront-widget/
│   └── shopify-web-pixel/
├── openapi/
├── examples/
│   ├── scenarios/
│   ├── catalogs/
│   ├── goals/
│   ├── policies/
│   └── eval/
├── plans/
├── scripts/
├── tests/
│   ├── integration/
│   ├── contract/
│   ├── fault/
│   └── e2e/
├── infra/
└── docs/
```

## 5. Dependency direction

```text
core
  ↑
application
  ↑
policy / optimization / search / agent
  ↑
persistence / providers / API / worker
```

Specific rules:

- `core` imports standard library and Pydantic only.
- `core` defines provider protocols and domain errors.
- `persistence` implements repositories; domain objects do not import ORM models.
- `providers` map remote APIs to canonical models.
- `agent` coordinates application services and uses IDs/small state.
- `policy` never imports an LLM provider.
- `optimization` may consume typed snapshots but not raw provider payloads.
- `search` consumes canonical product documents.
- API routes do not call SQLAlchemy sessions or raw provider clients directly.
- frontend consumes OpenAPI, not database schemas.

Add import-boundary tests or a dependency linter.

## 6. Provider ports

Prefer typed methods over a generic `execute(dict)`.

### Commerce provider

```python
class CommerceProvider(Protocol):
    async def capabilities(self) -> CapabilitySet: ...
    async def sync_catalog(self, cursor: str | None) -> SyncPage: ...
    async def sync_orders(self, window: TimeWindow, cursor: str | None) -> SyncPage: ...
    async def sync_inventory(self, cursor: str | None) -> SyncPage: ...
    async def sync_discounts(self, cursor: str | None) -> SyncPage: ...
    async def fetch_resource(self, ref: ResourceRef) -> ResourceSnapshot: ...
    async def create_discount(self, command: CreateDiscountCommand) -> ProviderResult: ...
    async def disable_discount(self, command: DisableDiscountCommand) -> ProviderResult: ...
    async def set_variant_prices(self, command: SetVariantPricesCommand) -> ProviderResult: ...
    async def reconcile(self, execution: ExecutionRef) -> ReconciliationResult: ...
```

### Ads provider

```python
class AdsProvider(Protocol):
    async def capabilities(self) -> CapabilitySet: ...
    async def sync_campaigns(self, window: TimeWindow) -> list[CampaignSnapshot]: ...
    async def sync_spend(self, window: TimeWindow) -> list[SpendFact]: ...
    async def set_campaign_budget(self, command: SetCampaignBudgetCommand) -> ProviderResult: ...
    async def reconcile(self, execution: ExecutionRef) -> ReconciliationResult: ...
```

### Search

```python
class ProductSearchIndex(Protocol):
    async def upsert(self, docs: list[ProductSearchDocument]) -> None: ...
    async def delete(self, tenant_id: UUID, product_ids: list[str]) -> None: ...
    async def search(self, request: SearchRequest) -> SearchResponse: ...
```

### Model

```python
class ModelProvider(Protocol):
    async def generate_structured(
        self,
        *,
        task: str,
        messages: list[SafeModelMessage],
        output_schema: type[BaseModel],
        metadata: ModelCallMetadata,
    ) -> BaseModel: ...
```

The executor invokes only known provider methods selected by a typed compiled action. There is no arbitrary provider API tool.

## 7. Main data flows

### Simulator boot

```text
create scenario instance
  → generate deterministic catalog/history
  → persist canonical state
  → build product documents
  → dense+sparse index
  → materialize initial metrics
  → ready
```

### Initial Shopify sync

```text
integration authorized
  → enqueue bulk sync
  → stream remote data
  → validate/map canonical records
  → PostgreSQL upsert
  → build/index changed products
  → consistency checks
  → freshness watermark
```

### Incremental Shopify event

```text
verified webhook
  → deduplicate receipt
  → enqueue
  → reread authoritative object
  → normalize/upsert
  → update index/metrics
  → mark receipt processed
```

### Goal run

```text
schedule/manual trigger
  → one active-run lock
  → snapshot
  → opportunities
  → hypotheses/intents
  → compile/estimate
  → policy
  → portfolio
  → persist proposals
  → approval interrupt or execute
  → reconcile
  → monitor
```

### External write

```text
approved/auto-eligible action
  → lock action/entity
  → reread target
  → preconditions/policy/kill switch
  → reserve budget
  → record attempt
  → provider call
  → reconcile remote state
  → transition/audit
```

## 8. Transactional boundaries

Use PostgreSQL transactions for:

- action transition + audit event;
- budget reserve/commit/release;
- approval creation/decision;
- sync high-water marks;
- outbox/job publication where needed.

Do not hold a database transaction open during a slow external API call.

Pattern:

1. transactionally mark attempt and commit;
2. call provider;
3. transactionally persist result;
4. reconcile;
5. finalize state.

Use an outbox or job table when losing a post-commit queue publication would break correctness.

## 9. Workflow persistence

LangGraph manages orchestration checkpoints, but domain tables remain authoritative.

- graph state carries IDs, not full records;
- one thread per goal;
- one run ID per cycle;
- persist proposal before interrupt;
- persist execution attempt before provider call;
- on resume, nodes inspect domain state and become idempotent;
- graph deletion never deletes audit/action records.

## 10. Queueing and schedules

Use one lightweight Redis-backed Python worker framework selected during bootstrap.

Queues:

- `sync`;
- `index`;
- `agent`;
- `write`;
- `reconcile`;
- `metrics`;
- `low_priority`.

Rules:

- writes have low concurrency and per-integration/entity locks;
- webhook processing outranks backfills;
- jobs carry IDs only;
- retry categories are explicit;
- dead letters are inspectable;
- scheduler enqueues due goals and monitoring windows.

A durable workflow engine such as Temporal is a later option, not a v0.1 dependency.

## 11. Configuration

Use typed settings with precedence:

1. defaults;
2. environment/file;
3. deployment administrator;
4. tenant policy in database;
5. goal policy.

Secrets never enter ordinary settings serialization.

Environment groups:

- database/redis/qdrant;
- API/public URLs;
- auth;
- encryption key;
- model provider;
- Shopify app;
- telemetry;
- feature gates.

Fail startup on missing required production settings. Demo mode has safe local defaults.

## 12. Observability

Every request/job/run/action has:

- request ID;
- trace ID;
- tenant ID as opaque identifier;
- goal/run/action IDs;
- version metadata;
- structured event code.

Trace major nodes and provider calls. Redact tokens, PII, raw webhooks, and sensitive model inputs.

## 13. Scaling path

MVP scales vertically and with separate worker replicas.

Later:

- partition high-volume events;
- Qdrant tenant shard keys/dedicated collections;
- object storage for large snapshots/artifacts;
- dedicated execution service with write credentials;
- durable workflow engine;
- read replicas/materialized analytics;
- per-tenant rate controls.

Do not design the MVP as if it already serves millions of merchants.

## 14. Architectural acceptance criteria

- dependency tests prevent forbidden imports;
- no external write outside executor path;
- API and worker restart without losing authoritative state;
- Qdrant can be rebuilt from PostgreSQL;
- Redis loss does not erase action status;
- every provider capability is explicit;
- every tenant path is scoped;
- simulator and Shopify implement the same contracts;
- no paid model is required for demo;
- one command launches all local components.
