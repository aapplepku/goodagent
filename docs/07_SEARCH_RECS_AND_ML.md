# Search, Recommendations, and ML

The private local operator runtime now supports [engagement-trained popularity and
logistic ranking](ENGAGEMENT_RANKING.md), independently of the simulator release path
below. Candidates require offline evaluation and explicit local serving approval.

An optional pinned MiniLM ONNX embedding adapter is implemented for local CPU
execution. It is not enabled by default: the default remains signed-hash vectors.
Installing the `learned-search` dependencies alone does not select the adapter;
`OPEN_COMMERCE_SEARCH_EMBEDDING_BACKEND=minilm` and the verified local model
directory must also be configured. The adapter does not download models or run
remote code. It rejects non-finite, incorrectly shaped, zero or degenerate vectors
before they can become index entries. This is embedding inference, not training
or personalized recommendations. Current alpha-image qualification is pending.

`scripts/verify_learned_search_runtime.py` checks an exact optional image offline
with the two pinned model files. It exercises normalization, batching and a small
semantic smoke case in a bounded, nonroot, network-disabled container, retaining
failure output and cleanup results. This is not a relevance benchmark, proof of
no attempted telemetry, database connectivity test or tenant-isolation test.
Choose an evidence output directory shared with the local Docker engine. The
verifier temporarily stages only verified public model bytes beside that evidence;
macOS system temporary directories may not be shared with Docker Desktop/Colima.

## Implemented simulator release path

The deployed API and search CLI now load catalog/rule/event state from PostgreSQL.
Qdrant is a reconstructable index, not the source of price, stock or action truth.
This section describes the simulator implementation. The optional local embedding
adapter above is implemented; personalized models and hosted embedding providers
elsewhere in this design document remain roadmap only.

- Collection `products_v2`, scoped by tenant, simulator instance and catalog version.
- Actual async sparse and dense Qdrant queries, with deterministic local RRF (k=60).
- `rank-v4` quantizes branch scores to six decimal places, groups near ties within
  0.00001 of each group's highest score, orders each group by product ID, and then
  selects 100 candidates per branch. Groups do not chain through intermediate
  scores. This corrects float-reduction noise crossing a rounding boundary in
  rank-v3. Exact retrieval of the small simulator catalog avoids nondeterministic
  server-side truncation of tied points; it supports at most 10,000 products.
- Five explicit modes: sparse, dense, hybrid, hybrid_reranked, hybrid_boosted.
- Dense vectors are local signed hashes plus small semantic expansions. They are
  not a neural embedding model. Sparse vectors use hashed term frequency and
  Qdrant IDF, not full BM25. Reranking is a bounded deterministic feature scorer.
- Search responses rehydrate authoritative PostgreSQL documents before applying
  relevance, currency, category, brand, attribute, exclusion and available-variant
  price checks. A cheap out-of-stock variant cannot satisfy a price constraint.
- Hard request filters intersect parsed constraints. Conflicts return 422;
  exclusions and explicit budgets are never relaxed. A Qdrant outage returns 503,
  without an in-memory fallback or a stack trace.
- The goal context selects its own catalog. Without one, the latest active
  manager-uploaded catalog is used when available, then the latest-created simulator
  instance; a first search otherwise creates a durable seed-42 catalog.
- Search boosts are read from committed simulator executor effects and linked to
  compiled action IDs. Their windows use simulated time. Direct rule POST/DELETE
  endpoints have been removed; use the approval/executor/rollback workflow.
- Only `hybrid_boosted` applies business rules. A boost is capped at 0.15 and
  requires independent relevance >= 0.20, all hard constraints and adequate stock.
- Event IDs and session references are hashed with tenant scope. Event receipts
  and deduplication survive restart. Arbitrary event metadata is rejected; only
  bounded numeric dwell_ms and quantity are stored. This endpoint is for
  synthetic local-demo events, not production customer analytics or consent.

Automatic indexing compares current source-version counts, then rebuilds missing
or partial catalogs from PostgreSQL. `commerce-agent search reindex --goal UUID`
forces reconstruction; `commerce-agent search query "outdoor" --goal UUID` uses
the same durable catalog and live adapter. Catalog versions include engine,
template, embedding/sparse model versions and exact product/variant state.

