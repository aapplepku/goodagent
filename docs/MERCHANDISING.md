# Simulator Merchandising

Private development profile, separate from the preserved acquisition engine.
The current implementation and tests are not a release qualification or evidence
of merchant lift. [Registered comparisons and failures](../examples/eval/merchandising-v1/REPORT.md)
are retained; [deployment/security evidence](MERCHANDISING_SECURITY.md) is separate.

## Capability Ledger
| Capability | Implemented boundary | Evidence and remaining gap |
| --- | --- | --- |
| Pricing | Finite candidates, exact costs/combined bounds, version/window/cooldown, approval, expiry and rollback | Real durable price/recovery/serving workflows; demand response remains unidentified |
| Promotions | Targeted create/disable, best single offer, reference-basis accounting, atomic global/offer caps | Concurrent redemptions/replay/abort tests; no causal promotion-harm estimator |
| Search | Lexical, labeled hash test baseline, pinned learned dense/hybrid, hard filters before boosts | 90 registered queries; failed held-out availability records and post-fix replay retained; no cross-encoder |
| PDP recommendations | One anchored alternatives/complements surface, explicit relationships, bounded policy, approval/reconciliation/rollback | Actual shared serving and simulated purchases in workflow records; no personalization or proven planner-selected lift |
| Coordination | Bounded read tools, typed finite proposals, wait, durable model journal | Deterministic comparison only; real generative-model planning remains blocked |

Migration `0008_merchandising` adds nullable goal-profile configuration. Existing
goals keep legacy behavior; selecting this profile requires a fresh simulator.
No live-provider writes or additional services are enabled. Do not downgrade away
audit/redemption records when rolling back feature code.

## Reviewed Goals
The primary workspace templates use these finite clauses. Each semicolon-separated
clause is recognized or blocks activation; unknown instructions are not discarded.
Omitted settings appear as defaults in the exact typed goal review.

```text
Merchandising: maximize contribution profit in 14 days; max base price change 10%; max effective discount 15%; promotion cap $50; minimum unit margin 25%
Merchandising: clear 200 excess inventory units in 14 days; no discounts; minimum unit margin 25%
Merchandising: maximize search purchases in 14 days; search only; minimum relevance 55%
```

No acquisition budget or CAC target is required. Advertising is prohibited at the
profile and provider boundaries even if tenant policy allows legacy campaigns.
`no discounts` additionally forbids effective base markdowns below the frozen
reference; it cannot be combined with a positive promotion cap or discount ceiling
without clarification. `prohibit prices`, `prohibit promotions`, `prohibit search`
and `prohibit recommendations` are supported individual clauses. The typed review
also supports cumulative price-change limits, cooldown, duration and relevance.
Changing an existing legacy goal into this profile requires a new simulator.
Legacy text interpretation, saved goals and benchmark evidence remain available.

Tenant policy is an independent gate. Price and PDP actions are not silently added
to its allowlist: review the policy's action-family checkboxes, save, then run a new
cycle. Default autonomy remains approval-required. Whole-day action windows match
the daily simulator; current versions, combined economics, exact approval and
dispatch preconditions must still match. Rollback does not erase cumulative price
movement, redemption usage, measurements or audit records.

## Economics And Evidence
Contribution profit = net realized revenue - product cost - variable payment fee.
Net revenue already excludes the offer discount. The equivalent gross accounting
identity subtracts the discount once, never twice. The recorded aggregate margin
uses gross revenue as its denominator for compatibility; the hard known unit
margin uses net revenue. Neither certifies future aggregate profit.

Reference prices are frozen at profile initialization. A redeemed promotion charges
`max(0, min(reference_price, current_base_price) - effective_price)` to its independent
promotion cap. A price increase cannot inflate the reference basis. Base-only
markdowns are separate from promotion redemptions. This accounting charge is not
a causal estimate of profit lost. Ad spending is zero; model usage has its own
existing journal and caps. Promotions never stack additively: the best single
eligible known offer is considered, including subtotal and new-customer conditions.

