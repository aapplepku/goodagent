# Conversational store-operator agents

The store-operator application is the default local product surface at `/manager`.
The route and backend `manager` namespace remain stable for API compatibility;
**store operator** is the product term for an owner, operator, merchandiser, or
other person running the store.
The preserved simulator diagnostic workspace remains available at `/lab`.

The current self-hosted application starts with authenticated owner setup and the
catalog-first **Products -> Preview -> Ready to share** journey. Upload a CSV,
explicitly choose the sample, or explore without data. Review products and wait for
verified indexing before previewing; sharing is a separate owner action. No sample
catalog is attached implicitly. See [self-service setup](SELF_SERVICE_SETUP.md).

Initial workspace bootstrap skips the older eight-step interview in `self_hosted`
and `hosted`; new-store setup follows the catalog-first journey. The explicit
`legacy_demo` profile still starts with the interview. **Reset manager workspace**
currently starts a fresh interview in every profile, including authenticated
self-service stores; reset is distinct from initial setup. Specialist agent
organization, business goals, engagement and operating preferences can be revisited
after initial setup rather than blocking a useful catalog preview.
In model-backed mode it holds a natural merchant conversation across assortment,
merchandising, operations, growth, customer experience, search, and recommendations.
It can invoke a finite search/recommendation tool set when structured work is useful,
but ordinary chat is not routed through a mandatory workflow. The objective compiler
asks one question when a material choice is missing. For example:

```text
Store operator: Enable semantic search and rank products by popularity.
Agent: How strongly should popularity influence ranking: light, balanced, or strong?
Manager: Balanced.
```

The resulting draft records the target surface, retrieval mode, ranking signals,
popularity strength, minimum relevance floor, installed semantic backend, status,
and canonical review hash. It is not activated in this milestone.

## Agent channels and reply threads

After onboarding, Workspace Home summarizes data readiness, active runs, discovery
drafts, recent agents, and browser-local unread activity. The workspace seeds
`#onboarding` and the selected specialist agents, or its existing starter defaults
when no selection has been saved.
Existing workspaces retain their current agents. Store operators can add, rename,
archive, and restore custom agent channels. Each agent channel owns
its full history, working memory, composer draft, scroll position, and in-flight
status. A channel's purpose is its agent brief: a built-in agent has one
focused function, while a custom channel can explicitly combine several.

Any message can open one durable reply thread in the right drawer. That branch
receives the root message as context and owns separate history and working memory.
Reply threads and channels can run concurrently; replies cannot nest beyond one
level. Drafts, unread timestamps, and scroll positions are browser-local in this
single-manager demo, while channel and reply messages are durable in PostgreSQL.

An explicit **Clear agent history** action removes that channel's messages, reply
threads, working memory, and channel-scoped periodic summaries. It immediately
starts the agent with a fresh introduction. Tenant-level onboarding answers and
explicit long-term preferences are retained. The mutation is tenant-scoped,
idempotent, and versioned so an in-flight reply cannot silently restore cleared
history.

Workspace settings, reset, clear-history and agent create/rename use modal dialogs.
Within the page, keyboard focus stays inside the open dialog; Escape dismisses it while idle and
returns to the initiating control when it is still available. Destructive dialogs
start on a safe control, not their confirmation action. Pending submissions cannot
be dismissed or duplicated; errors retain entered values. An uncertain channel
save or reset retains the exact submitted body and key for explicit retry, including
closing and reopening that dialog while the workspace remains mounted. Inputs
cannot silently change that unresolved operation. This in-memory protection does
not survive a full page reload. If a channel save or reset was confirmed but a
subsequent read failed, retry refreshes current workspace state without repeating
the mutation. Agent actions supports arrow keys, Home/End and Escape,
and closes before opening a child dialog. These controls do not grant permissions
or change the existing explicit confirmation requirements.

The server retains only the reset operation's post-cleanup receipt across later
resets, so retrying its same key cannot erase work created afterward. Other
manager receipts containing old conversational state are still removed. Reset
receipts contain the cleared/default setup result and retained catalog metadata,
not removed messages or memories. They are historical operation results, not a
current channel listing; clients refresh current state after confirmation.
Previously erased reset keys cannot be recovered by this change. Do not manually
purge receipts while an operation may still be retried.

User messages and queued runs are committed immediately. PostgreSQL stores run
events, provider continuation, tool receipts, and completion; ARQ delivers the
work. Model calls run outside database transactions. A partial unique index permits
one active run per conversation, while separate channels/replies run concurrently.
Duplicate submissions reuse their run. A new submission into a busy conversation
receives `MANAGER_THREAD_BUSY`. Clearing/resetting fences old completions and cancels
affected runs so they cannot restore removed history.

