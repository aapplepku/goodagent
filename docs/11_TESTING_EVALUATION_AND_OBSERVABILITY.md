# Testing, Evaluation, and Observability

## 1. Quality strategy

This system can spend money and change prices. “The demo works” is not sufficient.

Testing layers:

```text
static analysis
  ↓
unit/property tests
  ↓
domain and policy tests
  ↓
provider contract tests
  ↓
integration tests
  ↓
fault-injection tests
  ↓
end-to-end tests
  ↓
offline ML/search evaluation
  ↓
shadow-mode production validation
```

No real write capability is enabled until lower layers pass.

## 2. Repository commands

Provide a root `Makefile`:

```bash
make bootstrap
make dev
make lint
make format
make typecheck
make test
make test-unit
make test-integration
make test-contract
make test-e2e
make benchmark-search
make simulator-golden
make openapi
make migrate
make seed
make check
```

`make check` is the full local gate, including live integration when dependencies are available. CI can split non-live checks from dependency-backed integration jobs.

Use lockfiles for Python and Node dependencies.

## 3. Python quality

- Ruff formatting/linting;
- mypy strict enough to catch untyped public APIs;
- pytest;
- pytest-asyncio;
- Hypothesis for policy/money/state-machine properties;
- coverage report, with higher expectations for domain/policy code than adapters.

Suggested thresholds:

- domain/policy/action compiler: 90% line coverage;
- overall backend: 80%;
- do not optimize for coverage numbers at the expense of meaningful cases.

## 4. TypeScript quality

- strict TypeScript;
- ESLint;
- formatter;
- unit/component tests;
- Playwright for end-to-end;
- generated OpenAPI client compilation;
- no `any` in public application code without a documented exception.

## 5. Unit-test matrix

### Money and metrics

- currency mismatch;
- rounding at half-cent boundaries;
- zero revenue;
- refund handling;
- discount cost;
- CAC with zero customers;
- margin definition/version;
- timezone/day boundaries.

### Goal validation

- unsupported objective;
- target outside horizon;
- incompatible currency;
- unknown metric/operator;
- autonomy broader than tenant policy;
- missing provider capability;
- infeasible explicit constraints.

### Policy

Cover every rule, exact boundaries, precedence, and multiple failures.

### Action compiler

- stale state;
- missing product;
- duplicate discount code;
- price precondition mismatch;
- unknown cost;
- mixed currency;
- excessive target count;
- rollback construction.

### State machine

Property test allowed transitions. Invalid transitions must fail.

### Simulator

- deterministic seed;
- no negative inventory;
- spend cannot exceed assigned campaign amount;
- demand decreases with price under fixed inputs;
- discount lowers contribution per unit;
- same action changes future metrics.

### Search

- tenant filter always present;
- exact terms;
- semantic query;
- filters;
- RRF tie-breaking;
- relevance gating;
- retry cap;
- hard constraints not relaxed.

## 6. Provider contract suite

Define abstract tests every connector must pass.

```python
class CommerceProviderContract:
    def test_capabilities(...)
    def test_catalog_pagination(...)
    def test_create_discount_is_idempotent(...)
    def test_price_precondition(...)
    def test_reconciliation(...)
    def test_normalized_errors(...)
```

A connector advertises only tested capabilities.

Contract fixtures must include:

- success;
- validation error;
- rate limit;
- timeout before send;
- timeout after send;
- partial result;
- authentication failure;
- deleted remote entity.

## 7. Integration tests

Use Docker Compose services:

- PostgreSQL;
- Redis;
- Qdrant;
- API;
- worker;
- web.

Tests:

- migrations from empty database;
- outbox/worker delivery;
- LangGraph checkpoint resume;
- approval interrupt/resume;
- budget reservation race;
- kill switch race;
- index upsert/search/delete;
- SSE reconnect;
- OpenAPI client.

Use Testcontainers or Compose depending on local/CI simplicity.

## 8. Fault injection

Required scenarios:

1. API process dies after action is persisted but before provider call.
2. Worker dies after provider succeeds but before local status update.
3. Provider times out after accepting request.
4. Redis unavailable.
5. Qdrant unavailable.
6. PostgreSQL primary restarts.
7. duplicate webhook delivery.
8. events arrive out of order.
9. Shopify token expires.
10. policy changes while approval is pending.
11. kill switch activates during execution.
12. remote product manually changes before execution.

Expected outcomes must be explicit. No test may accept duplicate writes.

## 9. End-to-end acceptance tests

### Simulator acquisition

- create seeded instance;
- create goal;
- run multiple cycles;
- see at least one allowed, one denied, and one approval action;
- satisfy or explicitly declare infeasibility;
- compare baseline;
- reset and reproduce.

### Approval

- proposal awaits approval;
- wrong role denied;
- correct role approves exact hash;
- mutate target state;
- execution fails precondition;
- new proposal/version generated.

### Kill switch

- enable;
- pending bounded-auto action does not execute;
- reads and audit still work;
- rollback remains available according to policy.

### Search

- natural-language request parsed;
- hybrid results returned;
- hard price filter honored;
- trace shows branches;
- behavior event accepted;
- no cross-tenant result.

### Shopify shadow

- sync dev store;
- process duplicate webhook once;
- compute snapshot;
- produce proposal;
- assert zero mutation calls.