At simulated checkout, tenant-locked PostgreSQL state atomically records the line
receipt, stock decrement, global/offer cap usage and product economics. Concurrent
requests, transaction aborts and changed-key/replay cases have dedicated tests.
The cap is hard within this simulator transaction, not a promise about remote stores.

`GET /v1/goals/{goal_id}/merchandising/{view}` returns scoped, read-only evidence.
Views: `economics`, `pricing`, `products`, `inventory`, `outcomes`, `search`,
`recommendations`. Optional `product_id`/`category`; at most five products and two
variants per product. Exact candidate economics include unchanged price and no
promotion. Recorded conversion is descriptive, not identified elasticity. Predicted
orders and store profit remain null. No latent preferences, future outcomes,
customer data or free-form catalog instructions enter these tools.

## Serving And Coordination
The versioned synthetic catalog has 48 products, 96 variants and explicit authored
compatibility links. It is not a real merchant catalog. API and simulation call the
same Qdrant search and PDP eligibility/ranking functions. Hard shopper constraints,
stock and relevance precede business boosts. The sole recommendation surface is
one anchored PDP panel: alternatives require the same declared product type;
complements require explicit catalog-pair evidence, never vague similarity.

Each incoming session can check out once. An alternative can replace the anchor;
an explicitly compatible complement can add one optional unit after anchor purchase.
A declined optional add-on leaves the primary purchase intact. Checkout-to-line
references, serving policy versions, exposed products, clicks, carts and product
economics are recorded. Incoming traffic and unrelated random draws remain matched
by seed/day/channel/session/product keys across evaluation arms.

Deterministic coordinator v2 separates bounded candidate generation from selection
after compilation and policy. It records competing choices and unchanged behavior,
uses matched surface/window observations, and considers justified recommendation
revisions after version zero. Unknown demand response and profit effects remain
unknown. [Decision rules, reassessment and evidence limits](MERCHANDISING_DECISIONS.md).
Historical v1's first-match ordering and two-day global cooldown remain in its
frozen evaluation arm, not as claims about the revised controller.

The existing bounded model interface can investigate and propose these typed actions
but cannot supply authoritative cost/margin/budget facts or execute. The blocked
Ollama runtime remains disabled. No paid fallback or real-model validation occurred.

## Learned Search Installation
One optional text encoder, not a generative planning model:
`sentence-transformers/all-MiniLM-L6-v2`, revision
`dfa9feb5cece5be2cc8fc23a3cf1f32473a9d56f`, Apache-2.0 declared in its
[pinned model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/blob/dfa9feb5cece5be2cc8fc23a3cf1f32473a9d56f/README.md).
The upstream revision contains no separate LICENSE file; do not confuse its card
declaration with a separately verified license text. CPU ONNX FP32, 384 dimensions,
256-token truncation, attention-masked mean pooling and L2 normalization.

`scripts/fetch-search-model.py` retrieves exactly two fixed-revision data files,
checking hashes before any native parser sees them. Runtime performs no download,
custom remote code execution or model-daemon call. Model data: 90,871,461 bytes.
The final exact-image Linux arm64 CPU probe (network disabled, non-root, read-only)
loaded the encoder in 7.891 seconds, then measured five queries at 0.799, 0.156,
0.104, 0.106 and 0.134 seconds, with peak RSS 407,424 KiB under concurrent local
validation load. This is not production sizing. Exact evidence is retained in the
deployment/security review.

```bash
uv sync --frozen --all-packages --all-extras
uv run python scripts/fetch-search-model.py --directory .opencommerce/merchandising/models/minilm
docker compose -f docker-compose.yml -f infra/docker/compose.merchandising.yml up -d --build --wait
```

The ordinary Compose file retains explicitly labeled hash test retrieval and does
not install the optional native encoder. The overlay mounts verified model data
read-only and opts out of ONNX Runtime telemetry before native initialization.
An initial synthetic probe exposed a native telemetry default; the diagnostic was
retained and the full environment opt-out added after checking upstream source.
Do not infer from later quiet logs that the first probe's network behavior was proven.
Fresh image, license, SBOM and network-isolation results are retained separately.

