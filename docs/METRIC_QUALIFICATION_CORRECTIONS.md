# Metric Qualification Corrections

September 6, 2026 (UTC). Preparation for a replacement private RC, not final
hosted qualification. No migrations, simulator accounting, controller policy,
approval, execution, budget, reconciliation or rollback behavior changes.

## Completed local validation

`make check` passes: 338 backend/contract, 46 web and eight SDK tests, 41 real-service
integration tests (81.50s), lint/format, mypy on 208 Python files, strict TypeScript,
goldens, real Qdrant search, durable controller smoke and generated/legal/path checks.
All five production browser tests pass (5.0m including quota pacing); desktop/mobile
screenshots are inspected. Four recovery drills pass (25.37s). Four workflows,
four package archives and six built-image legal checks pass. Complete source/history
scans include all nine existing commits and 53 Python runtime/dev/build distributions
plus 383 Node dependencies; those strict dependency audits report no advisories.
Image raw findings and limitations below remain, so this is not a zero-vulnerability
claim. Nine fresh local SBOMs and all raw reports are in the 28-file archive below.
Final staged scanning and every exact-SHA hosted check remain necessary.

## Reproduced defects

The pre-fix API returned HTTP 400 for both existing `units_sold` and `revenue`
series because their stored-value mappings lacked definitions. The production
excess-inventory page reproduced the 400 and failed its combined snapshot update.
Unavailable CAC was serialized as string zero. Charts labelled all series as new
customers and clipped negative profit to a positive minimum bar. These are two
MEDIUM measurement findings, not cosmetic progress defects.

Missing definitions now describe whole-store totals, explicitly distinct from
the controller's scope-aware goal assessment. The nullable series contract and
CAC v2 definition preserve missing observations; page warnings indicate them.
Chart labels use the actual metric, units and UTC date. Negative and positive
values lie on opposite sides of zero; missing/empty observations are not bars.
Five API regressions, nine component cases and two persisted-state production
browser scenarios cover these corrections. Before correction, three API cases,
eight component cases and both production scenarios fail for the expected reasons.

Core artifact verification also found a LOW retention gap: a successful smoke
journal was hashed but not uploaded, and its summary was not hashed. Both files
are now retained and included in provenance. Two regression assertions reproduced
the missing coverage before correction. Full benchmark shard uploads were intact.

The first expanded five-case browser run passed both new scenario cases but the
longer acquisition case reached the unchanged production computation quota
(HTTP 429). Independent test workflows now wait for the actual 60-second quota
window between cases. Limits, concurrency gates and every assertion remain intact;
no mutation is blindly retried and no production configuration is weakened.

Local full rechecks also exposed a LOW tooling limitation: the ESLint configuration
does not ignore generated Playwright HTML/trace JavaScript. Preserve those reports
outside `apps/web/` before rerunning source lint; do not disable lint rules. Hosted
clean-checkout qualification runs source checks before generating browser reports.

## Deployment re-review

Fresh no-cache builds change exactly five reviewed runtime inputs: the API metric
aggregation module and response schema, the generated TypeScript client, the chart
component and its CSS. No dependencies, container isolation, provider construction,
database/storage choices, native invocations or upload paths changed. Every fresh
HIGH/CRITICAL record matches the previous advisory/package/version/severity/fix
metadata; only image-derived fields differ. No advisory fields are excluded from
the gate, and the stale deployment review was rejected before this re-review.

All seven new runtime proofs show non-root processes, zero effective/permitted/
bounding capabilities, no privilege gain and no setuid/setgid runtime executables.
The affected Perl, GNU gzip, infocmp, mount/namespace and systemd-homed entrypoints
remain absent. The libacl finding still requires a privileged path-based caller,
which these routes do not introduce. Python images still construct PostgreSQL and
remote Qdrant with SQLite forbidden; Node/Qdrant native dependency proofs remain
free of system SQLite. The metric aggregation and browser formatters introduce
none of the advisory-required invocation or malicious-database paths.

This supports refreshing all 268 exact record assessments to the new image/source
identities under the same narrowly scoped rules. Reviews are automated by Codex
with accountable project owner Han Chen, not independent certification or human
endorsement. Review date is September 6; expiry remains October 5, 2026. Original
reports, per-record assessments and nine SBOMs are preserved in
`security/reports/2026-09-06-metric-corrections-arm64/` when complete.

Raw image findings remain 863: 15 CRITICAL, 253 HIGH, 280 MEDIUM, 285 LOW and
30 UNKNOWN. The 268 HIGH/CRITICAL records are scoped not-applicable, not patched
packages or accepted applicable runtime vulnerabilities. Lower-severity native
findings, two Qdrant rand advisories with fixes and incomplete native advisory
coverage remain limitations. Public hosting, other architectures, host maintenance
or changed deployment invalidate these conclusions and require new qualification.

The next signed-off candidate must independently rebuild and repeat all hosted
checks, full controller reproduction, scans and SBOMs before final repository
review. No result from a superseded SHA transfers to it.

The September 6 refresh exposed stale contract-test fixtures combining September 5
raw scans and a frozen prior date with current assessments. Three positive controls
failed closed. Fixtures now load the current immutable review archive and review
date, requiring an accepted baseline before each negative mutation. Explicit
future-date, expiry, metadata and identity rejection tests remain; the production
gate still evaluates the actual UTC date and unchanged October 5 expiration.