## Memory layers

1. **Long-term preference** is cross-thread and created only from explicit language
   such as `Remember that ...` or `I prefer ...`. The store operator can forget these
   records from the Memory panel. The agent does not silently infer durable
   preferences from ordinary conversation.
2. **Working memory** belongs to one thread and contains only the current topic,
   open question, typed discovery draft, and at most eight recent decisions. It is
   replaced as the conversation progresses; the full message history is stored
   separately.
3. **Periodic memory** is an immutable compact checkpoint created every six operator
   turns by default. It captures the current typed objective and latest request,
   not a hidden reasoning transcript. Set
   `OPEN_COMMERCE_MANAGER_PERIODIC_MEMORY_TURNS` from 2 to 50 to change the cadence.

Messages, preferences, checkpoints, and request receipts live in PostgreSQL.
Tenant-scoped message and memory mutations require an idempotency key. In
`self_hosted` and `hosted` profiles, the server resolves owner access from an
authenticated merchant session and store membership, not a browser-supplied
tenant identifier. Only `legacy_demo` uses the configured local tenant and implicit
owner/operator role; that profile is not authentication and must remain local.

## ReAct boundary

The model chooses whether to answer, investigate, use a tool, ask a necessary
question, or finish. Channels supply context, not tool permissions. Recent dialogue,
memory and the channel brief accompany the request; status conversations also get
a fresh observation. Corrections such as "initial setup, not a change" belong to
that context and must not trigger a generic sales-decline script.

The UI inserts the operator message immediately and polls public events every
second while active. Activity describes actual model calls, tool requests/results,
and background waiting. Stop cancels future work; reload recovers the durable run.
Failed/cancelled runs retain their user message, observed findings, and continuation
text. Already completed actions are not silently reversed. Raw reasoning never
appears in public events. Opaque encrypted provider continuation stays private in
the checkpoint, not in the thread API or Activity drawer.

The operator workspace uses an application-owned, bounded model loop when
`OPEN_COMMERCE_MANAGER_MODEL_PROVIDER=openai`. The provider boundary is typed and
does not grant execution authority. Each model response may request at most one
strict function call; the application validates the name and Pydantic arguments,
executes an allowlisted tool, and returns the result for the next model turn. The
loop defaults to 12 model turns, 10 tool calls, and 300 seconds of active execution.
Model-attempt allowance is saved before dispatch, not only after a response. A
worker interruption keeps that spent allowance and the last validated continuation
and tool receipts; lease recovery cannot reset the count. Failure to persist the
checkpoint prevents dispatch. An interrupted attempt may conservatively consume
allowance even if the provider never received it. Daily usage charges likewise
retain uncertain outcomes; these limits are not refunds or exact billing measures.
The corresponding `OPEN_COMMERCE_MANAGER_MODEL_MAX_ITERATIONS`,
`OPEN_COMMERCE_MANAGER_MODEL_MAX_TOOL_CALLS`, and
`OPEN_COMMERCE_MANAGER_RUN_ACTIVE_SECONDS` settings are bounded. Two identical
failed calls are enough: a third identical request stops with the observed blocker.
Background index/recovery waiting releases the worker and resumes from its receipt
without another model call; runs have a separate 15-minute overall age ceiling.
Exhausting either time budget produces `RUN_TIME_BUDGET_EXCEEDED`, not a claim
that a dependency is down. An already-exhausted run starts no tools. Its user
message and completed results remain available for a smaller follow-up run.
The configured `OPEN_COMMERCE_MANAGER_MODEL_TIMEOUT_SECONDS` also bounds the
provider request/body roundtrip in elapsed time, in addition to per-I/O timeouts.
A continuously trickling response therefore cannot keep that await open beyond
the application deadline. External cancellation still propagates and closes local
connections; neither timeout nor Stop guarantees provider-side cancellation.
The model is instructed not to treat status inspection as a restart request.
This conversational-intent rule is prompt guidance, not a per-message code-level
authorization gate. The structural backstops remain local-recovery configuration,
owned-process checks, fresh failure evidence, and a verified recovery receipt;
the supervisor refuses recovery outside the explicitly enabled legacy demo.
Stronger per-operation consent is still needed before expanding that authority.

The first tool set is intentionally small:

- `inspect_data_onboarding` reads the tenant-level non-secret intake draft;
- `draft_data_onboarding` compiles explicit source/cadence choices but does not
  connect or schedule;