PDP relationship serving reads current tenant-owned catalog facts without rebuilding
the unrelated vector index. The first virtual day still constructs that index and
serves simulated shoppers; the browser gives this idempotent operation a bounded
120-second wait, as does a cold search request; ordinary reads remain at 15 seconds.
The retained legacy 1,000-product browser workflow exposed a roughly 100-second
index build under local validation load and the original 15-second timeout failed.
Two subsequent recovery-test preparations exceeded even 120 seconds before any
outage was injected. Cold 1,000-product learned indexing can therefore still exceed
the bounded browser deadline; the recovery test allows five minutes only for setup,
not for outage responses. Large cold catalogs
can still need explicit indexing or an eventual asynchronous workflow; no latency
SLA or production-scale behavior is claimed.

Search evaluation is separately registered under `examples/eval/search-merchandising-v1`.
No six-query benchmark or embedding smoke is treated as sufficient relevance proof.

## Search Evaluation
The 90 agent-authored queries have explicit relevance judgments: 36 development
queries and 54 held-out queries (including six unrelated/no-result cases). The
held-out catalog families overlap development, so this is limited synthetic
evidence. Lexical is TF-IDF-style, not BM25; hash vectors are not learned embeddings.

Held-out raw top-five NDCG: lexical 0.845918, learned dense 0.890431, hybrid
0.872148, hash test baseline 0.606010. These figures accompanied 36/42/42/42 raw
hard-constraint violations, respectively: an unavailable cheap variant incorrectly
qualified its product. The failed first pass and original source snapshot remain.
After correcting availability and live qualifying-price checks, an explicitly
post-fix replay found zero such violations with unchanged NDCG. It is not a new
held-out result. Correct eligible-empty behavior remained only 0.777778 lexical
and 0.666667 for the other arms; abstention is a remaining product gap.

The pinned model card and dependency license/notice provenance are retained under
`security/third-party/learned-search`. Model data itself is not committed. Native
library SBOM coverage and the model-card-only license declaration remain explicit
limitations; neither a quiet scan nor an offline smoke is a safety certification.

## Local Validation
September 6, 2026: private Linux arm64 Compose deployment with the actual pinned
learned encoder; Python 3.12.11 host checks. This is not hosted qualification.

| Check | Result |
| --- | --- |
| Full `make check` | Passed: lint/typecheck, 488 backend/contracts, eight SDK, 76 integration plus one deliberately gated real-model skip, goldens/search/controller smoke, OpenAPI and legal/path checks |
| Final web unit tests | 71 passed after the bounded search deadline change; the earlier full check contained 68 |
| Production browser | All seven workflows passed in 9.3 minutes, including actual PDP serving/economics, exact approval, worker execution, measurement, learned search, reset and desktop/mobile overflow checks |
| Outage/recovery | Four drills passed: Redis, PostgreSQL, API/worker restart, and Qdrant; the last ran separately after browser checks |
| New durable workflows | Six passed; four retained hash/MiniLM price/PDP fixtures include committed-effect crash, retry, actual serving/purchases and rollback |
| Evidence contracts | 92 focused security/archive/legal/comparison tests passed; 67 supplementary raw files verified by original/compressed hashes |
| Security | Seven final images, fresh applicability, source/all-extra dependencies, secret checks, licenses, SBOMs and network-none native encoder proof; see the separate security review |

Original failed browser captures, two timed-out cold-index recovery preparations
and the evaluation infrastructure interruption remain documented/retained. Passing
reruns do not turn them into independent quality cases or establish a latency SLA.
The Qdrant drill's five-minute initial indexing allowance does not relax its
15-second outage/recovery response checks. All isolated services were restored.

Implementation is on private draft [PR #3](https://github.com/aapplepku/opencommerce/pull/3),
stacked on the preserved model-planning branch. No merge, tag, publication, protected
ref/visibility change or real-provider enablement is part of this work. Hosted
checks triggered by the push are a separate, not-yet-qualified evidence scope.
