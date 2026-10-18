# Local Demo Runbook

This runbook describes the simulator checkout, not the future connector roadmap.
Use synthetic data on a trusted single-user machine. Local-demo roles are not authentication.

## Operator development runtime

Keep credentials and provider settings in the ignored `.env`. Local connection
overrides can go in the ignored `.opencommerce/local-runtime.env`; the launcher reads
both without replacing the existing catalog or demo database. Start PostgreSQL,
Redis and Qdrant first using your existing local services or Compose. Do not remove
volumes to restart the applications.

Apply pending migrations using the same local settings, then start the apps:

```bash
.venv/bin/python -c 'from open_commerce.config import Settings; from alembic import command; from alembic.config import Config; import os; s=Settings(_env_file=(".env", ".opencommerce/local-runtime.env")); os.environ["OPEN_COMMERCE_DATABASE_URL"]=s.database_url; command.upgrade(Config("alembic.ini"), "head")'
make dev-local
```

Use the operator and shopper URLs printed by the launcher. It selects free loopback
ports, records them in `.opencommerce/runtime/manifest.json`, and configures API
proxies/health checks consistently. Logs remain under `.opencommerce/runtime/`.
Stopping the launcher stops only its owned apps; it does not delete data or stop
infrastructure. Restart it after changing backend code/configuration. Next.js updates
the UI during development.

Try these in any operator channel with OpenAI configured:

1. "This is a new store. Help me drive more sales." Follow with "It's initial setup,
   not a change" and "Not sure I understand." Replies should use that context.
2. "Inspect my catalog, rebuild the active search index, then test a few useful
   searches and explain the results." Watch verified activity; switch channels or
   reload while waiting. Rebuild does not train a model or prove better relevance.
3. In a status agent, "Check the apps. Fix any supported local connection failures."
   Only an owned app with current failure evidence can be restarted. Unavailable
   infrastructure requires manual attention; scheduled status checks never repair.
4. Use Stop during a run. The message and previous tool findings remain available
   for a follow-up, and completed actions are not silently undone.

For the isolated manager browser test, set the existing local dependency URLs and
`OPEN_COMMERCE_BROWSER_TEST_URL` to the printed operator origin, then run
`OPEN_COMMERCE_RUN_INTEGRATION=1 .venv/bin/pytest tests/integration/test_manager_browser.py`.
The test creates a separate database, tenant, API and worker and never uses the
owner's messages for model prompts. It uses a deterministic test provider; live
model checks are separate.

## Five-minute tutorial

This historical tutorial requires a separate disposable `legacy_demo` installation,
not the authenticated self-hosted installation created by the current README.
Do not change your existing store's profile. For new stores, use the current
[first-store walkthrough](FIRST_STORE_DEMO.md) instead. Some historical onboarding
screens below have since changed; they are not alpha acceptance instructions.
Initial builds/downloads can take longer than five minutes; the walkthrough starts
after all services are healthy.

1. Open `http://localhost:3000/manager` and complete the eight-step essentials
   interview. Use the sample catalog when asked, wait for the Data panel to report
   the indexed product count as ready, or explicitly choose **No data yet** for
   limited exploration. Review and edit answers before opening the workspace.
2. Open `#search`, ask it to "Enable semantic search and rank products by
   popularity," answer its clarification, and inspect the Model and Activity
   drawers. Objective compilation is simulated and cannot activate a model. Open
   another channel while the response is pending, and use Reply on a message to
   verify a durable one-level thread.
3. Open `#status` to inspect live component state. In `#search`, say "Test search
   for a quiet coffee grinder under $150" to run a real read-only query against
   the active manager catalog. Ask how search works to let the model inspect only
   the allowlisted, secret-free search implementation excerpt.
4. Say "Remember that I prefer concise model summaries." The preference appears
   in long-term memory; ordinary conversation stays in working/channel history.
5. Open `http://localhost:3001`, create a local shopper account, and ask "Find a
   quiet coffee setup under $150 for a small apartment." Start a second
   conversation, sign out and back in, and verify both conversations remain.
   Say "Remember that I prefer quiet coffee gear" to create an explicit shopping
   preference, then remove it from the Shopping memory drawer.
6. Choose **Add** on a grounded product. Open the cart, adjust quantity, and select
   **Review checkout**. Use **Test decline** once to inspect the retry state, then
   **Approve test payment** to create a demo order. No card data is requested and
   no money moves. Return to `/manager`, open the commerce icon beside Settings,
   and inspect the order, payment, reservation, and unchanged observed inventory.
