# Full Repository Release Review

**Recommendation: MERGE AFTER FIXES and hosted qualification for the private RC.**
September 5, 2026. The historical local review below is superseded where noted.
This review covers the complete simulator implementation and qualification diff,
not only the latest correction. It follows `codex/99_REVIEW_PROMPT.md`. Findings
are evidence-based; merge approval does not authorize a public release or stable
version promotion. GitHub-hosted checks and launch settings remain prerequisites
before publication, not claims established by local testing.

## Open findings

### LOW, retained: local lint discovers generated browser report JavaScript

- Location: `apps/web/eslint.config.mjs:7`, global ignore list.
- Scenario: after a failed browser test generates the HTML trace viewer,
  `make lint` includes its bundled third-party JavaScript and reports unrelated
  lint errors. Clean hosted checkout checks run before browser report generation.
- RC disposition: preserve/move generated `apps/web/playwright-report/` outside
  the source tree before a local full recheck; keep original reports and traces.
  No source lint rule or security/test assertion is disabled. This affects
  repeat-check ergonomics, not runtime measurement or safety state.
- Future minimal correction: explicitly ignore generated Playwright report/test
  output directories and add a fixture proving real source is still linted.
  Deferred from this runtime correction to avoid unrelated configuration churn.

### MEDIUM, corrected in replacement preparation: missing series definitions

- Location: `packages/backend/src/open_commerce/api/demo.py`, `METRIC_DEFINITIONS`
  and `get_metrics_series`; `apps/web/src/components/demo-workspace.tsx`, snapshot refresh.
- Scenario: excess-inventory goals request `units_sold`, but the endpoint rejects
  it with HTTP 400 because the stored-value mapping has no matching definition.
  The combined snapshot request then fails, interrupting outcomes/catalog updates.
  Existing `revenue` mapping has the same registry defect.
- Correction: add definitions for the already stored whole-store metrics; clearly
  distinguish whole-store units from scope-aware objective attainment.
- Tests: both API regressions fail with 400 before correction; the real production
  excess-inventory browser test reproduces the same failure. Targeted API tests
  pass after correction; fresh complete qualification is required.

### MEDIUM, corrected in replacement preparation: misleading measurement values/labels

- Location: `demo.py`, `_metric_value`; `api/schemas.py`, `MetricSeriesPoint`;
  `demo-workspace.tsx`, `MiniBars`.
- Scenario: absent CAC is serialized as zero; every bar is labelled new customers
  even for purchases, costs, rates and profit. Negative profit is clipped to a
  small positive bar. These misrepresent measurement and are not cosmetic.
- Correction: nullable observations in the generated contract, CAC definition v2
  and completeness warnings; metric/unit/date labels, zero baseline and signed
  geometry, explicit unavailable and empty states. No controller/accounting changes.
- Tests: pre-fix API null-CAC and eight frontend cases fail as expected. Targeted
  tests pass after correction; added mixed-sign coverage and two persisted-state
  production scenario regressions. Full qualification remains pending.

### LOW, corrected in replacement preparation: smoke evidence omitted from upload

- Location: `.github/workflows/qualification.yml`, core artifact paths;
  `scripts/record-hosted-evidence.py`, evidence patterns.
- Scenario: attempt 33998180356 hashes a successful smoke journal but omits it
  from the core artifact, and does not hash the completed smoke summary. Full
  benchmark shards retain their separate raw journals, so no safety pass is inferred.
- Correction: upload both smoke files, hash the completed result as well as the
  partial journal. The two retention regressions fail before correction and pass
  afterward. Downloaded original artifacts and job logs remain unchanged.

