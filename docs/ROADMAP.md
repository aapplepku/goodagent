# Implementation And Roadmap

No dates are promised. Version labels describe a proposed sequence, not release
approval. The repository remains private until a separate owner decision.

| Stage | Status | Boundary |
| --- | --- | --- |
| Self-hosted store alpha | Implemented experience; release qualification in progress | Reviewed CSV catalog, private preview and explicit sharing, owner/shopper agents, optional shopper accounts and memory, demo cart/checkout; no production-service claim |
| v0.1 simulator | Implemented; experimental RC plus private polish branch | Deterministic goal controller, approval/policy/budgets, durable simulator execution/recovery, live local Qdrant, browser trace, synthetic evaluations |
| v0.2 Shopify read-only / shadow | Planned; not implemented | Read-only normalized store observations and shadow proposals, no merchant writes |
| v0.3 approval-gated Shopify writes | Planned; separate safety qualification | Narrow supported actions, exact approvals, provider-specific idempotency/reconciliation/rollback evidence |
| Later bounded autonomy and ads adapters | Research/design only | Separately approved capability limits, real-provider evidence and production identity/security |

Today there is no Shopify OAuth/sync/write, real advertising spend, payment
movement, refund, fulfillment change or live inventory mutation. No trained online
learning, causal attribution, public hosted SaaS or production authentication is
claimed. Inventory-quantity writes remain excluded.

Commerce/Ads protocols and price-action schema support do not mean a live connector
exists. Recommendation API support is similar/popular retrieval, not individualized
merchant personalization. The original controller defaults to deterministic code;
manager and shopper conversation have separately configured, bounded hosted-model
providers. Configuration alone does not establish connection or answer quality.

## Owner-requested Product Work

[First-store walkthrough](FIRST_STORE_DEMO.md) documents reviewed import, truthful
activity and interrupted demo-checkout recovery. Current work hardens and qualifies
this experience for an experimental self-hosted alpha.
[Feature requests](FEATURE_REQUESTS.md) records the next product-knowledge milestone
(sourced tags and talking points with database persistence and approval) and later
privacy-conscious shopping-behavior insights. These future capabilities are not
implemented by the current first-journey work.

The original numbered design pack preserves broader ideas. For current behavior,
use [architecture](ARCHITECTURE.md) and [owner setup](SELF_SERVICE_SETUP.md), not
future connector design as a feature list. The [simulator demo](LOCAL_DEMO.md) and
[benchmark summary](BENCHMARKS.md) describe the separate historical simulator.
