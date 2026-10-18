# Build Dependency Qualification Corrections

September 5, 2026. These are local preparation results for a replacement private
candidate, not hosted release qualification or a zero-vulnerability claim.

## Findings

GitHub Dependabot found two HIGH and one MODERATE alert in the initial candidate's
PEP 517 build requirements. The prior runtime/dev export omitted these pins.
This is a HIGH scan-coverage gap, even though the tools are not installed in the
shipped runtime. The reports and every reproduced record are retained under
`security/build-tool-findings/2026-09-05/`.

| Package / old pin | Advisory | Severity | Fixed pin selected |
| --- | --- | --- | --- |
| setuptools 75.8.0 | CVE-2025-47273 / GHSA-5rjg-fvgr-3xxf | HIGH | 83.0.0 |
| wheel 0.45.1 | CVE-2026-24049 / GHSA-8rrh-rw8j-w5fx | HIGH | 0.46.2 |
| setuptools 75.8.0 | CVE-2026-59890 / GHSA-h35f-9h28-mq5c | MODERATE | 83.0.0 |

The pinned pip-audit 2.10.0 reproduction returns five raw records: two entries for
the setuptools HIGH advisory, two for its MODERATE advisory, and one wheel HIGH
entry. Thus there are three raw HIGH records, two MODERATE records and three
distinct advisories. Duplicate records are preserved, not silently dropped.
GitHub's three alerts are a separate view of the same advisories, not three
additional distinct vulnerabilities. GitHub does not disclose a scanner version
for its hosted service. Its alerts have not been manually dismissed.

These packages run during building, outside the HTTP/controller execution path.
The vulnerable functions process package-index URLs, unpacked wheels or source
manifest exclusions. Dependency/checkout compromise is relevant to build
integrity even with read-only CI credentials; build-only status is not a waiver.
Both exact pins are upgraded and mirrored into the audited development lock.
`scan-source.py` now rejects any workspace build requirement without the same
exact audited pin. Its existing strict, hash-locked audit fails on any advisory;
there is no build-risk suppression. The patched dependency report includes
setuptools 83.0.0, wheel 0.46.2 and packaging 26.3 with empty advisory lists.
Future advisories still require a fresh scan and review.

## Image Re-Review

Fresh no-cache builds and all seven privilege/component proofs pass. The changed
deployment inputs are only the root development pins, backend build pins,
`uv.lock`, and generated `open_commerce_backend.egg-info/PKG-INFO` (metadata 2.4
under the updated builder). The runtime dependency declarations are unchanged;
the rebuilt API's installed distributions exclude setuptools and wheel.

All 268 HIGH/CRITICAL image records still exist. Forty-five CVE-2026-78408 records
changed their advisory fingerprint: LastModifiedDate changed and a disclosure
reference was added. The raw severity, affected package/version and vulnerability
description did not change. The existing gate rejected the new deployment before
review; neither date nor reference was removed from fingerprint validation.

The current [upstream nsenter advisory](https://github.com/util-linux/util-linux/security/advisories/GHSA-55fx-f4gg-cfhj)
requires privileged namespace-entry activity. Fresh runtime probes establish that
nsenter is absent and containers remain non-root with no capabilities or privilege
gain. The added disclosure-mail URL could not be fetched by the web reader; the
current upstream advisory and direct component/privilege evidence support the
same narrow non-applicability conclusion. Host administrator debugging outside
these images is not covered. Upstream fixes 2.41.6/2.42.3 exist; Trivy does not
report a fixed version for the installed Debian package. Per-record fixed-version
fields retain that scanner-specific distinction.

The updated 268-record review binds fresh image IDs, original raw report hashes,
all advisory fields, and deployment hash
`0759008e9fcb971987371ac802c17cdcbd4381186efa7b0c9e447a3a40b2f7d1`.
All remain scoped not-applicable under the unchanged rules, with October 5, 2026
expiry. This is an automated review with accountable project owner Han Chen,
not independent certification or human endorsement. Raw counts remain 15 CRITICAL,
253 HIGH, 280 MEDIUM, 285 LOW and 30 UNKNOWN. No applicable runtime waiver exists.

## Hosted Scanner Permissions

Attempt 33996463613 failed because scanner containers with all capabilities
dropped could not write runner-owned bind mounts. Scanner commands now use the
invoking UID/GID. Capability dropping and no-new-privileges remain enforced.
Local report creation under that identity passes; exact-SHA hosted verification
must confirm the Linux runner behavior. Failed logs and available raw outputs
are retained, not represented as successful security scans.

Final pre-staging log review found a second HIGH coverage gap: after the UID
change, Gitleaks 8.30.1 returned exit zero even though Git refused the mirror's
ownership and zero commits were scanned. Those local outputs are retained as
incomplete, not accepted evidence. The earlier build-tools archive uses the
pre-UID source scan, whose log confirms all eight available commits were scanned.
The correction trusts only the newly created read-only `/repo` mirror through
container-scoped Git environment settings, never a wildcard or global host
configuration. Both secret scans now retain logs and reject scanner errors,
warnings, zero scanned bytes or missing coverage; history also requires the
exact independently counted available commit total. Negative tests cover false
exit-zero, partial, missing and warning/error logs. This deliberately fails closed
if a future history shape or pinned scanner log format needs renewed review.
Hosted provenance and uploads retain these scanner logs even on failure.

Rebuilt local browser tests pass (3, 57.0s), with desktop/mobile screenshots
inspected. All four container outage/recovery drills pass (21.79s). There are no
runtime behavior, migration or live-provider changes in these corrections.

The replacement candidate must rebuild and rerun all hosted checks, including
complete controller reproduction, fresh scans/SBOMs and the final repository
review. No tag, merge, visibility change or publication is authorized here.
