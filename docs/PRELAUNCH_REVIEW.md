# Private Pre-Launch Review

Local review checkpoint, September 6, 2026, on `prep/public-preview`.
Not merge or publication approval. Hosted results must be read for the exact
branch and PR revisions; this committed checkpoint does not predict their outcome.
Scope: plans/093-private-prelaunch.md. Frozen RC source and evidence are unchanged.

## Initial Findings (Before Changes)

| Severity | Location at frozen RC | Failure scenario / impact | Minimal correction and regression |
| --- | --- | --- | --- |
| HIGH | apps/web/src/components/demo-workspace.tsx:880 | Goal text edits do not invalidate a previously parsed draft; Activate can submit old target/budget or scenario defaults rather than the displayed text. Exact review also shows draft/default content when a different saved goal is selected. | Invalidate on edits, require a reviewed draft, separate persisted goal from new draft; test edits after parsing, scenario changes and saved-goal review. |
| HIGH | .github/workflows/ci.yml:17 | main requires Private RC and DCO plus full reproduction, but normal CI produces neither with full-benchmark=false. Future development cannot satisfy protections. | Emit equivalent required contexts with private, trusted-base DCO and full qualification on development/PRs; retain RC workflow, pinning and review; contract and hosted tests. |
| MEDIUM | apps/web/src/components/demo-workspace.tsx:1864 | Monetary formatting discards cents, so a measured CAC of $1.34 looks like $1. Missing margin renders 0%. | Preserve cents and distinguish absent measurements; focused metric tests. |
| MEDIUM | apps/web/src/components/demo-workspace.tsx:1117 | Policy still says require approval for an already executed action with no immediately visible approval or reconciliation record. Estimates are unlabeled raw interval JSON. | Separate historical proposal policy, approval, execution/reconciliation, and measurement with real provenance; test pending/executed/insufficient cases. |
| MEDIUM | apps/web/src/components/demo-workspace.tsx:1020; globals.css:414 | Long technical trace pushes outcomes and search far below the fold; no navigation. Future Shopify teaser competes with implemented workflows. | Compact existing layout, landmark navigation, bounded trace scroll and actual evidence summaries; desktop/mobile browser inspection. |
| MEDIUM | README.md:7; docs/SECURITY_VERIFICATION.md:149 | Landing docs lead with qualification; historical prose says hosted workflows have not run despite subsequently approved hosted evidence. | Product-first README and dated current-state addendum; preserve raw historical reports and frozen-tag identity. |
| LOW | apps/web/eslint.config.mjs:7 | Generated Playwright failure reports can pollute lint after a failed browser test. | Ignore only generated test-results/playwright-report folders and retain source lint coverage. |

The old minimizing-objective progress bar issue is already fixed in the frozen
RC and covered by tests. No new progress percentage will infer attainment from a
ratio; persisted assessment and numeric measurements remain authoritative.

## Current Findings

- BLOCKER: none found in the reviewed local implementation. Hosted qualification
  is still a required verification gate, not an assumed pass.
- HIGH: the stale-draft failure is fixed and exercised in the production browser.
  The missing CI contexts are corrected with real signed/unsigned Git-history
  tests; hosted push and PR context verification remains required.
- HIGH (hosted discovery): `scripts/scan-source.py` omitted merge diffs, so PR
  history coverage failed at 11/12 even though push core qualification passed.
  Corrected log options include both ancestries and merge-resolution patches;
  exact coverage remains mandatory. A real Git regression is added; corrective
  hosted qualification is required before closing this verification finding.
- MEDIUM: benchmark breadth remains limited to six synthetic search queries and
  seeded simulator dynamics; impact estimates are uncalibrated and the default
  acquisition target is easy for the baseline. See [all results](BENCHMARKS.md).
  Before broader claims, add independently designed scenarios and held-out data;
  retain all arms and seeds. No such model changes belong in this polish goal.
- MEDIUM: a scripted walkthrough and first-screen review do not establish that an
  unassisted stranger understands the product in 30 seconds or finishes in five
  minutes. Conduct a small private first-use study before public preview; record
  comprehension, completion time and mistakes without coaching or favorable edits.
- LOW: raw trace/action JSON is still technical, and the mobile trace uses a bounded
  scroll region. A private novice study should check keyboard navigation and whether
  the visible summaries answer the five product questions before expanding polish.

No unresolved finding here can misrepresent approval, policy, execution,
reconciliation, measurement or rollback as successful. Missing state remains
explicitly missing. No backend contracts, migrations, planner, search algorithm,
simulator golden, policy or executor behavior changed.

## Validation

Local results on the final product source, September 6, 2026:

| Check | Result |
| --- | --- |
| `make check` (includes lint, typecheck, test and integration) | PASS |
| Backend unit/contracts | 354 passed after merge-history regression; two local-Qdrant capability warnings |
| Type checking | 210 Python source files; strict web/SDK TypeScript passed |
| Frontend / SDK units | 54 / 8 passed |
| PostgreSQL/Redis/Qdrant integration and migrations | 41 passed; one upstream Redis-close deprecation |
| Production Compose browser smoke | 5 passed, including stale-draft regression |
| Isolated Compose outage/recovery | 4 passed; services restored |
| OpenAPI/client freshness, legal source sync, local-path check | PASS |
| Local built-package legal proof | 4 archives passed; no publication |
| Local built-image legal proof | 6 built images passed; upstream Redis separately covered by notices/SBOM |
| Four pinned workflows / new contracts | actionlint passed; signed and unsigned contribution ranges tested |
| Simulator goldens, five search modes, short controller regression | PASS; reference data unchanged |
| Asset capture | Six real PNGs, hashes verified; 1440px desktop and 390px mobile inspected |
| Fresh source/container/security proof | [Scoped review and raw counts](PRELAUNCH_SECURITY_REVIEW.md) |

The merge-history correction also passed a local pinned Gitleaks 8.30.1 fixture:
four clean commits were covered, the old mode omitted the merge, and the corrected
mode detected and blocked a harmless sentinel introduced only in merge resolution.
No real credential was used. Dependency/source/history rescans passed. The
coverage gate itself and HIGH/CRITICAL applicability rules were not relaxed.

Cached image build plus empty-volume startup took 96.82 seconds. The final
healthy-stack six-scene capture took 104.417 seconds and sampled seven real runs.
These are separate measurements on macOS ARM64 with a local ARM64 Docker VM,
cached images/dependencies and Chromium 140.0.7339.186. They are not a cold-download
or unassisted-human timing guarantee. Optional video generation is documented but
no video was recorded or presented as evidence.

The full 1,200-case controller reference and independent reproduction are retained
from the frozen qualification. Local polish checks reproduce goldens, search and
the short controller regression, not a new full sweep. New full hosted shards and
independent reproduction remain mandatory in both push and PR qualification.
See [branch workflows](https://github.com/aapplepku/opencommerce/actions?query=branch%3Aprep%2Fpublic-preview).
The delivery report must distinguish the branch SHA from GitHub's PR merge revision.

## Protection Review

Read-only GitHub settings inspection confirmed both `main` and
`release/v0.1.0-rc1` still require one PR approval, stale-approval dismissal,
up-to-date branches, resolved conversations and the three GitHub Actions contexts:
`Private RC and DCO`, `qualification / verify`, and
`qualification / Full controller reproduction`. Administrator bypass, force pushes
and deletions remain disallowed. No protection settings were changed.

The independent trusted-base DCO workflow is retained. Proposed workflow files
still need human review: a contribution can change its own PR workflow definition,
so checking the policy script from the base is not a blanket guarantee against a
malicious workflow change. Required review must not be bypassed. The PR author
cannot supply their own required approval; an eligible reviewer is needed before
any separately authorized merge. No reviewer access was granted by this work.

## Completion Audit

| Owner criterion | Evidence / remaining gate |
| --- | --- |
| 1. Isolated development branch | `prep/public-preview`, directly based on frozen main; no merge |
| 2. Frozen RC unchanged | Tag object and peeled SHA verified; final remote check required |
| 3. Private repository | API and settings inspection; recheck after private push |
| 4. Product-first README | Identity, loop, quick start, real hero and visible experimental status |
| 5. Approximately 30-second comprehension | First-screen editorial review; independent human study not performed |
| 6. Approximately five-minute demo | Keyless Docker path and timed scripted walkthrough; cold-download caveat |
| 7. Obvious agent loop | Overview, semantic persisted trace, architecture control-model comparison |
| 8. Search differentiation | Actual score/filter evidence and canonical actuator diagram |
| 9. Safety architecture | Typed action, policy, approval, idempotency and authoritative-state boundaries |
| 10. Reproducible honest benchmarks | Generated all-mode/arm report, raw hashes and verification tests |
| 11. Reproducible assets | Fresh-stack capture script, six inspected PNGs and provenance manifest |
| 12. Coherent contributor docs | Code map, real extension protocols, DCO and test commands |
| 13. Truthful security wording | Scoped summary, all raw records, new review and unchanged expiry |
| 14. Implemented versus roadmap | Explicit feature matrix and separately labeled conceptual interfaces |
| 15. Natural main CI | Corrected proposal; exact hosted push/PR checks still required |
| 16. Qualification preserved | Local gates passed; reusable/RC workflows unchanged; full hosted gate required |
| 17. No unresolved BLOCKER/HIGH | Local fixes verified; cannot close hosted verification before it passes |
| 18. Nothing public or published | Private-only assets/evidence; no release, registry, website or visibility action |

## Recommendation

**DO NOT MERGE** at this checkpoint. Complete exact-revision hosted checks and
normal independent review; owner merge authorization is separate. Prefer **further
private product polish** next, focused on unassisted comprehension and demo tests.
Shopify shadow mode should follow a separate scoped approval after those findings,
not begin automatically. The public [release checklist](PUBLIC_RELEASE_CHECKLIST.md)
also retains contact verification, expiry refresh, public-CI policy and explicit
visibility/publication decisions. No public readiness or production safety claim
is made by passing local checks.