7. Open `http://localhost:3000/lab`, choose acquisition and leave seed 42. Enter
   "Acquire 200 new customers in 30 days with a $10000 budget." Select **Draft**,
   review **New goal review** and warnings, then **Activate and run**. The
   alternative scenario **Run scenario** button uses its fixed defaults.
8. Read the saved goal and proposal. Default goals require approval. A goal that
   is already on track may produce no proposal; that is not a failed job.
9. Select an awaiting-approval action and choose **Approve hash**. Approval binds
   the exact compiled action and policy version. Wait for the worker's recorded
   success/reconciliation, not just the approval acknowledgement.
10. Choose **Advance one day** repeatedly. The worker schedules subsequent cycles
   using virtual time. Wait for pending actions before advancing again: advancing
   a full day can expire an unanswered proposal. Measured outcomes normally use a
   seven-day window, capped by the goal horizon, with minimum sample requirements.
11. Reload. The URL's opaque goal ID or saved-goal selector recovers committed state.
   **Pause goal** prevents new execution; **Kill switch on** blocks further writes.
   Neither automatically reverses prior effects or stops already-budgeted campaign
   spending when you explicitly advance the simulator.
12. Try a stock/price-filtered query in the search panel and compare the five modes.
   Search boosts cannot bypass relevance, stock or price constraints.
13. Change the seed and choose **Reset seed**. A fresh goal is created and the old
   goal is archived. The old approvals, actions and audit are not erased.
   An archived goal's unfinished measurement closes as insufficient data, not a
   fabricated successful experiment. If a kill switch prevents the new goal's
   first plan, that goal remains selected; resolve the cause and use **Run
   controller** rather than creating another replacement.

Natural-language drafting is a deterministic parser, not an LLM. Review its typed
output and warnings. It parses a limited target, horizon and budget vocabulary;
other requested constraints are not silently accepted. The current goal-creation
contract uses the documented default CAC/margin/discount constraints.

The default count target can be much easier than the synthetic shop's historical
trajectory. Changing it to a larger target changes planning, but does not make the
heuristic forecast a calibrated probability. Only physical inventory bounds justify
the current explicit infeasible classification.

After the uploaded catalog reports ready, verify the active manager catalog through
the shopper search API:

```bash
curl --fail --json '{"query":"travel organizer","mode":"hybrid","top_k":5}' \
  http://localhost:8000/v1/search
```

The response `catalog_id` identifies the active uploaded catalog. Omitting a goal
context prefers that catalog; passing a simulator goal continues to use its own
catalog. The default signed-hash dense backend is a deterministic test baseline,
not a learned semantic model. Use the pinned local MiniLM option documented in the
search guide when learned semantic retrieval is required.

## Startup and ports

The default is credential-free deterministic manager conversation. To use the
OpenAI-backed conversation loop, set the provider, current model, and credential
only in the ignored `.env` as documented in `docs/MANAGER_AGENT.md`, then recreate
the API container. Never put the credential in `.env.example`, Compose YAML, logs,
screenshots, or tracked files.

```bash
docker compose ps -a
curl --fail http://localhost:8000/health/ready
```

`migrate` is expected to exit 0. API, worker, manager web, shopper web, PostgreSQL,
Redis and Qdrant should remain healthy. API liveness alone does not establish
dependency readiness. Web health endpoints establish only web-process liveness.

If a port is occupied, set a different `WEB_PORT`, `SHOPPER_PORT`, `API_PORT`, `POSTGRES_PORT`,
`REDIS_PORT`, `QDRANT_PORT` or `QDRANT_GRPC_PORT` in `.env` before starting Compose.
The browser uses its own same-origin proxy, so changing the web port does not
require rebuilding a public API URL into JavaScript. Host-side validation commands
need matching `OPEN_COMMERCE_DATABASE_URL`, `OPEN_COMMERCE_REDIS_URL` and
`OPEN_COMMERCE_QDRANT_URL`; `PLAYWRIGHT_BASE_URL` must match the manager web port
and `SHOPPER_PLAYWRIGHT_BASE_URL` must match the shopper port.

## Troubleshooting

- **Docker cannot connect:** start Docker Desktop or the selected local Docker
  engine. Do not switch contexts or delete other projects' volumes to repair this demo.
- **Migration/readiness fails:** inspect `docker compose logs migrate api` and
  `docker compose ps -a`. Verify the three dependency services are healthy.
