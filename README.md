# GoodAgent

**Empowering small businesses with AI.**

Open-source AI agents for store owners and their shoppers. Bring a product catalog,
review it, and try a conversational store without replacing your existing shop.

**Experimental source snapshot, not a qualified v0 release.** Use non-sensitive
test data on your own computer. Read the [current status and known limitations](docs/EXPERIMENTAL_STATUS.md)
before installing or contributing.
Checkout is a demo: no real payments, inventory writes, shipping or fulfillment.

## One Store, Two Experiences

**For the owner:** upload a catalog, review products and variants, watch indexing,
test a private shopper preview, and explicitly enable a store link. Talk to the
operator agent about search, catalog readiness, operational activity and store
questions. Specialist conversations keep separate context without restricting
questions to a rigid workflow.

**For the shopper:** open that store link, browse or chat without creating an
account, compare products, choose a variant, and explicitly add it to a demo cart.
Optional accounts preserve progress and provide controllable shopping memory.

The agents share authorized catalog services, not private conversations or
permissions. An agent suggestion cannot place an order or charge a customer.

## Take A Look

Current GoodAgent screenshots from an isolated two-product test store.
Prices and stock are synthetic; missing product photos use placeholders. The shopper capture uses
**Basic mode with AI disconnected**, not a model-generated answer or a
search-quality benchmark.

<details>
<summary>Owner: review products and variants before importing</summary>

![GoodAgent owner reviewing two synthetic products, variants and explicit import confirmation](docs/assets/alpha/20261018-current/catalog-review-resumed-1440x1000.png)

</details>

<details open>
<summary>Shopper: catalog results with explicit demo-cart controls</summary>

![Shopper interface displaying a catalog result in clearly labeled Basic mode](docs/assets/alpha/20261018-current/private-preview-1440x1000.png)

</details>

[Desktop/mobile gallery and capture provenance](docs/ALPHA_SCREENSHOTS.md).
The two planned real-model recordings are not complete; see
[recording status](docs/ALPHA_DEMOS.md).

## Quick Start

Requirements: Docker Engine running with Compose v2 or later, Python 3.12+, and
`make`. From a checkout of this repository:

```sh
make setup
```

Setup generates an ignored private environment only if it is missing, builds the
containers, applies migrations, waits for health checks, and prints the application
URLs. No host Node, pnpm, uv or Python package installation is required. Re-running
setup keeps the same configuration and volumes; it never resets your store.
The first build needs internet access and can take several minutes.

Run the **one-time owner token command printed by setup** in your own terminal.
Open the printed owner URL, enter that token, create your account and keep the
single-use recovery code somewhere private. Do not put either code in a screenshot
or share it with an agent.

Then:

1. Choose a CSV or explicitly select the bundled sample. No sample is attached silently.
2. Review field mapping, currency, product variants and validation errors. Confirm.
3. Wait for verified indexing, then open a private shopper preview.
4. Test a search, review image issues and acknowledge demo-only checkout.
5. Explicitly enable the store link and open it in another browser session as a guest.

Loopback links work on this computer only. Do not expose this alpha directly to the
internet. [Complete setup, existing installations and recovery](docs/SELF_SERVICE_SETUP.md).

### With Or Without A Model

Browsing, product details, catalog import and demo cart work without an AI key.
The default deterministic replies are a limited test mode, **not a conversational
LLM**. To enable the real agent, privately configure these existing settings in `.env`
and rerun setup:

```dotenv
OPEN_COMMERCE_MANAGER_MODEL_PROVIDER=openai
OPEN_COMMERCE_MANAGER_MODEL_ID=gpt-5.4-mini
```

Add `OPEN_COMMERCE_OPENAI_API_KEY` separately in that ignored file, never in Git,
chat, browser storage or a screenshot. Both apps use the instance's server-side
credential; shoppers never need their own key. Provider charges apply. Configured
request/token limits bound usage but are not a billing guarantee. Verify connectivity
in setup: a configured key does not prove the provider is reachable.

## What Works, What Is Experimental

| Capability | Current boundary |
| --- | --- |
| Generic and Shopify CSV import | Reviewed mappings, row errors, up to 20 MiB / 10,000 rows; no automatic Shopify sync |
| Catalog browsing and images | Authorized catalog versions, variant detail, safe image ingestion; failed images are reported |
| Owner workspace | Persistent channels/replies, memory, operational tools and in-app monitoring |
| Agentic shopper search | Bounded model/tool loop, authoritative product lookup, exact price comparisons and validated card selection; answer quality remains experimental |
| Guest shopping and accounts | Store-scoped sessions, optional registration, recovery codes and explicit cart-conflict review |
| Shopping memory | Model-selected, validated saves; account toggle, deletion and temporary guest memory |
| Ranking experiments | Popularity and supported logistic-regression candidates from engagement; training is not activation or proof of lift |
| Demo cart and checkout | Explicit user actions, idempotent test outcomes and demo orders; no real payment processor |
| Hosted identity adapter | Controlled OIDC fixture coverage; no hosted service or production deployment qualification |

**Not implemented for this alpha:** real payments, tax/shipping, live inventory or
fulfillment writes, automatic warehouse refresh, live Shopify authorization, product
research/enrichment, behavioral learning, team permissions or billing subscriptions.
See [feature requests](docs/FEATURE_REQUESTS.md) and [roadmap](docs/ROADMAP.md).