A valid manager catalog upload follows the same authority boundary: the API stores
bounded normalized records in PostgreSQL and creates a reconstructable indexing
job; Redis delivers the job ID; the worker builds dense+sparse Qdrant points and
atomically marks that catalog active only after a count match. Failed or partial
new versions never replace the previous ready catalog. Re-uploading identical
content is idempotent. This is catalog indexing, not model training or ranking-policy
activation.

[Measured search report](benchmarks/search-v2.md) and its raw artifact distinguish
the small synthetic benchmark from production relevance evidence. Rebuild and
filter behavior follows the [Qdrant filtering API](https://qdrant.tech/documentation/search/filtering/).

## 1. Product role

Search/recommendations are both:

1. a shopper-facing product-discovery capability; and
2. a merchant-agent actuator.

The runtime must never sacrifice basic relevance merely to satisfy a business goal. Business-objective optimization happens after relevance gating and within configured bounds.

## 2. MVP architecture

Use one Qdrant collection for product retrieval with:

- dense text vectors;
- sparse BM25-style vectors;
- payload filters;
- reciprocal-rank fusion;
- optional cross-encoder reranking;
- tenant isolation in every query.

```text
catalog normalization
  ├── product text → dense embedding
  ├── product text → sparse/BM25 representation
  └── attributes → typed payload
                         ↓
                     Qdrant
                         ↓
query → intent/constraints → dense + sparse retrieval
                         ↓
                       RRF
                         ↓
                structured filters
                         ↓
                 optional reranker
                         ↓
              goal-aware bounded boost
                         ↓
                   final results
```

Do not deploy Elasticsearch plus a separate vector database for v0.1 unless a concrete limitation appears. One service reduces setup friction.

## 3. Product search document

```python
class ProductSearchDocument(BaseModel):
    tenant_id: UUID
    product_id: str
    variant_ids: list[str]
    title: str
    description_text: str
    brand: str | None
    category_path: list[str]
    tags: list[str]
    attributes: dict[str, JSONScalar | list[JSONScalar]]
    min_price_minor: int
    max_price_minor: int
    currency: str
    in_stock: bool
    available_variant_count: int
    inventory_bucket: str
    unit_margin_rate: Decimal | None
    popularity_score: float
    quality_score: float | None
    updated_at: datetime
    source_version: str
```

Text for embedding:

```text
{title}
Brand: {brand}
Category: {category_path}
Description: {clean_description}
Attributes: {normalized_key_value_pairs}
Tags: {tags}
```

Do not include private merchant fields, unit cost, hidden tags, customer data, or agent instructions in shopper-visible text.

## 4. Collection strategy

MVP:

- collection: `products_v2`;
- point ID: deterministic UUID of `tenant_id + simulator_instance_id + product_id`;
- required payload scope: `tenant_id`, `instance_id`, `source_version`;
- shared collection with tenant filter;
- payload indexes for tenant, category, brand, stock, currency, and numeric price;
- vector names: `dense`, `sparse`.

Every repository method requires `tenant_id`; no search API accepts a raw filter that can remove it.

For larger deployments, add tenant shard keys or dedicated collections behind the same interface.

## 5. Embeddings

Create:

```python
class EmbeddingProvider(Protocol):
    model_id: str
    dimensions: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...
```

Defaults:

- local open embedding model for demo and CI;
- optional hosted embedding providers through environment configuration;
- batching, retry, cache, and content-hash deduplication;
- model/version stored with every indexed document.

Reindex into a new collection version when changing vector dimensions or materially changing the document template. Switch aliases atomically after validation.

## 6. Query understanding

Input:

```python
class SearchRequest(BaseModel):
    tenant_id: UUID
    query: str
    session_id: str | None
    user_context: SearchUserContext | None
    filters: SearchFilters | None
    goal_context_id: UUID | None
    top_k: int = 20
    debug: bool = False
```

Output of query understanding:

```python
class SearchIntent(BaseModel):
    normalized_query: str
    lexical_terms: list[str]
    semantic_query: str
    category_hints: list[str]
    required_filters: ProductFilters
    preferred_attributes: dict[str, list[str]]
    excluded_attributes: dict[str, list[str]]
    budget: PriceRange | None
    sort_preference: SortPreference | None
    ambiguity: list[ClarificationNeed]
    confidence: float
```

Use a layered parser:

1. deterministic extraction for price, currency, negation, exact SKU, quoted phrases, sizes, and obvious facets;
2. LLM structured extraction for complex use cases;
3. schema validation and catalog-facet resolution;
4. drop or clarify unsupported constraints instead of inventing attributes.

The LLM may suggest a brand/category string, but a resolver maps it to known values.

## 7. Retrieval

Run two retrieval branches:

### Sparse branch

Strong for:

- exact brand/model/SKU;
- rare terms;
- spelling-aware lexical match;
- attribute names.

### Dense branch

Strong for:

- use cases;
- paraphrases;
- semantic compatibility;
- long natural-language needs.

Apply hard filters in both branches when supported. Retrieve roughly 50–100 candidates per branch, configurable by catalog size.

Fuse with RRF:

```text
RRF(d) = Σ_r 1 / (k + rank_r(d))
```

Use deterministic tie-breaking by product ID.

Expose branch ranks and scores in debug traces, but do not imply raw sparse and dense scores are directly comparable.

## 8. Reranking

MVP tiers:

1. RRF only — default low-latency path;
2. local cross-encoder on top 30–50 — optional;
3. LLM reranking — off by default and restricted to small result sets for experiments.

Interface:

```python
class Reranker(Protocol):
    async def rerank(
        self,
        query: SearchIntent,
        candidates: list[SearchCandidate],
        context: RankingContext,
    ) -> list[RankedCandidate]: ...
```

Reranking features:

- hybrid rank features;
- title/attribute match;
- price fit;
- stock;
- category match;
- preference satisfaction;
- popularity;
- optional conversion prior;
- business objective features.

## 9. Relevance gating and business boosts

First compute a relevance score independent of the merchant goal.

Only products above `minimum_relevance_score` can receive a business boost.

Example:

```text
final_score
  = relevance_score
  + capped_goal_boost
  + capped_quality_boost
  - stock_risk_penalty
```

Rules:

- business boost cannot exceed a configured percentage of total score range;
- unavailable products are removed;
- low-stock products may be suppressed for high-volume promotion;
- unknown margin never receives a margin-based boost;
- a goal cannot bypass required shopper constraints;
- trace shows each score component.

For internal search rules:

```python
class SearchBoostRule(BaseModel):
    id: UUID
    tenant_id: UUID
    query_pattern: QueryPattern
    product_scope: ProductScope
    multiplier: Decimal
    starts_at: datetime
    ends_at: datetime
    reason_action_id: UUID
    status: RuleStatus
```

These rules affect only this project's search API/widget. They do not magically alter a marketplace's proprietary ranking.

## 10. Agentic search loop

For complex shopper queries:

```text
parse
  ↓
retrieve
  ↓
evaluate result set
  ├── good → answer
  ├── ambiguous → ask one clarification
  └── weak → reformulate or relax preference → retrieve again
```

Result-set evaluator:

```python
class ResultSetEvaluation(BaseModel):
    coverage_by_constraint: dict[str, float]
    hard_constraint_violations: list[str]
    result_diversity: float
    confidence: float
    decision: Literal["answer", "clarify", "retry", "no_result"]
    retry_plan: SearchRetryPlan | None
```

Retry rules:

- maximum two retrieval retries;
- never relax hard safety/explicit exclusion constraints;
- distinguish required versus preferred constraints;
- disclose relaxed preferences;
- stop when no improvement is likely;
- retain all traces.

Example:

```text
Required: waterproof, size 10.5, <= $180
Preferred: wide, dark color
Excluded: heavily insulated

Retry may relax "wide" from preferred to unscored.
Retry may not remove waterproof, size, budget, or insulation exclusion.
```

## 11. Recommendations

MVP recommendation strategies:

- similar products from dense vectors;
- complementary products from configured category rules;
- trending/popular by cohort;
- recently viewed fallback;
- goal-aware merchandising boost within relevance rules.

Interface:

```python
class RecommendationRequest(BaseModel):
    surface: RecommendationSurface
    anchor_product_ids: list[str]
    session_id: str | None
    user_context: SearchUserContext | None
    top_k: int
```

Do not build a custom deep-learning recommender before enough impression/click/order data exists.

Later roadmap:

- item-item co-visitation;
- implicit matrix factorization;
- two-tower retrieval;
- session encoder;
- product-level ranker;
- multi-objective/personalized ranking;
- contextual bandits.

## 12. Behavioral events

Canonical events:

```python
class BehavioralEvent(BaseModel):
    event_id: str
    tenant_id: UUID
    occurred_at: datetime
    session_id: str
    anonymous_user_id: str | None
    event_type: EventType
    product_id: str | None
    variant_id: str | None
    query_id: str | None
    result_position: int | None
    surface: str
    metadata: dict[str, JSONScalar]
```

Types:

- `search_submitted`
- `product_impression`
- `product_clicked`
- `product_viewed`
- `add_to_cart`
- `checkout_started`
- `purchase`
- `discount_exposed`
- `discount_redeemed`

Generate `query_id` and ranking version so outcomes can be attributed to exact retrieval/ranking configurations.

Use consent-aware pseudonymous IDs. Do not send raw customer identity to the model.

## 13. Indexing pipeline

Initial full load:

1. load normalized catalog records;
2. clean and render search text;
3. content-hash documents;
4. embed changed documents in batches;
5. upsert dense, sparse, and payload data;
6. mark index version;
7. compare source/index counts;
8. run smoke queries;
9. publish index alias/version.

Incremental:

- consume product create/update/delete events;
- debounce repeated updates;
- reread authoritative product data;
- upsert or tombstone;
- record source cursor and index lag;
- retry safely.

Never rely only on a webhook payload as the authoritative product representation.

## 14. Evaluation suite

Ship a benchmark CLI:

```bash
make benchmark-search
# or
uv run commerce-agent eval search --dataset examples/eval/queries.jsonl
```

Dataset row:

```json
{
  "query_id": "q-001",
  "query": "waterproof trail shoes under $150",
  "relevant_product_ids": ["p12", "p18"],
  "required_constraints": {
    "waterproof": true,
    "max_price_minor": 15000
  },
  "graded_relevance": {"p12": 3, "p18": 2, "p29": 1}
}
```

Metrics:

- Recall@K;
- Precision@K;
- NDCG@K;
- MRR;
- hard-constraint satisfaction;
- preference coverage;
- no-result rate;
- diversity;
- catalog coverage;
- latency p50/p95;
- embedding/LLM cost;
- retry frequency;
- click/ATC/purchase metrics when online data exists.

Compare:

- sparse only;
- dense only;
- hybrid;
- hybrid + reranker;
- agentic retry.

Include confidence intervals for aggregate metrics where practical.

## 15. Search trace

Debug response:

```json
{
  "query_id": "uuid",
  "intent": {...},
  "retrieval": {
    "sparse": {"count": 80, "latency_ms": 12},
    "dense": {"count": 80, "latency_ms": 18},
    "fusion": "rrf"
  },
  "constraints": {...},
  "retries": [...],
  "ranking_version": "rank-v1",
  "results": [
    {
      "product_id": "p12",
      "score_components": {
        "relevance": 0.78,
        "goal_boost": 0.06,
        "stock_penalty": 0.0
      },
      "constraint_matches": {...}
    }
  ]
}
```

Redact hidden merchant fields from shopper APIs. Full traces require operator authorization.

## 16. Acceptance criteria

- sparse, dense, and hybrid retrieval work from one local install;
- every query is tenant-filtered;
- hard price/stock/category filters are enforced;
- exact SKU queries outperform dense-only retrieval in tests;
- semantic use-case queries outperform sparse-only on the example set;
- RRF and tie-breaking are deterministic;
- business boosts cannot surface candidates below relevance floor;
- two retry attempts is the hard maximum;
- search events include query and ranking versions;
- index updates are idempotent;
- the benchmark compares at least four configurations;
- the storefront displays product cards from the search API.