- **Approval stays pending:** inspect `docker compose logs worker` and its health.
  PostgreSQL retains pending work if Redis is unavailable; restored delivery can
  take a bounded retry interval. Do not create a new goal merely to retry an action.
- **Action becomes cancelled/expired:** inspect policy/audit/trace. Changed policy,
  changed target, kill switch, exhausted budget or stale observations can correctly
  close the execution gate. Plan a new proposal after resolving the cause.
- **429 response:** wait for the local per-minute rate window. Rapid automated
  requests share the same process quota. This is separate from the budget ledger.
- **Qdrant unavailable:** search fails closed with a safe 503, not a silent local
  fallback. Restore Qdrant and reindex the relevant goal with the CLI below.
- **Historical UI looks unchanged:** confirm the selected saved goal and virtual
  day. Only the latest run is shown in the current workspace; older runs remain
  accessible through the API. The initial service-meta panel is not a continuous monitor.
- **Custom minimizing objective:** the overview shows observations and the target,
  not a percentage-complete bar. Inspect the direction in **Saved goal / Exact
  configuration** and the persisted assessment. A numerical ratio is not an
  approval, execution, measurement or rollback decision.
- **Ambiguous execution:** retain the durable attempt and reservation. Restore
  dependencies and let the worker reconcile. Do not manually erase receipts or
  blindly submit provider commands. Simulator reconciliation is not proof of real-provider semantics.

```bash
uv run commerce-agent search reindex --goal <goal-uuid>
uv run commerce-agent search query 'outdoor under $100' --goal <goal-uuid>
```

Use the local uv path `.tools/uv/bin/uv` if bootstrap installed it there and `uv`
is not in PATH. The CLI search uses the configured live local Qdrant service.
Use the browser/API for saved controller goals; the legacy process-local
`controller demo` entry point is no longer available. `controller evaluate` uses
disposable PostgreSQL databases. The engine-only `simulator run` and `simulator
golden` commands intentionally compute offline results without creating saved
controller goals and must not be used as durability evidence.

## Restart and reset

```bash
docker compose restart api worker
```

This preserves PostgreSQL-authoritative state. Redis can be rebuilt without
losing execution receipts. Qdrant indexes can be reconstructed; PostgreSQL cannot.

For a fresh UI scenario, use **Reset seed**, which preserves prior history.
To stop this project without deleting its data:

```bash
docker compose down
```

**Destructive local reset:** the following removes this Compose project's named
PostgreSQL, Redis and Qdrant volumes, including all saved goals and audit history.
Check the active project name and back up any data you need first. Do not run it
against a project belonging to someone else or while a benchmark uses its PostgreSQL server.

```bash
docker compose down --volumes
docker compose up -d --wait
```

To uninstall the demo, stop/remove its project as above, then remove only this
checkout and its optional local tool/dependency directories. Do not prune unrelated
Docker images, volumes, credentials, contexts or global runtimes.

## Verification and captures

```bash
make check
make test-integration
make install-browser
make test-e2e
```

Playwright exercises the running Compose API/worker and emits screenshots under
`apps/web/test-results/`, including desktop, mobile and a durable-goal view.
Use seed 42, a fresh goal and the committed test flow for comparable captures.
Browser/version, viewport and initial saved state affect screenshots; these are
not byte-identical image benchmarks. Trace/screenshot failure artifacts are local
and can contain synthetic goal data. No GIF or remote image hosting is automatic.
An optional recording can be made from the same flow with a local screen recorder;
review frames and remove unrelated desktop/private content before any separately
authorized public sharing. The [six-scene asset workflow](DEMO_ASSETS.md) uses an
isolated browser and fresh project, records actual metrics and file hashes, and
does not publish anything.

Run destructive outage tests only on a dedicated project:

```bash
COMPOSE_PROJECT_NAME=opencommerce-fault WEB_PORT=53000 API_PORT=58000 \
POSTGRES_PORT=55430 REDIS_PORT=56370 QDRANT_PORT=56330 QDRANT_GRPC_PORT=56331 \
docker compose up -d --build --wait

COMPOSE_PROJECT_NAME=opencommerce-fault WEB_PORT=53000 API_PORT=58000 \
POSTGRES_PORT=55430 REDIS_PORT=56370 QDRANT_PORT=56330 QDRANT_GRPC_PORT=56331 \
make test-fault
```

These tests stop/restart services. Do not run them concurrently with benchmarks,
integration tests or browser tests using the same project. Tests restore services
they stop; an externally interrupted test may require a manual `compose up`.
