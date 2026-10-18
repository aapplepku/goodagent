# Private Pre-Launch Security Review

September 6, 2026. Automated Codex review under the owner's private-development
authorization, not an independent certification or owner merge approval.
The frozen RC evidence remains unchanged. This is a new deployment review, not
an extension of the October 5, 2026 expiration.

## Changed Exposure

Only two files in the deployment reachability fingerprint changed from the RC:
`apps/web/src/components/demo-workspace.tsx` and `apps/web/src/app/globals.css`.
The full UI diff was reviewed: invalidating stale drafts, separating recorded
states, formatting metrics, rendering ranking evidence and bounded/linked layout.
React text rendering remains escaped. No HTML injection, dynamic execution,
native command, file/database upload, new endpoint or external request was added.
The existing generated client and same-origin proxy are unchanged.

Backend domain/planner/compiler/policy/executor/search/provider source, locks,
Dockerfiles, Compose, local identity boundaries and storage construction are
unchanged. The new report renderer/capture/workflow tests are development tools,
not request handlers or additional provider capabilities. The Python image copies
the scripts directory, but no runtime route dispatches the report renderer.

## Fresh Evidence

All seven rebuilt ARM64 Compose images were rescanned with pinned Trivy 0.74.0.
Every HIGH/CRITICAL advisory record and normalized scanner context was compared
with the prior retained scan. **268 matched; no new or changed HIGH/CRITICAL
record.** Artifact identities and layer-derived fingerprints were independently
checked against each newly exported image and runtime proof.

| Raw scanner severity | Records |
| --- | ---: |
| CRITICAL | 15 |
| HIGH | 253 |
| MEDIUM | 280 |
| LOW | 285 |
| UNKNOWN | 30 |
| Total | 863 |

The 268 HIGH/CRITICAL records retain per-record runtime scope, installed package,
scanner/version, advisory, reachability/exposure, decision, rationale, evidence,
review date and **2026-10-05** expiry. The decision remains not-applicable only
within the proven simulator deployment, not that the installed source packages
are patched. No advisory-wide exception, severity rewrite or waiver was added.

Fresh proof covers non-root real/effective/saved/filesystem UIDs; empty effective,
permitted and bounding capabilities; no-new-privileges; no setuid/setgid runtime
executables; removed Perl/gzip/infocmp/mount/namespace entrypoints; and absent homed.
Python images constructed PostgreSQL and remote Qdrant with SQLite connections
forbidden. Node/Qdrant native linkage does not include system SQLite. These are
specific proofs, not a claim that a vulnerable library is harmless in every use.

The deployment review concludes zero unresolved applicable HIGH/CRITICAL and zero
untriaged HIGH/CRITICAL **when the exact-record gate passes**. All 863 raw records
remain. Lower severities have not been universally declared inapplicable.
Source audits include the locked Python runtime/build/dev set and all pnpm
dependencies: no known dependency vulnerabilities were reported. Gitleaks checked
nonignored source and all 10 existing commits with verified scan coverage and no
detected secrets. This local history scan predates the new preparation commit;
hosted exact-SHA qualification must cover that commit as well.

## Applicability Sources

The existing advisory/component rules were retained. Primary advisory conditions
were rechecked on the review date: crafted SQLite FTS5 databases/MATCH execution
([11822](https://security-tracker.debian.org/tracker/CVE-2026-11822),
[11824](https://security-tracker.debian.org/tracker/CVE-2026-11824)); privileged
pathname ACL callers ([ACL](https://security-tracker.debian.org/tracker/CVE-2026-54369));
removed command paths ([infocmp](https://security-tracker.debian.org/tracker/CVE-2025-69720),
[GNU gzip](https://security-tracker.debian.org/tracker/CVE-2026-41992),
[Perl](https://security-tracker.debian.org/tracker/CVE-2026-13221),
[mount hooks](https://security-tracker.debian.org/tracker/CVE-2026-76642)); and
absent [systemd-homed](https://security-tracker.debian.org/tracker/CVE-2026-16742).

The installed Debian packages still have vulnerable source-package metadata.
The per-record fixed-version fields mirror the scanner for that installed distro
package. An empty fixed version does not mean no upstream fix exists: the Debian
references include fixes in newer distributions/upstream. Lack of a distro patch
is not the reason for the decision; the demonstrated unavailable attack paths are.

## Reproduction And Retention

New archive: `security/reports/2026-09-06-private-prelaunch-arm64/`.
Its manifest hashes unmodified gzip-compressed reports, nine SBOMs (source,
Python and seven images), image identities, proof and reviewed assessments.
Raw scanner logs and source/history snapshots remain in the separate ignored
private `.opencommerce/prelaunch/` directory. The prior RC archives are not replaced.

The first hosted branch core run at `6df1f84` also passed image/source gates with
the same 863 raw records and 268 scoped HIGH/CRITICAL dispositions. The first PR
run failed strict history coverage because merge diffs were omitted, not because
an advisory or secret finding was suppressed. Both complete raw archives were
downloaded and hash-verified. The corrective history-scan options and regression
are documented in [CI development](CI_DEVELOPMENT.md#merge-history-coverage).
This development-tool change does not alter the deployment reachability inputs,
installed dependencies, permission boundary or assessment expiration. Final exact
branch/PR hosted qualification remains a separate gate.

Run on this branch with the configured dedicated Compose project:

```bash
.venv/bin/python scripts/scan-images.py --output .opencommerce/new-review/images
.venv/bin/python scripts/verify-runtime-images.py --output .opencommerce/new-review/proof.json
.venv/bin/python scripts/scan-source.py --output .opencommerce/new-review/source
.venv/bin/python scripts/check-image-findings.py --scans .opencommerce/new-review/images --proof .opencommerce/new-review/proof.json
```

Use new output directories. Changed findings, scanner context, deployment inputs,
missing reviews, or expiry must fail and receive a new substantive review, never
an automatic fingerprint update. Tests exercise those negative cases. Hosted
branch qualification, normal-review approval, and retained exact-SHA artifacts
remain separate requirements. No public service, live commerce or unattended
real-money safety claim follows from this review.
