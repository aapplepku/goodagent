# Controller-only deployment review

Reviewed 2026-09-07. Hard expiration remains **2026-10-05**. Private simulator
development evidence, not a release approval or independent security certification.

Six controller source files changed relative to the preceding merchandising
review. Package locks, native libraries, serving, provider dispatch and Compose
isolation are unchanged. Exact API-image source hashes match pre-outcome commit
`e11c226f60b0d1895726ae20887a6044a4d4f948`. Source inspection found no new shell,
subprocess, SQLite/FTS5, ACL, mount, Perl or executable-compression invocation.
Fresh exact-image probes verify non-root users, zero capabilities, no-new-privileges,
removed entrypoints, no setuid executables and remote-only storage construction.
The learned encoder runs with network disabled and SQLite constructors forbidden.
Its pinned model files and dependencies are unchanged; this is not a generative model.

Trivy 0.74.0 reports **863 raw records: 15 CRITICAL, 253 HIGH, 280 MEDIUM,
285 LOW and 30 UNKNOWN** across seven images. The unchanged strict gate passes
268 per-record not-applicable assessments, zero untriaged/unresolved applicable
HIGH/CRITICAL findings, and no accepted applicable HIGH/CRITICAL waiver. These are
deployment-specific reachability decisions, not patched-library claims. Raw
lower-severity findings remain; root maintenance, different deployments, unknown
vulnerabilities, native coverage gaps and production exposure are not cleared.

The first review attempt correctly stopped on a changed advisory fingerprint.
Comparison with the prior raw archive identified 35 References-only differences
across seven advisories: vendor errata URLs changed for Red Hat, AlmaLinux and
Rocky. All other advisory fields, versions, fixes, severity, descriptions and
scanner context match. The complete before/after data and hashes are retained in
`scan-reference-changes.json.gz`. Fresh records bind the exact new fingerprints;
no field is exempted by the CI gate and no assessment rule was broadened.

Raw scans, seven image SBOMs, source/Python SBOMs, audit outputs, per-record
assessments, runtime proofs and compressed/uncompressed hashes are retained in
`../reports/2026-09-07-decisions-v2-arm64/manifest.json`. Extra image-source,
learned-runtime and legal proofs are listed in `changed-input-review.json`.
The legal check covers six locally built images; no distributable package archive
was produced. Upstream Redis was pulled unchanged, not published.

Frozen-source pip-audit 2.10.0 and pnpm 10.17.1 report no dependency findings.
Gitleaks 8.30.1 reports no leaks over the frozen nonignored source and all 20
available commits. Later result/report commits are not retroactively included in
that source snapshot. Trivy source-SBOM license collection has dependency-tree
coverage limits; retained third-party notices and exact-image legal checks are
separate evidence, not a comprehensive legal opinion.

The blocked Ollama runtime evidence is unchanged: 74 raw findings, including
43 HIGH/CRITICAL records still blocked. The daemon remains disabled. No paid
fallback, new model call, package/image publication or live provider is enabled.
