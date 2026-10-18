# Historical Simulator Implementation And Qualification Status

Prepared September 5, 2026, with the September 6 update below. This is a historical
simulator record, not current store-alpha status or qualification. Local evidence
is not hosted release evidence. At this record's date, private v0.1.0-rc1 hosted
qualification was incomplete. Its release report and execution plan are retained
privately, outside the public source export. See [historical RC notes](releases/v0.1.0-rc1.md)
for the later RC outcome, and the [current overview](../README.md) and
[security qualification guide](SECURITY_VERIFICATION.md) for current boundaries.

Update September 6 (UTC): candidate `4702a4e5236f451f969f275ce33eb9c421868037`
passed hosted core tests, DCO, scans and nine fresh SBOMs. It is superseded after
review reproduced missing units/revenue definitions and misleading CAC/chart
measurements. Its full benchmark was cancelled with all partial journals retained.
The [review](RELEASE_REVIEW.md) records the minimal corrections and regressions;
every hosted check must run again on the new signed-off SHA. No full hosted
qualification, tag or publication is claimed by the historical results below.

The private repository `aapplepku/opencommerce` contains initial signed-off SHA
`d490eeccd473e5c8f8cb2e6508679c8035a24e88` on `release/v0.1.0-rc1`. Its hosted
attempt passed clean setup/build/migrations, 292 backend/contract, 45 web/SDK,
41 integration, 3 browser, 4 recovery and 3 post-reset browser tests plus DCO,
legal and remaining complete-check targets. The run was cancelled during the
benchmark after hosted timing exposed a job-limit risk; security scans had not
started. Four 25-seed jobs with independent reproduction and an exact-SHA full
assembly gate now replace serial sweeps; partial journals are retained. This
qualification-only correction requires a new signed-off SHA and complete rerun.
Full-SHA action pinning, Dependabot alerts/graph and interim no-force/no-delete/
no-admin-bypass branch restrictions are configured. Required-check/review
protections and the final exact-SHA repository review remain pending.

The scheduling follow-up `040138e0850dd54d993aa82a7f1952f546b80127` also remains
unqualified: hosted scanners could not write runner-owned bind mounts. Its
application/recovery checks passed, and all four interrupted benchmark journals
were retained. Replacement preparation fixes scanner ownership without restoring
privileges and patches build dependencies omitted by the earlier audit. Fresh
local `make check` passes 321 backend/contract, 37 web, 8 SDK and 41 integration
tests, plus all other targets. See [build qualification corrections](BUILD_DEPENDENCY_VERIFICATION.md)
for raw findings, assessments and rebuilt-image evidence. A new candidate must
pass every hosted gate and final review; no hosted pass is claimed here.

## Delivered scope

PostgreSQL owns tenant-scoped goals, observations, actions, policy decisions,
version-bound approvals, attempts, idempotency receipts, budgets, measurements,
trace and kill switches. Redis carries recoverable identifiers. Qdrant is a
reconstructable remote index. Five migrations initialize the durable simulator
runtime. Typed executor gates remain mandatory; no live commerce or advertising
provider, inventory quantity write, remote LLM, or production identity is enabled.

## Last completed local qualification

Private RC preparation now also passes full local `make check`: 283 backend/contract,
37 web and 8 SDK tests, 41 integrations (90.53s), and all other check targets.
Three rebuilt-image browser tests and four recovery tests pass. Fresh raw scans,
per-record assessments and SBOMs are in the private RC preparation archive; the
private release report lists their hashes and limits. No hosted
run, remote setting or RC commit is established by those results.

These September 5 results precede private RC preparation and are not presented
as tests of its later workflow or assessment changes.

