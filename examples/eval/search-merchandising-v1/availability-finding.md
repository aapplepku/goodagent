# Retained Availability Failure

The original `development.json` and `held-out.json` are immutable first-pass
evidence for the registered v1 source fingerprint. They are not replaced by fixes.

The held-out variant fixture exposed a HIGH product correctness finding: catalog
normalization considered `inventory > 0` but omitted the variant's `available`
flag. An unavailable first variant with stock could therefore satisfy a budget
filter and supply a displayed price. The independent evaluator, unlike the
returned filter flags, checked both conditions against the fixture state.
First-pass violation records: lexical 36; learned dense 42; hybrid 42; hash 42.
These are repeated returned-result records, not distinct security advisories.

Fix: require both availability and positive stock in variant and product search
documents. Normalization version changes so existing projections rebuild. Regression
tests exercise sparse/dense/hybrid through both in-memory and Qdrant implementations.
No relevance threshold, embedding, query, judgment or ranking weight was tuned.

The same now-exposed queries may be rerun only as a **post-fix regression**, with a
separate output and source fingerprint. They are no longer unseen held-out evidence.
The initial failed held-out run and its unfavorable results remain reportable.
This fix does not eliminate false-positive relevance or query-parser limitations.
# Legacy Regression Reference
`legacy-availability-regression.json` is a separate replay of the historical
six-query dataset after the availability projection version changed. Every
non-timing result row and the quality-evidence hash match the unchanged
`examples/eval/results/search-v2-live.json`. Only catalog/template provenance and
runtime metadata/timings differ. `make benchmark-search` verifies this new
projection identity; a contract test enforces full non-timing equality with the
historical results. This replay is not additional search-quality evidence.