### Shopify write — opt-in live test

- create prefixed test discount;
- reconcile;
- disable/rollback;
- update one test variant price;
- restore;
- emit audit report.

## 10. Offline controller evaluation

Create a scenario suite with fixed seeds and compare controller versions.

Metrics:

- objective attainment;
- total constraint violations;
- hard-constraint violations — must be zero;
- budget overspend — must be zero;
- cumulative contribution profit;
- number of actions;
- rollback count;
- unnecessary action rate;
- regret versus scenario oracle where available;
- LLM cost;
- wall-clock latency;
- reproducibility.

A controller change cannot merge if it introduces a hard violation on the golden suite.

Do not tune only to seed `42`; use train/dev/held-out seed groups.

## 11. Search evaluation

Covered in the search doc, but CI should have:

- tiny smoke dataset on every PR;
- larger benchmark nightly or manually;
- saved metrics by configuration;
- regression thresholds;
- per-query diff artifact;
- latency distribution;
- model/version metadata.

Do not allow business-goal boosts to improve revenue metrics while relevance/constraint metrics collapse.

## 12. Shadow-mode evaluation

Before enabling writes on a real store:

1. run for at least a configured observation period;
2. collect proposed actions;
3. compare with merchant/operator decisions;
4. measure:
   - proposal acceptance;
   - policy denial reasons;
   - estimated versus realized opportunities where observable;
   - data freshness;
   - false positive rate;
   - missing capability rate;
5. manually review high-risk cases;
6. enable only one action type at a time.

## 13. Experimentation

MVP outcome estimates are observational or simulator-based and must be labeled.

For real causal claims:

- randomize eligibility/exposure where possible;
- persist assignment before exposure;
- avoid cross-contamination;
- define primary/guardrail metrics before start;
- use an analysis appropriate for sequential monitoring;
- store experiment version;
- report uncertainty and sample size.

The runtime may initially propose experiments rather than claim causal lift.

## 14. Structured logging

Every log includes:

- timestamp;
- level;
- service;
- environment;
- request ID;
- tenant ID as opaque ID;
- run/action ID where relevant;
- event code;
- safe fields.

Never log:

- access tokens;
- authorization headers;
- cookies;
- raw customer data;
- raw Shopify webhook bodies;
- full prompts containing user/catalog data;
- unit cost in public logs when deployment policy forbids it.

Use redaction tests.

## 15. Metrics

### API

- request rate/latency/error by route;
- authentication/authorization failures;
- SSE connections;
- idempotency conflicts.

### Workers

- queue depth;
- oldest job age;
- retries;
- dead letters;
- job duration.

### Agent

- runs by state;
- node latency;
- LLM calls/tokens/cost;
- malformed structured outputs;
- proposals by type;
- allow/approval/deny counts;
- graph resume failures.

### Actions

- execution success/failure/uncertain;
- reconciliation lag;
- rollback rate;
- precondition failures;
- provider errors;
- budget reservations.

### Data

- sync lag by resource;
- webhook lag/duplicates/dead letters;
- index lag;
- metric completeness.

### Search

- QPS;
- p50/p95/p99 latency;
- no-result rate;
- retry rate;
- constraint satisfaction;
- click/ATC/purchase where available.

## 16. Tracing

Use OpenTelemetry spans:

```text
goal.run
├── snapshot.build
├── opportunities.detect
├── llm.hypotheses
├── actions.compile
├── impact.estimate
├── policy.evaluate
├── portfolio.select
├── approval.wait
└── actions.execute
    ├── provider.preflight
    ├── provider.write
    └── provider.reconcile
```

Search:

```text
search.request
├── query.parse
├── embed.query
├── retrieve.sparse
├── retrieve.dense
├── fuse.rrf
├── rerank
└── result.evaluate
```

Do not record sensitive payloads as span attributes.

## 17. Alerts

Initial alerts:

- any policy invariant violation attempt;
- budget ledger negative/overdrawn;
- external write uncertain beyond threshold;
- repeated reconciliation mismatch;
- token/auth failure;
- webhook dead-letter growth;
- stale order/inventory data;
- error-rate spike;
- kill switch activation;
- rollback failure;
- cross-tenant guard assertion.

For self-hosted demo, alerts appear in UI/logs. Hosted deployments can connect email/PagerDuty later.

## 18. Release gates

### Simulator release

- golden suite;
- zero hard violations;
- deterministic reset;
- complete trace;
- clean install.

### Shopify shadow beta

- security review;
- read-only scopes;
- webhook verification;
- tenant isolation;
- no mutation code reachable in shadow;
- deletion/uninstall behavior.

### Approved-write beta

- connector live tests;
- reconciliation;
- rollback;
- policy race tests;
- audit;
- explicit beta warning;
- per-tenant enablement.

### Bounded autopilot

- action-specific production evidence;
- low-risk reversible actions only;
- kill switch drills;
- budget race tests;
- monitor/rollback runbook;
- versioned policy defaulting to off.

## 19. Definition of done

- `make check` passes from a clean clone;
- controller golden tests prevent unsafe regressions;
- provider contract suite is reusable;
- process-kill tests prove no duplicate writes;
- structured logs and traces exist for a full run;
- dashboards expose freshness, policy, actions, and errors;
- live tests are opt-in and cannot target an unapproved store;
- release gates are documented and enforced.