- `inspect_discovery_capabilities` reads the installed search/recommendation
  capability contract;
- `draft_discovery_objective` compiles finite objective fields into working memory
  but is explicitly simulated.
- `test_catalog_search` runs the existing tenant-scoped read-only search runtime
  and returns bounded real results with available variants from the active catalog;
  the tool requires `in_stock=true`. Review unavailable products through catalog
  browsing or inventory inspection, not a false stock flag in this discovery tool;
- `inspect_service_status` observes API, PostgreSQL, Redis, Qdrant, catalog index,
  search, recommendations, homepage, manager, and shopper-surface status;
- `configure_status_refresh` persists an explicit 0-60 minute status polling
  interval; five minutes is the default and zero disables automatic checks;
- `inspect_runtime_code` returns a curated, bounded source excerpt for an exact
  allowlisted subsystem topic.
- `inspect_catalog` and `inspect_index_jobs` return catalog readiness and durable job metadata;
- `recover_catalog_index` retries a failed job or rebuilds the active normalized catalog;
- `test_recommendations` returns bounded similar/popular retrieval results;
- `inspect_commerce` returns aggregate observed inventory, order and test-payment counts;
- `repair_local_service` asks the external local supervisor to verify/restart one owned app.

All tools share a typed registry with input/output validation, permissions and
verification descriptions. Index recovery has preconditions, idempotency receipts,
an audit/policy decision and the previous version as rollback metadata. A replacement
becomes active only after count verification. Previous usable projections remain
available during replacement; older versions are retained, with cleanup deferred.

Every model-backed channel also supports practical [everyday store operations](STORE_OPERATIONS.md):
`review_store_day`, `audit_catalog_quality`, `review_inventory_risks`,
`review_checkout_operations`, `review_shopper_performance`, and
`inspect_store_readiness`. These read persisted store facts and propose concrete
next actions, without changing products, stock, payments, sharing or customer data.
Time windows, coverage, unknown/stale stock, demo totals and test-traffic exclusions
are explicit. The model can follow findings with existing search/ranking tests and
requested in-app monitoring. Owner controls still own catalog replacement and sharing.

The code tool cannot accept file paths or inspect the repository, environment,
credentials, generated artifacts, or arbitrary files. Search arguments cannot
select a tenant, and status checks cannot mutate state. In deterministic mode,
explicit `test search for ...` and status questions use the same application-owned
tools. Strategy discussion alone does not execute a search.

Tools can inspect engagement, train real popularity/logistic candidates and preview
them; [activation](ENGAGEMENT_RANKING.md) requires separate operator confirmation.
Arbitrary custom training, online measurement and individual personalization remain
unsupported. No
conversation can execute a commerce write. Model/provider failures return an
explicit temporary-unavailability error; the runtime does not silently pretend a
deterministic fallback was model-backed.

Catalog CSV indexing is now a durable application-owned worker job. A valid upload
is normalized into tenant-scoped PostgreSQL product records, queued through Redis,
and published to Qdrant only after the indexed count is verified. The model sees
only bounded status such as queued/running/ready/failed and product counts, never
raw product rows. [Read-only Shopify intake](SHOPIFY_INTAKE.md) reuses this pipeline.
Warehouse sync and external commerce writes remain unavailable. Assistant Markdown
renders safely, with raw HTML/images and unsafe link schemes disabled.

OpenAI Responses requests use `store=false`, strict function schemas, sequential
tool calls, bounded input/output, and a timeout. Conversation text, recalled
memory, and tool arguments remain untrusted. Common credentials, email addresses,
and phone numbers are redacted before cloud model use; managers must still avoid
entering customer data, production records, secrets, addresses, or credentials.

