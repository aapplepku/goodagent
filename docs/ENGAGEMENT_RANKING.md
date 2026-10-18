# Engagement-based search ranking

The local runtime builds real popularity and scikit-learn logistic regression
candidates. A discovery draft remains just a draft; `train_search_ranker` queues
actual CPU fitting and reports held-out evaluation.

## Try it

1. Upload and index a catalog, then upload matching engagement in Data or chat.
   Older profile-only engagement uploads must be uploaded again.
2. Ask: "Inspect the engagement signals and build a search ranker to increase
   purchases. Use logistic regression if the data supports it."
3. In the Model drawer, inspect metrics and the artifact hash. Enter a query to
   preview baseline versus candidate results.
4. Only candidates passing the offline baseline gate can be applied. Review and
   explicitly confirm the exact model. The agent cannot activate it. Restore baseline
   disables the model without deleting it.

The approved ranker serves both apps on the same catalog. Training is not proof of
better search quality or increased sales.

## Inputs and evaluation

CSV limits: 512 KiB, 64 columns, 10,000 rows. Normalized events retain product ID,
type, UTC timestamp, a tenant-hashed deduplication key and optional tenant-hashed
session ID. Raw CSV, queries, visitor IDs and extra fields are discarded. Direct
identifiers and secret-like values are rejected. Models see only aggregate counts,
targets, metrics and safe errors, never event rows or session hashes. Session hashes
are pseudonymous data, not anonymization; use non-personal test data.

Supported events: `search`, `impression`, `click`, `product_view`, `add_to_cart`,
`purchase`. IDs must match the active catalog. Conflicting duplicate IDs, timestamps
without timezones and future events fail validation. The agent selects a finite
target from merchant goals and available signals. Profit/revenue/retention and vague
improvement goals require an explicit supported proxy. A tool goal must match a
recent merchant-authored message. No executable training code is accepted.

- Popularity uses log-scaled target counts from earlier 70% of timestamps; held-out
  product-level NDCG@10 is compared with stable identifier order.
- Logistic regression uses earliest 30% for historical features, middle portion for
  fitting, last 30% for evaluation. Features are historical product views and smoothed
  click/cart/purchase rates, not user/query features.
- Conversions require a product view and same-session/product target within 30 minutes.
  Click prediction requires impressions; search events are not impressions. Repeated
  exposures collapse per session/product; boundary-crossing and immature examples drop.
- Logistic needs 40 train and 20 held-out exposures with five positives and negatives
  in each split. Seed 42, fixed parameters and frozen features make fitting reproducible.
  Held-out labels do not enter fitting or a later refit.
- Held-out log loss versus a constant training-prevalence predictor gates logistic
  activation. AUC is reported too. Popularity must meet its held-out baseline. These
  are offline diagnostics, not an online experiment or causal lift.

ABO-associated engagement is synthetic, not Amazon customer behavior. Its purchase
candidate scored 0.46713 held-out log loss versus 0.46692 constant baseline, AUC
0.45937: activation was correctly blocked. A separate deliberately learnable synthetic
fixture verifies the successful approval path, not business performance.

## Durability and serving

Migration `0018` adds tenant-scoped immutable snapshots and leased ranking jobs.
PostgreSQL checkpoints state; ARQ workers fit with up to three interrupted-lease
attempts. JSON-only artifacts store coefficients, scores, cutoffs and library version
with SHA-256 hashes. No pickle or model code is loaded.

Approval checks exact hash, current catalog, expected active model and offline gate,
and records an idempotent policy/rollback receipt. Replacement catalogs do not inherit
an older catalog's model. Eligible relevance-sorted candidates get at most 10% base-score
boost. Exact identifiers, explicit sorting, price and stock filters stay authoritative.

Cancelling an operator run does not cancel an already-queued fit; it may finish as an
inactive candidate. No automatic retraining, XGBoost, query-aware learning-to-rank,
personalization, experiments, deletion UI or production distribution yet.

APIs: `GET /v1/manager/ranking`; `POST /v1/manager/ranking/train` (idempotent job),
`/preview` (read-only comparison), `/approve` (explicit apply/disable confirmation).

References: [LogisticRegression](https://scikit-learn.org/1.8/modules/generated/sklearn.linear_model.LogisticRegression.html)
and [data leakage](https://scikit-learn.org/stable/common_pitfalls.html).
