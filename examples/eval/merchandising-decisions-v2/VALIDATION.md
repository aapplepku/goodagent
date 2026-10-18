# Local validation and open blockers

Runtime freeze: `e11c226f60b0d1895726ae20887a6044a4d4f948`. Subsequent local
commits record security review, a browser assertion correction and documentation,
not new decision rules. No migration, new public endpoint or package-lock change.
The registered held-out process completed all 36 arms and exited zero; its
hash-verified results and adverse cases are in HELD_OUT_FINDINGS.md.

## Repository checks

`make check` completed successfully on macOS arm64, Python 3.12.11, pinned
pnpm 10.17.1, against isolated local PostgreSQL/Redis/Qdrant. Integration uses
uniquely named disposable databases. Existing demo databases were not reset.

- Lint and strict Python/TypeScript checks pass (278 Python source files).
- 514 backend/contract tests and 79 web/SDK tests pass.
- 77 real-service integration tests pass; one explicitly opt-in live-model test
  is skipped. SQLite connections are forbidden in the durability test processes.
- Three unchanged simulator goldens, the legacy search-quality reference and
  twelve-case three-day controller smoke pass. This smoke is not the full
  1,200-case hosted benchmark; original hosted artifact assembly is documented
  separately under `hosted/DIAGNOSIS.md`.
- OpenAPI/SDK freshness, legal files and portable release-path checks pass.
- Warnings remain for local-mode Qdrant test options and ARQ's deprecated Redis
  close method. They are not suppressed.

Timing, raw-log location and SHA-256 are in `validation/repository-check.json`.
The final browser assertion has separate passing lint/type checks. Repository
checks do not include a claim that browser or Docker health checks passed.
After the held-out run completed, an additional archive-integrity regression
checks that the committed summary equals the independently recomputed result,
with all 36 arms and the exact pre-outcome source identity. It imposes no profit
target. The focused evidence/archive/applicability suite passes 85 tests in
6.16 seconds; final test lint/format and portable-path checks also pass. The
earlier full-run count remains 514 rather than retroactively adding this test.

## Browser results

The initial seven-workflow run passed one and failed six. One failure was in the
new merchandising assertion: a candidate-summary reason was expected inside the
timeline's event JSON, which does not display that summary. The corrected test
checks completed UI state and the typed saved-run decision separately. It passed
in 3.7 minutes, including actual PDP serving, recorded economics, persistence and
1440/390-pixel layout checks; screenshots were inspected. No product UI changed.

After full integration completed, the task's own test app containers were
restarted unchanged and the other five workflows were retried once. Kill-switch
reset recovery passed; goal-revision display, two historical metric workflows
and the broad historical durable browser workflow still failed on timeouts or
temporary-unavailable responses. Several recorded HTTP requests took about
15 seconds before a 503, matching the unchanged proxy deadline. The metric API
itself could return the expected series while a separate baseline/catalog fetch
prevented the page from loading it. These are **not** passed workflows or evidence
that the browser is robust under this load. No deadline or safety gate was widened.

Three distinct workflows passed across these runs, four remain unverified. This
is not a seven-test suite pass. All original traces/screenshots remain local with
hashes and request/error metadata in `validation/browser-evidence-reviewed.json`.
The earlier `browser-evidence.json` is the retained pre-retry checkpoint.

## Local worker health

The new stack's migration exits zero and its API/dependencies/web start, but
`docker compose up --wait` failed on worker health. The unchanged probe's measured
import time was 9.004 seconds, followed by 1.073 seconds for successful database
and Redis heartbeat checks, versus a five-second Docker deadline. The worker
also completed real browser planning jobs. See `validation/worker-health-diagnostic.json`.
This explains this observed health failure, not a healthy Compose result or an
established latency SLA. More than 50 containers share the local Docker host.
Only this task's three app containers were temporarily stopped/restarted; prior
stacks and all data services were preserved. Broader cleanup needs owner consent.
After all browser attempts finished, the task's own three app containers were
stopped again to release resources; the old merchandising demo and all data
services remain running. This is not a new healthy demo deployment.

## Security and remote state

The [changed-input review](../../../security/decisions-v2-review/README.md)
retains 863 raw image findings, including 268 HIGH/CRITICAL, with zero unresolved
under exact deployment-specific assessments. Raw records, source/image SBOMs,
hashes, reference-metadata changes and native/runtime/legal proofs remain intact.
Expiration is still 2026-10-05. Lower severities, native coverage and other
deployment limitations remain; this is not zero vulnerabilities.

Seven contributions through the initial uploaded head
`66ef369b33dfa7a994578480c02595baeafc22f6` pass the exact-SHA DCO checker. After
explicit owner authorization, that head was independently verified on private
`feature/merchandising-decisions-v2` and draft PR #4 was opened against exact base
`5962b51571a10b84c787a6d8a06aa3b884ce4275`. The earlier rejected upload and
absent-ref checkpoint remains in `validation/remote-state.json`; it is historical,
not the current delivery state.

PR run 34153571264 completed failure in three seconds. Authorization job
101840633342 has no steps and no retained log blob; qualification was skipped.
Execution stopped before source checkout; no hosted code test ran and no retry
was dispatched. Private provider annotations and internal account details are
not part of the public export. The unchanged original delivery record remains
private; the [sanitized execution summary](validation/hosted-public-summary.json)
retains its hash, timestamps, failed authorization and skipped qualification.
Original repository/PR/run links require access to the private repository.

The repository remains private; parent PRs and main/RC branch/tag are unchanged.
The committed twenty-commit source audit is not claimed to cover later evidence
commits. A separate source/dependency/secret audit at the initial uploaded head
passes all 23 available commits; raw outputs remain local, not retroactively
inserted into the earlier archive. The final documentation-only delivery commit
and its DCO/source-audit status are reported after it is pushed.

Ollama has no listening port, the separate blocked model-runtime findings remain
blocked, and no real generative model or paid fallback was called.