Intermediate Responses `commentary` is not a finished answer. Both agents continue
within their existing iteration and usage limits, preserving the original message
phase and encrypted continuation even when no tool was called. Manager runs
checkpoint this state before continuing. An incomplete provider response or exhausted
run reports unfinished work, not success. Unfinished/failed turns cannot dispatch or
checkpoint a new tool operation, even if its arguments are valid JSON. Explicitly
incomplete tool/message items are rejected by the Responses adapter before storing
continuation. Already completed tool receipts remain available for recovery.
New pending-call checkpoints bind the accepted completion status to the exact
call. After an upgrade, an older pending call without that evidence stops for a
fresh request instead of executing. Existing completed receipts and messages are
retained; this does not reset the workspace or require a database migration.
Ordinary final conversation and clarification
still need no tool. See the [OpenAI phase guidance](https://developers.openai.com/api/docs/guides/reasoning#phase-parameter).

Default startup remains credential-free with the deterministic interpreter. For a
local model-backed manager demo, place these values only in the ignored `.env`:

```dotenv
OPEN_COMMERCE_MANAGER_MODEL_PROVIDER=openai
OPEN_COMMERCE_MANAGER_MODEL_ID=gpt-5.4-mini
OPEN_COMMERCE_OPENAI_API_KEY=<local-secret>
```

The API returns the active conversation provider and model identifier in
`ManagerAgentCapabilities`; it never returns the credential.

## API

```text
POST   /v1/manager/workspace/bootstrap
GET    /v1/manager/workspace
POST   /v1/manager/workspace/reset
GET    /v1/manager/status
POST   /v1/manager/threads
GET    /v1/manager/threads
GET    /v1/manager/threads/{thread_id}
PATCH  /v1/manager/threads/{thread_id}
DELETE /v1/manager/threads/{thread_id}/messages
POST   /v1/manager/threads/{channel_id}/replies
GET    /v1/manager/threads/{channel_id}/messages/{root_message_id}/replies
POST   /v1/manager/threads/{thread_id}/messages
POST   /v1/manager/threads/{thread_id}/runs
GET    /v1/manager/runs/{run_id}
GET    /v1/manager/runs/{run_id}/events?after=0
POST   /v1/manager/runs/{run_id}/cancel
POST   /v1/manager/threads/{thread_id}/datasets/profile
GET    /v1/manager/memories
DELETE /v1/manager/memories/{memory_id}
```

Bootstrap, reset, create, update, clear-history, reply creation, message, profile, and delete operations
require `Idempotency-Key`. Existing `/threads` routes remain compatible.

The legacy manager dataset-profiling endpoint retains bounded normalized product
and variant fields plus structural metadata and a fingerprint for a valid catalog
CSV; it discards the raw CSV and unnormalized rows after profiling. Self-service
imports instead stage the original CSV encrypted in PostgreSQL during mapping and
review, with a 24-hour expiry. Confirmation or cancellation clears the encrypted
payload. Expiry blocks further review; cleanup clears expired payloads, rather than
guaranteeing deletion at the exact expiry time. Neither flow sends the raw CSV to
the hosted model. Engagement retains only allowlisted normalized events for local
ranking; models see aggregate summaries. Periodic memories cannot be manually
deleted; they are retained as conversation history.

Workspace reset additionally requires the exact `RESET` confirmation token. It
deletes manager channels, replies, messages, manager memories, and onboarding state,
then starts a fresh interview in every runtime profile, including `self_hosted` and
`hosted`. It retains catalog/search records, simulator state, shopper accounts,
shopper conversations, and shopper memory.
Do not enter customer PII, secrets, credentials, or production data in the local
workspace.

## Local runtime and recovery

`make dev-local` starts API, operator, shopper and worker with consistent local
settings. See [LOCAL_DEMO.md](LOCAL_DEMO.md) for migration/startup instructions.
The ignored runtime manifest records actual ports, process ownership and launch
identities, never credentials. Proxies and health URLs use those actual ports.
The supervisor runs outside the API and accepts only finite service IDs: `api`,
`manager_web`, `shopper_web`, `worker`. Model-generated commands, paths, environment
values and PIDs are rejected. Restarts reuse the supervisor's original configuration.

Recovery runs checkpoint into waiting state before the supervisor acts. It checks
fresh failure evidence, fences cancellation, records an idempotent operation and
verifies the resulting owned process/health endpoint (worker: current heartbeat).
Healthy processes are not restarted. A failed verification is not success. The
supervisor cannot repair PostgreSQL, Redis or Qdrant. Five-minute scheduled status
checks only observe; explicit conversation requests can select an allowed repair.

Model configuration is not connectivity: the board reports the last actual model
response and its time, or unchecked/unavailable state. Retrieval availability and
index counts do not establish search quality. Hash-based embeddings remain a test
baseline unless a learned provider is separately configured.

This is a trusted single-operator local runtime, not remote machine administration.
An unavailable worker cannot execute a newly queued investigation; restart the
launcher manually in that case. A supervisor crash is not automatically recovered
or allowed to adopt arbitrary existing processes. A crashed in-flight model request
may be reissued after lease expiry; completed mutation receipts prevent repeated
mutations. Cancellation does not undo a restart already underway.

Migration `0017` adds `manager_runs`, `manager_run_events`, and `runtime_operations`.
Existing messages, catalog, shopper accounts, commerce records and release-security
evidence are retained. The prior image applicability review is stale for the changed
deployment source: its contract gate must remain failing until separately refreshed.
