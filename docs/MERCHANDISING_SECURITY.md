# Merchandising Deployment Review

Review date: September 6, 2026. Hard expiration: October 5, 2026.
Private, loopback-only simulator; no real commerce, model-planning approval or
production-safety certification. The blocked Ollama installation remains disabled.

## Fresh Evidence
[Archive manifest](../security/reports/2026-09-06-merchandising-final-arm64/manifest.json)
binds the raw reports, exact-image runtime proofs, seven CycloneDX image inventories,
source/Python SBOMs and per-record assessments. Image inventory records both OCI
image and selected config identities, architecture and every scan/SBOM SHA-256.
The final web image was rescanned after its bounded advance/search timeout fixes;
the other six images are unchanged from the retained initial seven-image scan.
The earlier merchandising archive remains intact. Exact final image legal proof is
retained in `security/merchandising-review/raw/legal-cold-search.json.gz`; each
compressed and original report hash is listed in that directory's parent manifest.

Trivy 0.74.0, pinned scanner image, Linux arm64, fresh database on September 6:
**863 raw findings: 15 CRITICAL, 253 HIGH, 280 MEDIUM, 285 LOW, 30 UNKNOWN.**
The 268 HIGH/CRITICAL scanner records have fresh deployment-specific assessments:
268 not-applicable, zero unresolved applicable, zero untriaged, zero accepted
applicable HIGH/CRITICAL. Original severities remain unchanged. This is not zero
vulnerabilities, patched packages, or a waiver for another deployment.

| Reviewed mechanism | HIGH/CRITICAL records | Concrete restriction |
| --- | ---: | --- |
| mount/namespace helpers | 180 | Affected executables absent; non-root, zero capabilities, no privilege gain |
| Perl runtime | 40 | Interpreter entrypoints removed, no application embedding/invocation |
| infocmp | 18 | Affected executable absent, shared-source package associations retained |
| systemd-homed | 10 | Affected home-management service absent |
| SQLite FTS5 | 10 | Vulnerable library present; no deployed FTS5 database/query path demonstrated |
| GNU gzip | 5 | Affected executable removed; not Python/Node zlib |
| privileged ACL caller | 5 | No privileged runtime caller or application ACL operation |

All raw advisory fingerprints were compared, including changed descriptions,
references and fixed versions; these 268 matched prior advisory content, but
**application reachability was reviewed anew**. The ordinary and learned-overlay
application source, dependency locks, Docker configuration and encoder notices are
bound by the new deployment hash. Host-generated `.egg-info` metadata is excluded;
real runtime files, dependency changes and deployment changes invalidate review.

Fresh exact-image probes verified all seven non-root UIDs, zero effective/permitted/
bounding capabilities, no-new-privileges, removed entrypoints and no setuid/setgid
runtime files. Application root filesystems are read-only and host ports loopback.
Python storage construction uses PostgreSQL and remote Qdrant with Python SQLite
connections forbidden; Node/Qdrant dynamic linkage was checked separately.

The changed native encoder was actually executed without networking, with read-only
model data and SQLite constructors forbidden. ONNX Runtime/tokenizers dynamic
libraries showed no system SQLite linkage. The malicious SQLite FTS5 database/MATCH
path described by the [Debian advisory](https://security-tracker.debian.org/tracker/CVE-2026-11822)
is therefore assessed unreachable in this reviewed configuration, not patched.
Pinned checksummed ONNX/tokenizer bytes, not user-uploaded model/database files,
reach native parsing. No custom operator library, arbitrary script, model download,
privileged maintenance endpoint or SQL upload was added.

## Encoder And Source Review
Optional dependencies are locked and included in source auditing. pip-audit 2.10.0
and the Node audit returned no known dependency records in this snapshot; image
findings above remain. No additional HIGH/CRITICAL package finding was discovered
in the optional encoder installation. This does not exhaust native supply-chain
or model-file vulnerabilities.

The exact final API-image CPU probe returned 384 dimensions: cold construction
7.891 seconds; five queries 0.799, 0.156, 0.104, 0.106, 0.134 seconds; peak RSS
407,424 KiB. Network was disabled, UID 10001, read-only filesystem, telemetry opt-out
set before native import. These loaded-VM observations are not production sizing.
[Raw probe](../security/merchandising-review/learned-runtime-final.json.gz) and
[native linkage](../security/merchandising-review/native-links.json.gz) are retained.

An earlier probe exposed ONNX Runtime's telemetry default. Its diagnostic remains;
that first probe's network behavior was not traced and is not retroactively called
offline. The deployment now opts out before native initialization and the final
probe denies networking outright.

Gitleaks 8.30.1 initially reported three public tokenizer checksums and then six
occurrences of two synthetic idempotency keys in the expanded trajectory. Raw
redacted records remain under `security/merchandising-review/raw/`. Contract tests
verify the real tokenizer checksum and reconstruct both action keys from typed
facts. Exceptions require exact values AND exact file paths. Six actual scanner
controls prove changed values and wrong paths still fail. The subsequent full
source and complete 14-commit history scans passed; later commits require their
own history scan, not an inferred extension of this snapshot.
The implementation commit `64709cb825da6df128a98af7b69554e548ef92be` then passed a
fresh source audit and all 15 locally available history commits (16.36 MB scanned).
Its original reports/logs and source/Python SBOMs are retained under
`security/merchandising-review/raw/committed-source/`, with hashes in the retained
raw manifest. A later documentation/evidence commit is not retroactively included
in that 15-commit snapshot.

## License And Limits
Apache-2.0 first-party license and DCO remain unchanged. Pinned model-card license
declaration, upstream exact-commit tokenizers/flatbuffers licenses, installed
package notices and original ONNX third-party notices are retained in
`security/third-party/learned-search`. Built-image legal files were checked by hash.
The model revision has no separate LICENSE file; its model-card declaration is
not a separate legal certification. The runtime never downloads model data.

Remaining risks include incomplete enumeration of statically linked native
dependencies, unpatched but assessed-unreachable system libraries, lower-severity
raw findings, synthetic-only testing, host/maintenance exposure outside this
configuration and dependence on correct isolation. No applicable HIGH/CRITICAL
risk was accepted to enable this work. Optional blocked Ollama retains its separate
74 raw records and 43 blocking HIGH/CRITICAL assessments, unchanged.

The fail-closed gate rejects new/untriaged HIGH/CRITICAL records, changed advisory
content, missing/expired assessments and changed application/deployment hashes.
This review expires October 5, 2026 regardless of private/public status. Later
releases or public release after that date require refreshed assessments.
