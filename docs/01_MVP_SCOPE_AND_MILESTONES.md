# MVP Scope and Milestones

## 1. Release ladder

Treat each stage as an independently demonstrable release.

| Release | Core outcome | Real external writes |
|---|---|---:|
| `v0.0.1-foundation` | Monorepo, domain schema, local stack | None |
| `v0.1.0-simulator` | Goal-conditioned closed-loop demo | None; simulator only |
| `v0.2.0-shopify-shadow` | Real Shopify data and proposals | None |
| `v0.3.0-shopify-approval` | Approved discounts and small price updates | Human-approved |
| `v0.4.0-acquisition` | Shopify + real ads budget control | Human-approved |
| `v0.5.0-bounded-autopilot` | Low-risk, reversible, policy-controlled actions | Explicitly allowlisted |

The public open-source launch should happen at `v0.1.0-simulator`. Do not wait for all integrations.

## 2. Practical schedule

For one experienced engineer using Codex carefully:

- simulator-first public demo: **2–3 focused weeks**;
- Shopify shadow alpha: **another 2–3 weeks**;
- approval-gated Shopify writes: **another 2–4 weeks**;
- first real ads connector and credible bounded autonomy: **roughly 8–12 focused weeks total**.

These are planning ranges, not promises. Nights/weekends often stretch calendar time. Release the simulator as soon as it is coherent, reproducible, safe, and well documented.

## 3. Milestone 0 — Foundation

Codex prompt: `codex/00_BOOTSTRAP_PROMPT.md`

### Deliverables

- Python `uv` workspace and one backend package;
- TypeScript `pnpm` workspace;
- FastAPI API;
- worker entrypoint;
- Next.js shell;
- PostgreSQL, Redis, Qdrant;
- Docker Compose;
- Alembic;
- structured logging;
- generated OpenAPI client;
- CI, lint, typecheck, tests, Makefile.

### Acceptance

From a clean clone:

```bash
cp .env.example .env
make bootstrap
docker compose up --build
make check
```

The dashboard shows service status, and no business logic has been prematurely added.

## 4. Milestone 1 — Core domain and persistence

Codex prompt: `codex/01_CORE_DOMAIN_AND_PERSISTENCE_PROMPT.md`

### Deliverables

- canonical money/metric/goal/constraint models;
- action intent and compiled-action types;
- action state machine;
- tenant-aware database schema and repositories;
- policy primitives;
- approval records;
- budget ledger;
- append-only audit trail;
- integration/credential metadata envelope.

### Acceptance

- every core object round-trips through PostgreSQL;
- invalid transitions fail;
- concurrent reservations cannot overspend;
- approvals bind to exact action hashes;
- tenant-isolation tests pass;
- no LLM or provider write exists.

## 5. Milestone 2 — Deterministic simulator

Codex prompt: `codex/02_SIMULATOR_PROMPT.md`

### Deliverables

- provider protocols;
- virtual clock;
- seeded catalog/customers/campaigns;
- daily demand and economics;
- normalized events;
- idempotent simulated discount, price, search-boost, and campaign-budget commands;
- acquisition, excess-inventory, and search-conversion scenarios;
- no-agent baseline.

### Acceptance

- seed `42` is reproducible;
- same actions produce the same output;
- economic identities hold;
- write commands change future outcomes;
- no API key is needed.

## 6. Milestone 3 — Search and recommendations

Codex prompt: `codex/03_SEARCH_AND_RECS_PROMPT.md`

### Deliverables

- product normalization;
- local dense embeddings;
- sparse/BM25 vectors;
- Qdrant hybrid retrieval with RRF;
- structured filters;
- relevance gating;
- bounded business boosts;
- optional reranker;
- result critique/retry;
- basic recommendations;
- events and benchmark CLI.

### Acceptance

- exact and semantic queries work;
- all searches are tenant-filtered;
- hard constraints are enforced;
- business objectives cannot promote irrelevant products;
- sparse, dense, hybrid, and reranked configurations are benchmarked.

## 7. Milestone 4 — Controller and safety loop

Codex prompt: `codex/04_CONTROLLER_AND_POLICY_PROMPT.md`

### Deliverables

- deterministic opportunity detectors;
- optional LLM hypothesis layer;
- typed action compilers;
- impact estimators;
- deterministic policy engine;
- budget-aware portfolio selection;
- LangGraph orchestration with PostgreSQL checkpointing;
- approval interrupts;
- one idempotent executor;
- monitoring/outcome loop;
- kill switches;
- scheduler.

### Acceptance

The acquisition scenario performs repeated:

