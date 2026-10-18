# Private Model Planning Milestone

Simulator only. One local Ollama adapter; no external paid provider, real commerce
connector, autonomous model execution or trained merchant prediction model.
The deterministic no-key controller remains the default. Model-backed mode never
substitutes deterministic output when the local backend fails.

## Current Evidence

Development integration uses Ollama 0.33.3 with Qwen3 4B Q4_K_M. It can return
structured responses, but early results do **not** establish useful planning.
A goal-extraction attempt omitted the total budget and invented a source quote;
the independent validation gate rejected it. A separate operator-reviewed typed
goal completed two real planning cycles, both no-action. Model summaries contained
incorrect numeric comparisons and unsupported on-track claims. There were no
real-model-triggered approvals, executions or measurements in those two cycles.
Mocked integration tests cover those paths separately and label their source
`replay`, not real-model qualification. The ten-case development comparison then
completed 30 real model calls: all no-action, zero tools/proposals, and outcomes
identical to no intervention. It does not support useful model-backed planning.
[Full comparison, trace and unfavorable results](benchmarks/planning-capability-v1-results.md).

Further live/held-out validation is **LIVE_MODEL_VALIDATION_BLOCKED**. A separate
scan found 43 HIGH/CRITICAL records in the optional Ollama runtime; it was stopped.
Those records are not covered by the default application's prior dispositions.
[Security scope and retained blocking assessment](MODEL_PLANNING_SECURITY.md).

## Opt-In Local Setup

Use a patched, rescanned, operator-approved local Ollama installation, not the
currently blocked retained 0.33.3 build, on the same host as the Python API and
worker. Start it on `127.0.0.1:11434` with `OLLAMA_NO_CLOUD=1`; confirm the server
log reports cloud disabled. Download a local model explicitly, not from app startup.
Record `/api/version`, `/api/tags` and the downloaded runtime/model hashes. The
operator's local-only attestation is a trust assumption, not remote attestation.

The development model manifest is:
`sha256:359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
Do not assume a mutable model tag still points there: the adapter checks the pinned
digest before every inference and rejects uninstalled or cloud-relay models.

Set `OPEN_COMMERCE_MODEL_ENABLED=true`,
`OPEN_COMMERCE_MODEL_LOCAL_ONLY_ATTESTED=true`, `OPEN_COMMERCE_MODEL_ID`, and
`OPEN_COMMERCE_MODEL_DIGEST` in the host API/worker environment. No credentials are
needed or accepted. The URL must be a literal loopback HTTP origin; DNS names,
credentials, paths, redirects and inherited proxies are rejected.

Default Compose does not add a model service or bridge to a host model. Opted-in
model planning currently requires host Python API/worker processes; their Postgres,
Redis and Qdrant endpoints can use explicitly mapped local Compose ports. Do not
expose the model server, API or demo identity through a tunnel or public interface.
Run migrations through `0007_inference_journal` on the chosen development database.
Never migrate the retained frozen-RC evidence database in place.

## Review And Safety

- `POST /v1/goals/draft` chooses deterministic or model-backed interpretation.
  Model mode requires a stable `Idempotency-Key`; retries reuse recorded work.
- `POST /v1/goals/review` validates a directly supplied typed configuration without
  inference. It explicitly labels its source `typed_review`.
- A draft contains the objective, scope, direction, target, horizon, budgets,
  constraints, preferences, allowed actions, warnings and review hash. Missing,
  unsupported, contradictory or ungrounded values do not become an active goal.
- `PATCH /v1/goals/{goal_id}` accepts an exact reviewed replacement and
  `expected_revision`. The new semantic revision invalidates unstarted proposals
  and pending approvals. In-flight uncertain execution must recover first.
- Model investigation sees allowlisted current observations, budget-ledger balances,
  prior actions, pending windows and aggregate outcomes. Customer data, catalog
  prose, source code, seed, hidden demand parameters and future events are omitted.
- Five typed read-only tools inspect products, inventory, campaigns, search and
  outcomes. Missing attribution remains unavailable. There is no SQL, filesystem,
  shell, arbitrary HTTP or direct mutation tool.
- Three finite proposed action families enter the existing compiler, authoritative
  safety-fact reconstruction, policy, exact approval, reservation, executor,
  reconciliation and rollback paths. Model statements are never policy evidence.
- Model summaries are unverified statements, not authoritative business outcomes.
  The compiler's existing intervals remain uncalibrated heuristics. Zero model
  confidence is an unavailable sentinel, not an empirical probability.

## Limits And Recovery

Default cycle limits are four model requests, three tool calls, 1,024 output tokens,
16,000 input-message bytes and 60 seconds per request. At most two proposals per
decision are accepted. There are no automatic model retries. Schema, context,
usage, tool, stale observation and budget failures stop without a fallback action.
Worker deadlines cover the entire configured cycle plus bounded overhead; recovery
leases exceed those deadlines. The browser draft proxy allows at most 100 seconds
for the single interpretation call; ordinary proxy requests retain 15 seconds.

PostgreSQL reserves conservative token capacity before dispatch. All reservations
count toward a separate lifetime goal scope (40 requests / 720,000 tokens) and
UTC tenant-day scope (150 requests / 2,700,000 tokens); goal-draft requests share a
separate draft scope. Merchant budget entries are never used for inference costs.
Reservations include schema/framing overhead, are not refunded, and may exceed
reported actual usage. Report both. Local provider fees are zero; electricity,
hardware, downloads and wall-clock operator cost are unmeasured, not free.

Completed responses are replayed after restart. A dispatched request with a live
lease is pending; an expired request without a committed response becomes
uncertain and is not automatically reissued. Its reservation remains consumed.
Goal/observation revisions are checked again after inference and before compilation.
Only settled responses can advance the planning checkpoint. Settled journal
evidence cannot be updated or deleted by normal application writes.

Raw inference records contain bounded synthetic prompts/responses, model identity,
template/schema hashes, usage, elapsed time and provenance. Do not add real merchant
inputs. Private chain-of-thought is neither requested nor retained from the provider's
separate thinking field. The local database and model daemon remain trusted components.

## Validation

Ordinary tests use replay fixtures and require no model or credentials. Live model
tests require both `OPEN_COMMERCE_RUN_INTEGRATION=1` and
`OPEN_COMMERCE_RUN_LIVE_MODEL=1`, the explicit model settings above, a disposable
PostgreSQL admin endpoint, and `OPEN_COMMERCE_MODEL_TRACE_OUTPUT` for retained JSON.
Run `tests/integration/test_live_model_trace.py` separately. Its planner fixture
is independent of its interpretation subtest; inspect `interpretation_passed` and
actual action counts, not just the test exit code.

The separately registered [capability evaluation](benchmarks/planning-capability-v1.md)
uses matched keyed exogenous draws and does not replace the frozen benchmark.
Development smoke traces are not held-out decision-quality results.

## Official Integration References

[Ollama chat API](https://docs.ollama.com/api/chat),
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
[tool calling](https://docs.ollama.com/capabilities/tool-calling),
[local-only configuration](https://docs.ollama.com/faq),
[Qwen3 4B model](https://ollama.com/library/qwen3:4b).
Checked September 6, 2026. Only the structured chat endpoint performs inference;
the app never invokes Ollama download, shell, search or commerce tools.