Candidate `4702a4e5236f451f969f275ce33eb9c421868037` passed the core hosted job and
DCO in [attempt 33998180356](https://github.com/aapplepku/opencommerce/actions/runs/33998180356).
This confirms the earlier build-audit/scanner corrections against that exact SHA:
332 backend/contract, 37 web, eight SDK, 41 integration, three browser, four recovery,
three post-reset browser tests, legal files, all scans and nine fresh SBOMs passed.
Dependabot closed the three original alerts as fixed, not dismissed. The four
benchmark shards were cancelled after discovering the measurement issues above;
all partial journals were retained and verified. The final assembly correctly
rejected incomplete shards. This SHA is not fully qualified; the next candidate
must repeat every hosted check and receive a final complete-repository review.

### HIGH, corrected locally: secret scanner can report success without coverage

- Location: `scripts/scan-source.py`, scanner completion handling.
- Scenario: after the scanner UID fix, Git refused ownership of the read-only
  mirror, but pinned Gitleaks returned zero with zero commits scanned. Exit status
  and an empty findings file alone therefore do not establish history coverage.
- Correction: container-only trust for the exact newly created mirror, retained
  scanner logs, independent commit count and mandatory nonzero/error-free coverage.
  No global safe-directory change or broad trust exception is introduced.
- Tests: false-success, zero/missing/partial scan, warnings/errors, required scan
  call wiring and unconditional hashed/uploaded log retention. Earlier affected
  local outputs are retained as incomplete; hosted confirmation remains required.

### HIGH, corrected locally: isolated build dependencies omitted from audit

- Location: initial `packages/backend/pyproject.toml:28` and `scripts/scan-source.py:111`.
- Scenario: the runtime/dev export omitted setuptools 75.8.0 and wheel 0.45.1,
  allowing a passing dependency scan despite GitHub reporting two HIGH build
  advisories and one MODERATE advisory. Compromised build inputs can affect output
  integrity even when the tools are absent from shipped runtime.
- Correction: exact fixed pins 83.0.0 and 0.46.2, mirrored into the audited lock;
  scanner rejects unaudited build pins. No build-risk waiver or alert dismissal.
- Tests: build-pin coverage, invalid/missing pins and immutable raw assessment
  coverage. Fresh no-cache builds, package/image legal checks and full local
  checks pass. Hosted confirmation remains required.

### MEDIUM, corrected locally: scanners cannot write hosted evidence

- Location: prior `scripts/scan-source.py:159`, `scripts/scan-images.py:68`.
- Scenario: capability-dropped root scanner containers cannot write runner-owned
  mounts; attempt 33996463613 failed source/image scan stages. No scan pass exists.
- Correction: use invoking UID/GID, retaining ALL capability dropping and
  no-new-privileges. All interrupted benchmark journals were successfully retained.
- Tests: command contracts require the owner and restrictions; fresh source and
  seven image scans plus applicability gate pass locally. Exact-SHA hosted rerun
  remains mandatory. See [full correction evidence](BUILD_DEPENDENCY_VERIFICATION.md).

Resumed pre-commit review corrected three qualification gaps before the initial
checkpoint: missing scan-date/automated-review-owner fields, absent npm/pnpm
environment versions, and a HEAD-only RC DCO range that could miss an unsigned
earlier fix. The latter now checks all contributions after the historical base
and the exact owner author identity. Seventy-six focused tests and the full
292-backend/45-frontend-SDK/41-integration local check pass. Raw scan bytes and
runtime deployment inputs are unchanged. Final exact-SHA hosted review remains
pending; these local results do not establish release qualification.

Private hosted qualification is incomplete. Initial SHA
`d490eeccd473e5c8f8cb2e6508679c8035a24e88` passed DCO, full checks, browser and
recovery/reset stages in [run 33994832632](https://github.com/aapplepku/opencommerce/actions/runs/33994832632).
That run was deliberately cancelled during the benchmark after the scheduling
issue below was observed. Logs and the available artifact are retained; scans
were not reached, so this is not hosted security or release qualification.
The repository is private; action pinning, dependency alerts and interim
force-push/deletion/admin-bypass restrictions are configured. Required checks and
review protections still need final verification against passing hosted results.

### MEDIUM, qualification correction: serial hosted sweeps risk the job limit

- Location: initial candidate `.github/workflows/qualification.yml:75`.
- Scenario: early acquisition controller cases took 143-152 seconds on the hosted
  runner versus a 74.64-second local mean. Two local sweeps already took about
  five hours together. The measured slowdown projects beyond the hosted six-hour
  job limit, preventing completion of subsequent security gates.
- Minimal correction: four fixed 25-seed jobs, each reproducing its own full
  30-day cases; separate existing application/security qualification. Assembly
  must verify all 1,200 cases against the committed reference twice, with exact
  SHA/source/hash provenance. No case or safety gate may be removed.
- Tests: shard coverage, missing/duplicate/changed cases, failures, hard violations,
  wrong SHA/source/bytes, summary integrity and the final all-shards-success gate.

### MEDIUM, qualification correction: partial benchmark journals not retained

- Location: initial candidate `.github/workflows/qualification.yml:124` and
  `scripts/record-hosted-evidence.py:36`.
- Scenario: an interrupted benchmark writes `.partial.jsonl`, but upload and
  provenance patterns matched only completed gzip artifacts. Initial attempt
  logs remain available, but its completed case rows were not archived.
- Minimal correction: always upload and hash partial journals, with a shorter
  benchmark-step timeout leaving time for evidence retention and cleanup.
- Tests: a synthetic partial journal must appear in provenance, and workflow
  contracts require unconditional shard artifact upload and timeout headroom.

Final exact-SHA repository review remains pending; these findings are not
dismissed merely because the initial application tests passed.

### MEDIUM, corrected for RC: progress fill assumes a maximizing objective

- Location: `apps/web/src/components/demo-workspace.tsx`, `GoalWizard`.
- Failure: a minimizing CAC objective above its target displayed a full bar.
- Impact: can falsely imply measurement target attainment. This is not strictly
  cosmetic and cannot remain a LOW RC exception.
- Correction: removed the inferred percentage. The server-provided assessment,
  measured value, target and action counts remain visible.
- Tests: five new cases cover maximizing/minimizing, above/below, zero/missing
  values; all 37 frontend unit tests and all three rebuilt-image browser tests pass.

### HIGH, gate correction under validation: incomplete finding identity

- Location: `scripts/check-image-findings.py`.
- Failure: the earlier advisory/package/version match did not bind all changed
  scanner fields or every newly required applicability field.
- Correction: 268 per-record reviews now bind finding/scanner context, deployment
  and rule hashes, runtime scope, fixes, evidence and expiry. Fresh exact-image
  proofs remain mandatory; applicable unresolved runtime risk cannot be waived.
- Tests: 59 focused assessment/image-identity cases pass, including changed findings, missing/expired reviews,
  changed scope/scanner/architecture/deployment and weakened proofs.
  Hosted execution of these gates remains required.

## Corrected findings and negative controls

| Original issue | Correction and evidence |
| --- | --- |
| BLOCKER: owner release terms/private channel absent | Owner supplied Apache-2.0, exact Han Chen NOTICE, DCO 1.1 without CLA and verified private email. Exact text/hash regressions, trusted-base DCO tests, four actual package archives and six project-built image checks pass. Hosted PVR/rules/notification checks remain explicit launch prerequisites. |
| HIGH: native notice table did not establish full legal-file coverage | Preserve 805 original legal/attribution files from 387 source packages, including all 28 native libraries and locked Rust dependencies. Version matching, archive/file hashes, coverage regressions and final actual-image verification pass. Upstream omissions/templates remain explicit, not invented attribution. |
| BLOCKER: process-local authoritative state | Durable tenant-scoped PostgreSQL records, request receipts, leases, attempts, ledgers, outcomes and trace; real restart/pool/process tests. |
| BLOCKER: ambiguous/duplicate execution | Effect and receipt commit atomically in the simulator; durable preparation then reconciliation. Actual exits 85/86 and independent-pool/delivery races pass. This does not establish remote-provider semantics. |
| HIGH: dispatch safety races/incomplete gates | Current policy, target, approval, freshness, budget, horizon, kill switch and simultaneous-intervention rechecks. Explicit adversarial tests and database races pass. |
| HIGH: non-live/non-reproducible retrieval | Deployed remote Qdrant with authoritative catalog gates. Rank-v3 failed 4/12 repeats; rank-v4 passed 12/12 fresh collections and broad checks, preserving all queries and unfavorable results. |
| HIGH: unsupported historical evaluation claims | CLI now executes the durable controller and matched baseline; failed/partial artifacts cannot render as full release evidence. The full 1,200-row generation and independent reproduction pass, including exact raw-row/summary equality and zero hard violations. |
| HIGH: stale browser kill-switch poll | Controlled delayed-read test failed the old image, then both production tests passed after synchronous read invalidation. Backend correctly refused the unsafe plan throughout. |
| MEDIUM: streamed request bodies bypass computation concurrency | Synchronized three-request negative control admitted three handlers against a limit of two. Recheck immediately before dispatch; HTTP/security group passed. |
| MEDIUM: archived measurements poll indefinitely | Real database negative control failed before correction. Early archival now records insufficient data with a termination reason; repeated delivery/pool restart preserves one outcome and existing history. |
| MEDIUM: failed reset hides a newly saved goal | Real kill-switch browser negative control failed the saved-selection assertion. Persisted creation/activation is now selected before later calls; the clean-v3 production regression passed twice. |
| LOW: UUID log correlation over-redacted as a phone | Valid canonical v4 request UUIDs are retained in that context only; phone/email/token values and sensitive fields remain redacted. Negative and positive tests pass. |
| HIGH: environment-dependent generated contract | Clean bootstrap changed version/hash from local `.env`. Canonical validated schema settings ignore environment/dotenv sources; override regression failed old exporter and all six contract/version tests then passed. |
| HIGH: public CLI bypasses durable controller | `controller demo` still selected the legacy process-local service. The command was removed, leaving the durable evaluator and explicitly offline simulator calculations. Its subprocess negative control failed old code and passed the correction, now included in clean-v4 checks and exact-image scans. |
| MEDIUM: full release evaluation can exceed the CI deadline | Two sequential full sweeps plus builds/checks were capped at 180 minutes, while the first local sweep alone exceeded two hours. Release qualification now permits 360 minutes; normal CI remains 180. Hosted runtime is still unverified and a timeout still fails the gate. |
| HIGH: final images lacked complete qualification evidence | Final clean-v4 now passed frozen bootstrap, no-cache build, empty/repeated migrations/startup, full checks, explicit integration, all three browser tests, four outages, complete volume deletion/recreation and post-reset browser tests. Four scanner archives preserve exact identities; no runtime source changed afterward. |
| MEDIUM: release CI overwrote its full benchmark reference | The first command regenerated committed evidence before comparison. It now verifies that committed reference into an ignored primary output, then independently verifies the primary. The structured workflow test failed the old sequence and passed the correction; actionlint passed. |
| HIGH: independent full controller reproduction was unfinished | Independent clean-v3 run exited 0 after 8723.341s. Both complete artifacts validate 100 seeds, 30 days and all 1,200 cases; raw rows and summaries match exactly, with no failures and zero hard violations. The reproduction is preserved as `examples/eval/results/controller-v2-durable-reproduction.json.gz`. |

## Requirement completion

| Requirement | Evidence / current result |
| --- | --- |
| All required durable controller records | Normalized migration 0004 plus worker-failure migration 0005; API uses durable services by default. State survives actual API/worker termination. |
| Tenant isolation and audit immutability | Tenant predicates, composite database constraints, append-only repository operations and immutable audit/ledger triggers; cross-tenant and mutation tests pass. DB owner remains trusted. |
| Domain/provider boundaries | Domain/policy imports are independent of HTTP/provider/UI packages; typed simulator providers and executor-only consequential calls are covered by contract tests and source review. |
| LLM/action adversarial boundary | No remote LLM enabled. Typed parser/planner drafts compile to finite actions; malformed/injected, unsupported, excessive, stale, unapproved and duplicate action tests pass. |
| Restart/fault cases 1-17 | Mapped in `FAULT_VERIFICATION.md`; real services/pools/processes, no in-memory durability substitute. Clean-v4 full and explicit integration runs and all four final container drills pass. |
| Clean install/migrations | Final clean-v4 bootstrap, no-cache build, empty/repeated migration/startup, full checks, volume reset and post-reset browser suite passed. |
| Acquisition cycles, approval, measurement, reset | Eight-cycle database regression and all three production browser tests pass before and after reset, including partial-failure and delayed-read regressions. |
| Controller statistics and zero hard violations | Complete 1,200-row/100-seed/30-day generation and independent reproduction, zero hard violations, exact non-timing raw-row/summary equality, validated distributions and deterministic rendering. No separate fixed-rule baseline exists. |
| Five-mode search statistics/gates | Versioned raw six-query evidence and generated report; NDCG/Recall, constraints, timing, catalog/query/index identities and relevance-safe bounded boost checks. Tiny synthetic benchmark only. |
| Local security defaults and redaction | Loopback-only ports, explicit demo-auth warning, origin/host/CSP/body/rate controls, safe error envelopes, no session cookies or remote telemetry exporter. |
| Dependency/secret/container scans and SBOM | Six versioned archives, including fresh final owner-image scans/proofs/SBOMs. Raw 268 HIGH/CRITICAL entries remain with expiring applicability; none unresolved under that scope. Final source/dependency/history audits pass. Exact-checksum false positive has preserved evidence and negative controls, with no blanket exclusion. |
| Public documentation and metadata | README, tutorial, architecture, threat model, limitations, reset, API, connector boundaries, owner-approved legal/contribution/security policies and candidate report exist. Proposed stable-version patch is checked but unapplied. |
| CI/release workflow | Pinned read-only workflows, locally linted. Not executed on GitHub; no publication job. |
| No live provider/payment/inventory writes | None implemented or configured; future connector design documents are explicitly not deployed capabilities. |

## Commands and limits

Final owner-metadata `make check` passed: 202-file Python lint/format/mypy,
strict TypeScript, 241 backend unit/contract tests, 40 web/SDK tests, goldens,
live search reproduction, durable controller smoke, 41 integrations (91.11s)
and schema/client/legal-copy freshness. Final clean-reset browser suite: 3 passed
(47.4s), with desktop/mobile captures visually inspected. Final image outage suite:
4 passed (20.33s). All actual legal/image proofs pass. Focused DCO/legal/workflow/
six-archive suite: 27 passed (2.34s). All four workflows passed pinned actionlint;
the unapplied version patch passes `git apply --check`, and `git diff --check`
passes. Exact commands and versions are in IMPLEMENTATION_STATUS.md.

The final backend differs from the completed-benchmark runtime only in OpenAPI
license metadata. Controller/search/simulator/persistence logic is byte-identical.
Full artifacts were not regenerated for legal-only changes; their independent
1,200-row reproduction remains preserved and current smoke passes. Native notice
collection does not imply exhaustive native vulnerability coverage or independent
legal certification.

### Earlier validation history

Latest root `make check` passed Ruff/formatting, mypy on 193 files, strict
TypeScript, 214 backend unit/contract tests (42.21s), 40 web/SDK tests, goldens,
live search reproduction, short durable controller reproduction, 41 real-service
integration tests (174.62s) and OpenAPI/client freshness. The subsequent exporter
fix passed its six targeted tests and mypy. Clean-v3's subsequent full check
passed 215 backend tests, 40 web/SDK tests and 41 integrations (378.35s), with all
other check targets passing. The later CLI removal passed its subprocess contract
test and targeted mypy. Final clean-v4 includes it and passed `make check` with
217 backend tests (76.31s), 40 web/SDK tests, 41 integrations (249.30s), 194-file
Python lint/type checks, strict TypeScript and every other check target. Explicit
integration rerun passed 41 tests (259.38s). All four scanner archives pass integrity
validation. All three browser tests passed (1.5m), four outage tests passed (55.72s),
and complete volume deletion/recreation plus all three post-reset browser tests
passed (1.6m). The subsequent workflow-only reference-preservation regression
passed its targeted test/actionlint. Its first workspace rerun stopped on a
missing third-party YAML type stub; after a narrowly scoped test import annotation,
the complete workspace check passed with 195-file Python checks, the 219-test
backend target, 40 web/SDK tests, all benchmark smoke/contracts and 41 integrations
(155.13s). No runtime/image code changed from the final clean-v4 checkpoint.

The clean-v2 clone passed `make bootstrap`, no-cache build, empty and repeated
startup/migration, `make check`, explicit `make test-integration` (40 tests,
180.35s), production `make test-e2e`, `make test-fault` (4 tests, 42.96s), complete
volume deletion/recreation and post-reset E2E (2 tests, 1.1m). Exact environment,
commands, failures and image identities are retained in implementation status and
security archives. Newer code is not silently covered by those earlier images.

Full independent controller reproduction then exited 0 in 8723.341s. Both full
artifacts passed renderer coverage/hash/summary validation; all 1,200 raw rows and
summaries match exactly, with zero hard violations and no failed cases. The same
non-timing hash is recorded in the benchmark methods and implementation status.

The final source audit refresh includes both full artifacts and the workflow
guard. Python/Node dependency scans, source/history Gitleaks and SBOM generation
passed. All five archive integrity tests, six report tests and the workflow test
passed together (12 tests, 0.28s). All 219 checked runtime/configuration/source
files match the clean-v4 image source; only evidence and documentation were added
after that full workspace check. At that historical checkpoint the owner
prerequisite remained a BLOCKER. The follow-up above resolves it; the later RC review above reclassifies and corrects the UI issue.

Not yet completed: GitHub-hosted CI; launch-time PVR, notifications, non-admin
visibility and required-check settings. The owner verified the interim private email.
No amd64, production hosting, real
merchant performance, independent external security certification, remote provider,
calibrated forecast or causal-lift claim is made.

**Recommendation: MERGE AFTER FIXES and hosted qualification.** The earlier local
MERGE recommendation does not establish the stricter private RC gates. Complete
plan 092 and verify the exact hosted SHA before RC acceptance. This document is
not tagging, publication or visibility-change authorization.
