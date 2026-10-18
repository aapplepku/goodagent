# Requested Product Improvements

Owner-requested backlog. These are not implemented capabilities or release dates.

## Next: Product Knowledge Enrichment

During catalog onboarding, offer an explicit AI enrichment step that researches
products, proposes tags and useful talking points, and persists approved knowledge
for grounded shopper and operator answers.

Prerequisite from Plan 122 evaluation: fix comparison query decomposition,
grounded variant lookup and selection of displayed recommendation cards. Adding
research cannot compensate for retrieving the wrong product or comparing only one
side of a requested comparison. Keep that acceptance gate explicit.

- Resolve exact product/variant identity before researching. Prefer manufacturer
  documentation and authorized merchant sources; record URLs, retrieved dates,
  source excerpts, provenance, confidence and supported product identifiers.
- Separate catalog facts, independently sourced facts and generated suggestions.
  Mark conflicts and unknown attributes. Do not infer safety, health, certification,
  compatibility or sustainability claims from appearance or marketing language.
- Store versioned, tenant-scoped product knowledge in PostgreSQL, linked to catalog
  version and variant where applicable. Track approval, expiry, refresh status,
  source rights, cost and the model used. Catalog replacement invalidates stale links.
- Show proposed tags/talking points for review, allow correction/deletion, and
  retain the unchanged original catalog. No automatic external store writes.
- Treat web/catalog content as untrusted data. Typed extraction, approved retrieval
  tools, SSRF controls, budgets and prompt-injection isolation are required.
  Never send shopper PII, credentials or raw engagement rows to a research model.
- Retrieve relevant approved facts when answering, provide source attribution,
  and admit uncertainty. Do not put the entire catalog into each model context.
- Acceptance: exact-match/conflict/unknown tests, tenant and variant isolation,
  stale-source refresh, resumable bounded jobs, editable review and grounded answers
  that never turn unsupported proposed tags into verified product claims.

## Future: Understand Shopping Behavior

Study consented shopping behavior to help merchants identify discovery friction,
unmet needs and useful merchandising improvements. Start with aggregate insights,
not individual surveillance or unsupported claims of causal sales impact.

- Build on existing typed search, selection, cart and demo-checkout telemetry.
  Separate real visitors, previews, samples and automated traffic. Demo totals
  are not revenue; clicks alone do not establish preference or search quality.
- Define explicit purposes, consent/opt-out where needed, retention and deletion.
  Use tenant-scoped aggregates with minimum cohort sizes; exclude sensitive
  inferences and never expose shopper identities or raw private conversations.
- Propose testable hypotheses with sample sizes, uncertainty and evidence.
  Evaluate bias, seasonality and confounding before personalized ranking or
  causal claims. Any later experiments require review and controlled measurement.
- Explain insights and suggested actions in the operator app. Keep approval,
  budgets and commerce-write boundaries unchanged.
- Acceptance: event validity, bot/sample exclusion, deletion propagation,
  small-cohort suppression, isolation, reproducibility and honest unknown states.

## Current Work

The [first-store walkthrough](FIRST_STORE_DEMO.md) covers reviewed catalog import,
grounded agent demonstrations and interrupted demo-checkout recovery. Current work
is self-hosted alpha reliability and qualification; product knowledge and behavior
learning remain deferred until that work is reviewed.
