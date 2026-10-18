# Open-Source Launch and Business Strategy

## 1. Open-source thesis

The open-source project is the distribution and technical standard.

The possible business is the canonical managed implementation:

```text
Open source
- runtime
- simulator
- provider interfaces
- Shopify connector
- hybrid search
- policy engine
- evaluation
- local UI

Commercial/hosted
- managed infrastructure
- secure token/KMS operations
- high-scale sync/indexing
- premium connectors
- advanced experimentation
- trained tenant models
- SSO/RBAC/audit retention
- support and SLA
- cross-store benchmarking, only with proper privacy
```

Do not cripple the open-source version. It must be useful enough to earn adoption.

## 2. License and ownership

Owner decision for v0.1: first-party code uses Apache-2.0, Copyright 2026 Han Chen,
with DCO 1.1 sign-off and no CLA. Contributors retain their own copyrights.
Root LICENSE/NOTICE are canonical; third-party terms remain unchanged. The
following launch/business sections are roadmap context, not publication authority.

Before launch:

- verify all dependencies and model licenses;
- add `LICENSE`;
- add copyright headers only where useful;
- review name provenance; no trademark registration is authorized;
- enforce the approved Developer Certificate of Origin policy;
- document inbound contribution terms;
- keep a clean IP provenance record;
- avoid copying incompatible source code.

No dual licensing, contributor assignment, CLA, noncommercial or hosted-service
restriction is part of the v0.1 decision.

Past released versions under a permissive license cannot simply be revoked from recipients.

## 3. Repository readiness

Root files:

```text
README.md
LICENSE
NOTICE
CONTRIBUTING.md
CODE_OF_CONDUCT.md
SECURITY.md
GOVERNANCE.md
ROADMAP.md
AGENTS.md
PLANS.md
CHANGELOG.md
```

GitHub templates:

- bug;
- feature;
- connector proposal;
- security link;
- discussion;
- pull request checklist.

Labels:

- good first issue;
- help wanted;
- connector;
- search;
- policy/safety;
- simulator;
- frontend;
- docs;
- breaking change.

## 4. README structure

The first screen:

```text
# <Name>
Run a store toward a goal — with explicit budgets, policies, approvals, and rollback.

[30-second GIF]

docker compose up --build
```

Then:

1. one-sentence value proposition;
2. simulator command;
3. magic demo goal;
4. screenshot of action trace;
5. safety architecture;
6. Shopify shadow setup;
7. search/ML differentiation;
8. supported capabilities;
9. roadmap;
10. contributing;
11. license.

Avoid opening with “multi-agent LangGraph RAG.” Developers care after the demo is compelling.

## 5. The launch demo

Use a 60–90 second recording:

1. start acquisition scenario;
2. enter goal/budget/constraints;
3. show agent detect poor channel CAC;
4. show proposed discount and search boost;
5. show a policy-denied 25% discount;
6. approve a bounded action;
7. advance virtual days;
8. show budget reallocation and KPI movement;
9. hit kill switch;
10. show baseline comparison.

The demo must be real and reproducible from the public repository.

## 6. Five-minute experience

Success criteria for a new developer:

```bash
git clone ...
cp .env.example .env
docker compose up --build
```

No API key required for default demo. Use a deterministic planner fallback or local model mode. An optional hosted LLM key makes explanations richer but cannot be mandatory for core simulation.

Seed and index data automatically on first start.

## 7. Launch channels

Technical:

- GitHub;
- Hacker News;
- relevant Reddit communities;
- search/recommendation and agent developer communities;
- Shopify/WooCommerce developer communities;
- short technical blog posts;
- conference/workshop demos.

Merchant:

- Shopify development partners;
- small brands;
- agencies;
- ecommerce operators;
- founder-led demos.

Do not buy a broad merchant marketing campaign before the connector and value measurement work.

## 8. Content strategy

Publish technical artifacts that make the project credible:

- why an LLM must not directly change prices;
- building an idempotent commerce action executor;
- hybrid search versus one-shot embeddings;
- goal-conditioned ranking without destroying relevance;
- simulator design for commerce agents;
- evaluating agentic retrieval;
- designing approval and rollback;
- lessons from Shopify shadow deployments.

Open benchmarks and scenario datasets can become a stronger adoption engine than generic product announcements.

## 9. Contribution strategy

Prepare modular issues:

- WooCommerce mapper;
- new simulator scenario;
- benchmark query set;
- Qdrant reranker;
- dashboard panel;
- provider fault fixture;
- policy rule.

Require:

- tests;
- capability declaration;
- no new secret exposure;
- docs;
- DCO 1.1 sign-off on every contributed commit; no CLA for v0.1.

Create a connector template generator later:

```bash
commerce-agent create-connector acme
```

## 10. Governance

Early:

- founder is BDFL/lead maintainer;
- clear code ownership and release authority;
- public roadmap;
- security decisions can be private until patched;
- documented decision process.

As community grows:

- maintainer criteria;
- review quorum for action/policy changes;
- compatibility policy;
- security response team;
- RFC process for new action types;
- independent foundation only when it serves adoption and governance.

Do not promise foundation governance at launch.

## 11. Telemetry

Default: off.

Optional opt-in telemetry may report:

- version;
- deployment mode;
- enabled connectors;
- anonymous feature usage;
- errors/performance.

Never collect:

- catalog text;
- revenue;
- prices;
- customer/order data;
- access tokens;
- prompts;
- tenant domain;

unless separately and explicitly authorized for a defined hosted service.

Show the exact payload and provide a disable switch.

## 12. Commercial validation

Before building a full hosted SaaS, find:

- 5 Shopify development stores in shadow mode;
- 3 operators willing to review proposals weekly;
- 1–2 stores willing to test an approved discount;
- evidence that a repeated action category saves time or improves a KPI.

Ask merchants about:

- goal they would delegate;
- data available;
- actions they trust;
- maximum autonomous bounds;
- required approval flow;
- willingness to pay;
- existing tools.

## 13. Pricing hypotheses

Possible hosted tiers:

### Developer

- local OSS;
- free.

### Starter managed

- one store;
- managed sync/search;
- shadow goals;
- limited runs/events;
- approximately low hundreds per month.

### Growth

- approved actions;
- advanced analytics;
- ads connector;
- experiments;
- higher usage;
- several hundred to low thousands per month depending value.

### Enterprise/platform

- SLA;
- VPC/private deployment;
- SSO;
- audit retention;
- custom connectors;
- dedicated models/support.

Price against measurable value and operational burden, not LLM token cost.

## 14. Acquisition optionality

A strategic buyer does not need the code to be closed source. It may value:

- canonical project and brand;
- maintainers;
- community;
- integration ecosystem;
- merchant deployments;
- hosted revenue;
- evaluation datasets;
- operational knowledge;
- position in the agentic-commerce stack.

Optimize for becoming the trusted default, not for making copying impossible.

## 15. Metrics to track

Open source:

- successful clean installs;
- weekly active deployments via opt-in telemetry;
- stars/forks;
- contributors;
- merged external PRs;
- issue response time;
- connector count;
- benchmark usage;
- upgrade adoption.

Product:

- connected stores;
- shadow goals created;
- proposals reviewed;
- approval rate;
- execution/rollback rate;
- time saved;
- attributed KPI lift with honest methodology;
- retained merchants;
- hosted MRR.

Safety:

- hard policy violations;
- uncertain writes;
- rollback failures;
- kill-switch activations;
- stale-data blocks;
- security incidents.

Stars are useful distribution, not proof of merchant value.

## 16. Launch milestones

### Private alpha

- simulator;
- core docs;
- 2–3 trusted engineers;
- no real writes.

### Public v0.1

- polished simulator;
- search benchmark;
- Docker install;
- security model;
- roadmap;
- Shopify connector may be shadow-only.

### Merchant design-partner beta

- Shopify sync;
- weekly shadow proposals;
- manual review;
- no broad public write enablement.

### Approved-write beta

- tenant allowlist;
- explicit terms/beta warning;
- reversible actions only;
- close monitoring.

### Hosted preview

- only after self-hosted workflows are stable and design partners show value.

## 17. Founder time allocation

For the first eight focused weeks:

- 60% core product/demo;
- 15% tests/safety;
- 15% docs/content;
- 10% user conversations.

Do not spend early weeks on:

- incorporation complexity beyond what is necessary;
- elaborate billing;
- trademark filing before name validation, while still avoiding infringement;
- conference sponsorship;
- enterprise sales deck;
- many connectors.

## 18. Project kill or pivot criteria

After public v0.1:

- can 100 strangers complete the simulator?
- do search/agent engineers contribute or discuss it?
- do at least five merchants accept shadow access?
- do proposals identify non-obvious, actionable opportunities?
- is there one action merchants repeatedly approve?

If technical adoption is strong but merchants are weak, emphasize the agentic retrieval/evaluation runtime.

If merchants value operations but developers do not care, build a focused SaaS rather than chasing stars.

If neither appears after disciplined iteration, preserve the project as a portfolio/research asset and stop expanding scope.

## 19. Definition of launch readiness

- project name checked;
- license/IP provenance reviewed;
- five-minute demo succeeds on clean machine;
- no paid key required;
- clear safety architecture;
- simulator is reproducible;
- security policy and reporting channel;
- contribution process;
- public roadmap;
- no claims of autonomous real-store safety beyond actual evidence;
- demo GIF/video and technical launch post ready.