The bundled sample contains 48 attributed Amazon Berkeley Objects listings.
Prices, stock and engagement are synthetic, not current Amazon offers or actual
customer behavior. [Sample attribution](examples/datasets/amazon-berkeley-objects/README.md).

## Guides

- [Owner setup and publishing](docs/SELF_SERVICE_SETUP.md)
- [Private backup and isolated recovery](docs/BACKUP_RESTORE.md)
- [First-store walkthrough and bounded model tasks](docs/FIRST_STORE_DEMO.md)
- [Shopper accounts, memory and search](docs/SHOPPER_AGENT.md)
- [Operator agent and tool boundaries](docs/MANAGER_AGENT.md)
- [Everyday store operations](docs/STORE_OPERATIONS.md)
- [Demo cart, inventory observations and checkout](docs/CART_CHECKOUT.md)
- [Architecture and trust boundaries](docs/ARCHITECTURE.md)
- [Development and contribution](CONTRIBUTING.md), [tool/provider extension](docs/EXTENDING.md)

The older simulator remains available for regression work, not the primary store
onboarding journey. Its explicit `legacy_demo` profile is not authenticated and must
stay local. [Simulator walkthrough](docs/LOCAL_DEMO.md), [historical benchmarks](docs/BENCHMARKS.md).

## Architecture

The operator and shopper Next.js apps use separate sessions and same-origin proxies
to FastAPI. PostgreSQL stores identities, catalogs, messages, memory, jobs and audit
receipts. Redis/ARQ runs background work; Qdrant is a rebuildable search projection.
Images live on a persistent asset volume. External model calls use typed providers;
tool arguments and returned identifiers are validated by application code.

An LLM cannot choose its tenant, grant preview access, publish a catalog, bypass
cart controls or execute arbitrary commands. Catalog text is untrusted input.
Defaults remain draft-only or approval-required. [Detailed safety model](docs/THREAT_MODEL.md).

## Development

Use Python 3.12+, Node 22 and the pinned uv/pnpm versions. Developer setup is separate
from the Docker-first user setup:

```sh
make bootstrap
make lint
make typecheck
make test
make test-integration
make check-openapi
```

Use disposable dependency services for integration tests. Browser suites and
real-model evaluation have separate opt-ins and budgets; see the
[reproduction guide](docs/FIRST_STORE_DEMO.md). Do not run fault tests against your store.
`make dev-local` is for configured native development and prints its actual ports.

## Release And Security Status

**Experimental source candidate, not a qualified alpha release.** A recorded local
run ended October 18, 2026 at 21:44 UTC. Lint, type checking and OpenAPI/client
freshness passed, along with 4,089 Python tests, 245 integration tests, 608
frontend/SDK tests and both application browser checks. **Four release-evidence
tests still fail**: three security gates and one dependency-attribution gate, so
`make test` is not green. One Python test and 11 opt-in
integration tests were skipped. These checks used disposable local stores with
model calls disabled, not fresh production containers or Linux CI.

An offline rehearsal of the source-only export retained all four release-gate failures.
It excludes private review-tool tests and reuses installed/cached dependencies;
it is not a cold installation. See the dated [validation summary](docs/ALPHA_VALIDATION.md)
for source identities, exact copy-test counts and platform-related skips.

The source-only export excludes 78 copied files from four dependencies whose
original notices remain unresolved. It preserves their identities, hashes and
explicit disclosures; this permits separate review of the narrowed source
selection without claiming permission to redistribute affected dependency
binaries. [Attribution scope and checks](docs/DEPENDENCY_ATTRIBUTION.md).

Earlier snapshots passed production-container journeys, same-machine backup
restoration and bounded model checks. After two failed model evaluations and fixes,
two new runs passed automated checks using 59 model requests in total. Independent
review found no actionable issue in eight tested adversarial outputs; human
narrative approval remains pending. This small synthetic sample is not a general
search-quality guarantee, and older evidence does not qualify later source changes.

Scans of the earlier eight-image candidate contain **982 service-scoped findings:
261 HIGH, zero CRITICAL, 349 MEDIUM, 366 LOW and six UNKNOWN**. All HIGH records
remain blocked pending current-artifact applicability review. Its separate source
scan reports one HIGH Node dependency finding, also blocked. These are dated
occurrences, not a count of unique vulnerabilities or a scan of this newer source.
Historical assessments expired October 5, 2026. No failed gate has been suppressed
and no risk waiver is implied by source publication. This is not a zero-vulnerability
claim. Clean Linux installation, current-container security qualification, remaining
reviews and the two planned recordings are still outstanding.

[Publication checklist](docs/PUBLIC_RELEASE_CHECKLIST.md): experimental source
disclosure requires exact-candidate approval and is separate from alpha qualification.

Report vulnerabilities privately using [SECURITY.md](SECURITY.md). Do not submit
credentials, customer data or private conversations in issues. There is no stable
release, support SLA, proven sales lift or production-safety guarantee.

## License And Contributions

[Apache-2.0](LICENSE). Copyright 2026 Han Chen; contributors retain their copyright.
[DCO 1.1](DCO.md) sign-off is required; no CLA. [Contribution guide](CONTRIBUTING.md),
[conduct](CODE_OF_CONDUCT.md), [NOTICE](NOTICE), [third-party notices](THIRD_PARTY_NOTICES.md).