```text
observe → propose → deny/approve/execute → measure → adapt
```

It produces at least one policy denial, one successful bounded action, one measured outcome, and a complete resumable trace, with zero hard-policy violations across the golden scenario suite.

## 8. Milestone 5 — Public simulator UI

Codex prompt: `codex/05_API_AND_FRONTEND_PROMPT.md`

### Deliverables

- scenario selector;
- goal wizard;
- virtual-time controls;
- goal/KPI/budget dashboard;
- run trace;
- action approval/detail;
- policy editor;
- kill switch;
- search playground;
- baseline comparison;
- Playwright flows.

### Acceptance

A stranger can clone and experience the core idea in under five minutes without a store or paid model key.

This is the public `v0.1.0` release.

## 9. Milestone 6 — Shopify shadow

Codex prompt: `codex/06_SHOPIFY_SHADOW_PROMPT.md`

### Deliverables

- encrypted custom-app token path;
- versioned GraphQL client;
- capabilities;
- bulk catalog/order/inventory/discount sync;
- verified, deduplicated webhooks;
- normalized Shopify snapshot;
- product indexing;
- shadow proposals;
- uninstall/data cleanup.

### Acceptance

A Shopify development store syncs and creates useful proposals while the system proves that no Shopify mutation is reachable.

## 10. Milestone 7 — OAuth and storefront surface

Codex prompt: `codex/07_SHOPIFY_OAUTH_AND_STOREFRONT_PROMPT.md`

### Deliverables

- secure OAuth/token refresh;
- staged scopes;
- app-specific webhook registration;
- merchant-activated theme app extension;
- consent-aware Web Pixel extension;
- public shopper search API;
- storefront events and search UI.

### Acceptance

A development/Partner app installs through OAuth, tokens refresh, the merchant explicitly activates the storefront extension, and search events arrive without PII. Admin writes remain disabled.

## 11. Milestone 8 — Approved Shopify writes

Codex prompt: `codex/08_SHOPIFY_WRITES_PROMPT.md`

### Deliverables

- explicit scope upgrade;
- approved discount create/disable;
- approved small variant-price update;
- preflight reread;
- policy and approval hash;
- application-level idempotency;
- reconciliation;
- exact rollback;
- live development-store test harness.

### Acceptance

A prefixed test discount and test-product price can be approved, executed, reconciled, and rolled back exactly. Process failure and timeout tests do not create duplicate effects.

## 12. Milestone 9 — Hardening and public beta

Codex prompt: `codex/09_HARDEN_AND_RELEASE_PROMPT.md`

### Deliverables

- fault-injection suite;
- threat model;
- security scans;
- release gates;
- clean install testing;
- public docs/governance/contribution files;
- benchmark artifacts;
- reproducible demo assets;
- honest limitations.

### Acceptance

There are no unresolved release blockers, the safety claims are test-backed, and every public claim can be reproduced.

## 13. Milestone 10 — Real acquisition budget

Codex prompt: `codex/10_GOOGLE_ADS_OPTIONAL_PROMPT.md`

This is post-v0.1.

### Deliverables

- Google Ads campaign/performance sync;
- explicit attribution definitions;
- conservative budget opportunity detection;
- approved update of existing campaign budgets;
- reporting-delay buffer;
- cross-provider budget ledger;
- rollback/reconciliation.

### Acceptance

The user can give a real acquisition goal using Shopify outcomes plus Google Ads spend, while the UI keeps platform-reported and store-attributed conversions distinct.

## 14. Dependency graph

```text
Foundation
  ↓
Domain + persistence
  ↓
Simulator ─────→ Search
  └─────────────┬───────┘
                ↓
       Controller + policy
                ↓
          API + demo UI
                ↓
        Public simulator v0.1
                ↓
         Shopify shadow
                ↓
 OAuth + storefront search/events
                ↓
       Approved Shopify writes
                ↓
          Release hardening
                ↓
     Ads connector / acquisition
                ↓
        Bounded real autopilot
```

## 15. Scope-control rules

An unplanned feature may enter a milestone only when it:

1. is necessary for an acceptance criterion;
2. enforces a safety/security invariant;
3. prevents an irreversible architecture trap; or
4. removes more complexity than it adds.

Before v0.1, reject:

- many conversational sub-agents;
- six commerce connectors;
- deep-learning training platform;
- arbitrary plugin installation;
- Kubernetes requirement;
- autonomous refunds/fulfillment;
- inventory writes;
- unrestricted ads/campaign creation;
- fully individualized pricing;
- enterprise admin features.
