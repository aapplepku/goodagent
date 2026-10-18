# Merchandising Search Evaluation V1

## Registration
Registered before development or held-out search evaluation. Corpus is authored
`merchandising-catalog-v1`: 12 product families, four brands, two variants each.
Dataset consists of 84 family queries plus six unrelated no-result queries.
Development: exact, material and budget queries (36). Held-out: paraphrase, use
intent, brand and variant-availability queries (48), plus six no-result queries.
All model/retrieval thresholds are frozen before either split is run. Any change
after inspecting held-out results requires a new dataset/version, not replacement
of the retained results. Model smoke/workflow tests are not relevance evaluation.

These are agent-authored synthetic judgments, not merchant/customer judgments.
Held-out means withheld from tuning, not unseen product families: the same 12
families occur in both splits. There is no claim of independent merchant generality.
Each query's positive products are the explicitly named family, intersected with
its authored hard constraints. Positive grade is 3; all other products grade 0.
Budget is checked against an available variant, never a sold-out cheap variant.
The variant fixture marks every first variant unavailable, without changing the
price or stock of second variants. Its restrictive family budget should yield no
eligible family result; irrelevant cheap items are not credited. Unrelated queries
have no positives. Judgments never depend on what a retrieval arm returns.

## Arms And Metrics
- Existing Qdrant sparse hashed-term/IDF retrieval, called `lexical_tfidf`, not BM25.
- Actual pinned MiniLM dense retrieval, called `learned_dense`.
- Shared reciprocal-rank fusion (k=60), called `learned_hybrid`.
- Retained signed-hash dense vectors, explicitly called `hash_dense_test_baseline`.

All arms use the same documents, authoritative hard filters, top five and current
shared ranking implementation. No business rules or learned reranker are applied.
The learned semantic-only eligibility threshold is cosine >= 0.45. Merchandising
serving additionally requires relevance >= 0.55; this evaluation reports raw
retrieval and final merchandising eligibility separately. A bounded business boost
cannot bypass either a shopper constraint or the serving eligibility threshold.

Report query-level IDs, grades, returned prices, constraints, score components,
NDCG@5, precision@5, recall@5 and reciprocal rank. For no-positive queries report
empty-result correctness instead of manufacturing a relevance denominator.
Report hard-constraint violations and false-positive results separately. Aggregate
by split and query kind; preserve every failure. No inference of business lift.
Runtime metadata records immutable model identity/hashes, Qdrant version, source
fingerprint, actual elapsed times and process peak memory. Same-run repeats are
reproductions, not additional independent cases.
