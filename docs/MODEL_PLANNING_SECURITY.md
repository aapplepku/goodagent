# Model Planning Security Review

September 6, 2026. Automated engineering review, not independent certification or
permission to merge. The repository, model traces and security evidence remain private.

## Two Different Runtime Scopes

The default Compose application and the optional operator-installed model daemon
are separate artifacts. A passing application image gate does not qualify the
daemon. No model binary, weights or paid-provider credentials are shipped in the
application images. Model mode remains disabled by default.

The new application deployment fingerprint is
`cd65ff5a00078e7f68db1fb97acf0f533cda1484b9dd6ee30e2eea63e588bbc4`.
Review covers the 36 changed/new deployment files enumerated in the per-record
assessment's hashed inventory: goal schemas/parser/revisions, inference journal,
local HTTP adapter, bounded evidence/proposal loop, paired evaluation-only RNG,
worker timing, API/SDK and narrow browser controls. Dependencies, container
isolation, Dockerfiles and storage drivers are unchanged.

New SQL is parameterized and tenant-scoped. No SQLite database, FTS5 query, database
upload, archive extraction, native shell, ACL, mount, Perl, gzip, infocmp or homed
entrypoint was added to request/model paths. Model fields cannot select SQL,
filesystem paths, arbitrary URLs or execution status. Tools construct allowlisted
synthetic JSON; source code, customer data and catalog prose are excluded. React
continues to escape displayed JSON and summaries. The longer draft-proxy deadline
is bounded to 100 seconds; existing body and local-origin/rate controls remain.

The adapter checks literal loopback, local-only opt-in, pinned model digest, bounded
response size/usage and strict schemas. These are not a sandbox for the model
daemon, a semantic truth checker, or proof that every daemon dependency is unreachable.

## Application Evidence

Seven newly built ARM64 images were scanned with pinned Trivy 0.74.0. Raw counts:
863 total, including 15 CRITICAL, 253 HIGH, 280 MEDIUM, 285 LOW and 30 UNKNOWN.
Fresh runtime proof passed for all seven images: non-root UID, empty capabilities,
no-new-privileges and removed affected entrypoints. Python runtime construction
uses PostgreSQL/remote Qdrant with SQLite connections forbidden; Node/Qdrant
linkage does not include system SQLite. Application roots remain read-only.

The existing component/advisory rules are substantively applicable to this changed
default deployment for the same demonstrated unavailable attack paths. Per-record
refresh additionally requires exact normalized advisory/scanner matches, new image
identity and scan hashes, and this source fingerprint. The executable gate remains
authoritative; changed, missing, expired or unresolved records must fail. No
severity is suppressed or lowered. The October 5, 2026 expiry is unchanged.

The strict comparison initially stopped on changed scanner metadata. Review found
35 records across seven advisories changed only their reference URLs, primarily
AlmaLinux 9-to-10 errata links. Package/version, severity, descriptions, fix status
and attack conditions were unchanged. The exact reference deltas and old/new
finding hashes are retained; new complete hashes are explicitly reviewed rather
than teaching the CI gate to ignore reference changes. The additional Perl
[archive traversal](https://security-tracker.debian.org/tracker/CVE-2026-42496),
[glob execution](https://security-tracker.debian.org/tracker/CVE-2026-48962) and
[archive allocation](https://security-tracker.debian.org/tracker/CVE-2026-9538)
conditions still require removed Perl entrypoints.

Advisory conditions were rechecked against the primary Debian tracker: crafted
[SQLite FTS5 data](https://security-tracker.debian.org/tracker/CVE-2026-11822),
[continuation pages](https://security-tracker.debian.org/tracker/CVE-2026-11824),
[privileged ACL callers](https://security-tracker.debian.org/tracker/CVE-2026-54369),
[infocmp](https://security-tracker.debian.org/tracker/CVE-2025-69720),
[gzip](https://security-tracker.debian.org/tracker/CVE-2026-41992),
[Perl](https://security-tracker.debian.org/tracker/CVE-2026-13221),
[mount operations](https://security-tracker.debian.org/tracker/CVE-2026-76642), and
[systemd-homed](https://security-tracker.debian.org/tracker/CVE-2026-16742).
Installed package metadata remains vulnerable. Lower severities are not universally
triaged away. This review does not transfer to host maintenance shells or model hosting.

Locked Python and pnpm audits returned no known dependency findings. Gitleaks
reported no detected secrets in the scanned nonignored source and all 12 available
commits. That history scan predates feature commits; exact-SHA hosted checks remain
separate. Source/SBOM coverage and immutable hashes are retained with the new archive.

## Optional Model Runtime: Blocked

The explicitly downloaded official Ollama 0.33.3 macOS universal binary was used
for development calls with Qwen3 4B Q4_K_M. It was bound to loopback, cloud disabled,
with no real merchant data or paid inference. Following the new security scan the
daemon was stopped. No held-out model calls were made.

Both the universal binary and its exact ARM64 slice report the same 74 dependency
records: **1 CRITICAL, 42 HIGH, 25 MEDIUM, 2 LOW and 4 UNKNOWN**. These are two scans
of the same installed runtime, not 148 independent findings. The 43 HIGH/CRITICAL
records receive individual conservative **block** decisions, not inherited
not-applicable dispositions. Reachability has not been proven absent. A block is
not a claim that all records are exploitable in this configuration.

Examples include jsonparser v1.1.1, x/crypto v0.43.0 and Go stdlib v1.26.0. Scanner
fixed versions are preserved per record. Official sources include the
[jsonparser fix](https://github.com/buger/jsonparser/commit/a69e7e01cd4ad67bdfd3ac2c080b9212af16f4b0)
and [Go SSH advisory](https://pkg.go.dev/vuln/GO-2026-6303). The official latest stable
release endpoint still reported 0.33.3 on the review date. No waiver or custom
unreviewed upstream rebuild was substituted to finish the benchmark.

Trivy detected 69 Go package records. Its [Go coverage](https://trivy.dev/docs/latest/coverage/language/golang/)
does not prove symbol reachability or complete native inference-library/model-file
coverage. Bundled native libraries, model parsing, macOS and privileged local
processes remain residual limitations. No universal vulnerability-free claim is made.

The runtime is not distributed in this repository or its containers, but it is a
runtime dependency of the optional tested configuration. Therefore that optional
configuration is **not security-qualified**. `LIVE_MODEL_VALIDATION_BLOCKED` applies
to further/held-out validation pending a patched, rescanned operator-approved
runtime or an evidence-backed per-record review. Do not start the retained daemon
merely to obtain favorable results. Ordinary no-key CI does not invoke it.

Ollama is [MIT licensed](https://github.com/ollama/ollama/blob/v0.33.3/LICENSE);
Qwen3-4B uses [Apache-2.0](https://huggingface.co/Qwen/Qwen3-4B/blob/main/LICENSE).
Original notices remain in the downloaded local distribution. Neither binary nor
weights are published, and these licenses do not establish security or model quality.

## Retention

Application raw scans, SBOMs, proofs and assessments are versioned under
`security/reports/2026-09-06-model-planning-arm64/`. Optional-runtime raw scans,
SBOMs, artifact hashes and blocking assessments are retained separately under
`security/model-runtime/`. Prior RC/pre-launch archives are unchanged.
The blocked model assessment is an audit artifact, not an executable permission
grant. A future live run needs refreshed evidence for its actual daemon/build and
configuration, including the unmeasured native-library scope.