| Check | Recorded result |
| --- | --- |
| Full repository check | Ruff/format/mypy on 202 Python files; strict TypeScript; 241 backend unit/contract tests; 32 web and 8 SDK tests |
| Real services | 41 integration tests, 91.11 seconds |
| Browser after complete volume reset | 3 tests, 47.4 seconds; desktop/mobile screenshots inspected |
| Container recovery | 4 outage drills, 20.33 seconds |
| Contracts | OpenAPI, generated client and legal copies current |
| Workflow/legal/DCO/archive focus | 27 tests, 2.34 seconds; all four workflows pass pinned actionlint |
| Distribution legal coverage | Four actual package archives and six project-built image filesystems checked |
| Image privilege checks | All seven Compose images: non-root, no capabilities, no-new-privileges, removed components |
| Security archive | Six checkpoints with 27 hash-linked files each; raw scans preserved, dependency-export comment redactions explicitly recorded |

Environment: macOS Apple Silicon host with a Linux ARM64 Docker VM (4 CPUs,
8 GiB RAM, 50 GiB disk); Python 3.12, uv 0.8.15, pnpm 10.17.1. Node host 25.2.0,
image Node 22.23.2. Temporary checkout names, personal paths, socket locations and
isolated local port allocations are intentionally omitted. Original local
provenance is retained privately; raw scan identities and hashes remain in
[security reports](../security/reports/).

## Evaluation evidence

Full controller generation and an independent reproduction each contain 1,200
cases: seeds 0-99, three scenarios, two variants, two matched arms, and 30 days.
All non-timing rows and summaries match exactly. Each has zero failed cases,
zero hard-policy violations, 1,100 executed simulator actions and zero rollbacks.
Rollback is separately exercised by fault tests. Durations were 9,190.011 and
8,723.341 seconds. Non-timing hash:
`sha256:a1aeb60320deb3a202a6bc00ac1397f25a0d8b3a59bd2c74ecbe2cd321328e76`.

Artifacts: `examples/eval/results/controller-v2-durable.json.gz` and
`controller-v2-durable-reproduction.json.gz` in the same directory.
The [generated report](benchmarks/controller-v2-results.md) preserves unfavorable
and no-action results. Default excess-inventory/search goals often need no action;
there is no separate fixed-rule baseline or causal-lift claim.

The [search report](benchmarks/search-v2.md) records five modes and six synthetic
queries. Rank-v4 reproduced in 12/12 fresh collections, with zero hard violations
and 16 boosted results. Prior rank-v3 failed 4/12 repeats; the correction is
documented rather than removing unfavorable cases. Current non-timing hash:
`c058a63aa2bb6910553b55e0f75cdeaf0b8c641b9c5b09ddf0afcbcf81c59172`.

## Portable clean-clone procedure

Use a disposable checkout, the owner-confirmed private remote and exact RC SHA.
Do not run outage/reset commands against an ordinary development stack.

```bash
git clone "$PRIVATE_REMOTE" opencommerce-rc-validation
cd opencommerce-rc-validation
git checkout --detach "$RC_SHA"
test "$(git rev-parse HEAD)" = "$RC_SHA"
cp .env.example .env
export COMPOSE_PROJECT_NAME=opencommerce-rc-validation
export OPEN_COMMERCE_DATABASE_URL=postgresql+asyncpg://opencommerce:opencommerce@127.0.0.1:5432/opencommerce
export OPEN_COMMERCE_REDIS_URL=redis://127.0.0.1:6379/0
export OPEN_COMMERCE_QDRANT_URL=http://127.0.0.1:6333
export PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000
make bootstrap
docker compose build --no-cache
docker compose up -d --wait --wait-timeout 180
docker compose run --rm migrate
make check
make install-browser
make test-e2e
make test-fault
docker compose down --volumes
docker compose up -d --wait --wait-timeout 180
make test-e2e
```

The workflow also performs full independent evaluations, package/image legal
verification, source/history/dependency/image scanning, per-record applicability,
SBOM generation and DCO. Exact commands are versioned in
`.github/workflows/qualification.yml`. Default ports must be free; any overrides
must be applied consistently to Compose and client URLs.

## Remaining limits

Hosted ARM64 qualification, required repository protections and final hosted
artifact verification are pending. AMD64, public hosting, real merchant results,
calibrated forecasting, live providers and independent security/legal certification
are not established. Local identity is trusted-demo identity, not production auth.
The revised UI removes inferred progress percentages rather than deriving a
second measurement or policy decision in the browser.
