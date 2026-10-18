# Security Verification Record

Current self-hosted alpha qualification is incomplete. The historical simulator
evidence below applies only to its exact artifacts, not the current application.
This record is not authorization to publish or expose either runtime. Original
scanner severities remain visible; there is no zero-vulnerability claim.

## Current Alpha Review: October 17, 2026

The latest acquisition rehearsal built **eight service entries and eight distinct
images** from frozen source-tree SHA-256
`0cc2ecf3f8db315cb0d1e9d837f0f312589aac81b7bc9f055a970b31da28f2dc`.
Its scans retain **985 raw records: 0 CRITICAL, 261 HIGH, 352 MEDIUM, 366 LOW and
6 UNKNOWN**. These are per-service occurrences, not unique CVEs. All **261 HIGH
image records remain pending exact-artifact applicability review**, and one HIGH
source advisory remains unapproved. No prior disposition is automatically inherited.

The raw reports, eight SBOMs, source snapshot and identity records are retained
privately. Image acquisition and a separately verified privacy-policy follow-up
completed locally; this is not hosted qualification or release approval. The
original failed privacy check is also retained. Current working source includes
later release-tooling fixes and therefore is not qualified by this earlier frozen
rehearsal. The protected current-approval record remains **pending**.

A separate local, AI-assisted source-review bundle now passes the actual typed
source verifier for the external patched `braces` build/development path.
Independent review replayed that check and eight rejection controls. The raw
HIGH, scanner `dev:false` and scanner fix fields are preserved. This is an
**unadopted consistency rehearsal**, not runtime clearance or human approval; its
review expires **October 18, 2026 at 00:00 UTC**. The embedded Next.js copy is
outside that source determination.

New offline observations bind the embedded Node files and native components to
the eight rebuilt images. Independent review verified the limited byte/link
continuity without transferring earlier dispositions. Application-file captures
use never-started containers with no network or store mounts. Their generated
code differences and opaque files require separate review; metadata equality is
not a normal-entrypoint test or whole-program reachability proof. The 261 HIGH
image records remain pending, with original raw fingerprints and layer changes
retained.

The separate application comparison leaves six compiled-body occurrences
unresolved. Matching source is not a substitute for reviewing those generated
bodies. It also identifies generated frontend signing/encryption material in
private test-build evidence. Only sanitized field hashes belong in shared review
summaries; these test images must not be published or promoted. The final
candidate requires a fresh build with fresh keys and its own qualification.

### Previous Exact-Artifact Component Review

The earlier local scan of eight service entries and seven distinct images,
including the repaired Qdrant shutdown image,
retains **985 raw records: 0 CRITICAL, 261 HIGH, 352 MEDIUM, 366 LOW and 6 UNKNOWN**.
That ACL-hardened candidate has source-tree SHA-256
`833e2019c476b58ca90f48f1132848966d67f431005950f0071c56071064db6b`.
Its local ARM64 build, selected-path/privilege checks and all eight scan/SBOM
collections completed. A new exact-image primary assessment records **261 HIGH
records as not applicable within their reviewed boundaries, zero unresolved
applicable HIGH/CRITICAL and zero untriaged HIGH/CRITICAL**. Independent review
verified the reporting corrections. These are 93 affected-component absence,
162 libmount call-boundary and six Perl engine/module/application determinations.
Package metadata was retained; pruning affected
files does not suppress version-based findings. Exact-image startup, catalog,
worker and graceful-restart checks passed. A bounded merged-filesystem ELF
inventory and independent metadata-delta review completed. Offline recovery passed
after resolving test-host disk exhaustion. Whole-release qualification remains
incomplete: these decisions apply only to the frozen source and exact images above,
not the current working tree or future builds.

A record-level reconciliation rechecked 500 retained evidence bindings and all 261
raw identities without changing scanner severities. Independent review caught two
reporting defects: missing upstream-fix details in six ACL records and inherited
application-evidence wording in 27 Qdrant rationales. Separately versioned records
correct both; the original drafts and review findings are retained. The corrected
partial assessment remains retained with its original 120/141 dispositions. The
subsequent primary assessment explicitly adopts the current web, application and
Perl supplements after rechecking 2,305 evidence/source/archive files, including
all 1,659 frozen source files and their modes and membership. It passed 25 primary
adoption controls and 51 draft reconciliation controls. Its separate corrected
version passes 31 controls and retains the earlier record unchanged: Qdrant's Perl
rationale uses only the native-service boundary, and the CVE-2026-78409 upstream
version-scope discrepancy remains explicit. A changed working progress
document was detected and withdrawn from active proof as historical informational
context; its old binding and failed check are retained. The frozen source document
remains hash-verified. No changed runtime or raw finding was ignored.

The one changed current Python bytecode body was reproduced exactly using the
matched trusted compiler and unchanged source. The old body was not reproduced;
no old/current semantic-equivalence claim is made. The original cleanup-diagnostic
failure and independent resolution remain retained. Complete semantic analysis of
the 614 opaque records in 118 unchanged outer files is not claimed. The new primary
assessment expires **October 24, 2026**, or earlier on any bound-input change.
This does not make the historical CI gate pass or qualify the current working tree.

### Current Gate Hardening

The container scan gate now validates unique service coverage, per-image completion,
scan metadata, actual result structure, recomputed severity/fix counts and SBOM
identity before considering any findings. Duplicate JSON fields, nonfinite numbers
(including exponent overflow), missing results and malformed SBOM components fail
closed. All eight retained scan/SBOM pairs validate; 56 focused tests include 11
CLI-entrypoint regressions. Independent review verified these corrections. This
closes the reproduced malformed-input defect, not the remaining evidence-contract
or CI-approval requirements. New gate code is newer than the frozen images above.

The separate `scripts/check_release_assessments.py` verifier defines a current,
typed image-assessment contract. A new manual, read-only
[current-evidence workflow](CURRENT_RELEASE_SECURITY.md) invokes both image and
source verifiers from trusted default-branch policy. Its approval record remains
**pending**, and no real hosted run or approved bundle has passed it. It does not
replace or bypass the existing failing historical gates.
It reads an immutable evidence bundle and checks a review-manifest digest and
source-tree digest supplied by a trusted caller. Do not derive the expected review
digest from an unreviewed pull request and call that approval. For a separately
adopted, privacy-reviewed bundle, the read-only command is:

```sh
.venv/bin/python scripts/check_release_assessments.py \
  --bundle-root release-evidence \
  --review-manifest review.json \
  --expected-review-sha256 "$APPROVED_REVIEW_SHA256" \
  --expected-source-sha256 "$BUILT_SOURCE_SHA256"
```

The contract checks frozen source files/modes/membership, exact image and scanner
identities, raw scans and SBOMs, one assessment per HIGH/CRITICAL record, dates,
scope and evidence hashes/pointers. Proofs include concrete bound observations,
not just a completion assertion. Selected empty or failed JSON observations are
rejected; legitimate empty results require an explicit complete, matching-scope
envelope identifying examined inputs. All 320 focused verifier tests pass, and
independent re-review closed the reproduced observation-completeness defect.
This validates the evidence contract, not arbitrary prose or rationale truth.
Scanner-reported distribution fixes and upstream
fix availability are separate fields. Applicable runtime HIGH/CRITICAL findings
have no acceptance or mitigation override. A successful result verifies consistency,
not the truth of the reviewer judgment or permission to publish. Historical/private
ledgers are not automatically converted or accepted. Protected CI inputs, exact
artifact promotion, source-audit dispositions and review of the assembled current
candidate remain necessary before it can replace the historical gate.

Source scan collection now runs dependency export and audits inside its retained
source snapshot, with source membership/hash/mode checks before and after scans.
Raw tool exits remain recorded. Complete findings reports are distinguished from
tool/schema/coverage failures; neither becomes a clean result by ignoring the exit
code. Independent review confirmed compatibility with the retained actual report
formats, then reproduced two completeness defects. The collector now requires an
empty JSON findings array as well as a clean Gitleaks log, and rechecks every saved
report, secret-scan log and tool-version binding before reporting success. These
checks pass 165 focused tests; independent re-review closed both reproduced
defects. Hosted artifact uploads and provenance also retain
the tool-version stdout/stderr files, including empty stderr. This is validation
of collection behavior, not a new source scan or a newly approved candidate.
The existing source qualification still fails when advisories are present.
The separate current source-assessment verifier and protected adoption workflow
are implemented but not operationally qualified. They require current complete
collections, exact finding assessments and a human-approved artifact record;
synthetic contract tests do not qualify the retained historical collections.

Independent review of the new verification path reproduced and closed five scoped
defects: missing reconciliation of inventory child hashes with original build
provenance, rejection of documented ref-qualified workflow paths, archive root
ordering for valid filenames, rejection of literal Next.js bracket paths, and
missed unmanifested empty directories. Regression tests retain the original failure
cases. Five combined synthetic tests exercise the real transport and both semantic
verifiers; only GitHub metadata is mocked. They preserve raw findings and reject
changed or missing assessments even with refreshed transport hashes. These are
reviewed engineering checks, not a hosted run, a fresh scan or publication approval.

A separate October 17 primary review records **255 not-applicable and 6 blocked**
for the older ARM64 snapshot identified below. Those dispositions are not copied
to the new candidate. Both sets of raw findings, assessments and build receipts
remain available privately. Neither is a passing current release gate.
The separate source audit reports no Python advisories and one Node HIGH advisory
in `braces` 3.0.3. A new primary assessment records scoped local remediation for
the development/build dependency and a separate not-applicable determination for
the known embedded Next.js runtime copy. The raw HIGH record remains unchanged.
These decisions bind the frozen source and exact ARM64 image bytes above; they
do not qualify the current working tree, other images or the whole release.

The current working tree adds a [pinned local braces patch](../infra/patches/README.md)
for bounded nesting/AST traversal. The version-based source scanner still reports
the HIGH advisory; its raw result is retained, not suppressed. Fresh-install and
Node 22 regression checks are part of patch verification, not a completed source
or container qualification. The embedded Next.js copy is unchanged. Independent
review traced its ordinary NFT exports and internal consumers: the sole micromatch
consumer calls `isMatch`, which delegates to Picomatch rather than the affected
braces walkers. Exact bundle/image hashes and source-scope analysis support that
limited determination; zero calls in serving probes alone would not. The local
patch intentionally rejects excessive depth and malformed ASTs; it is not a
general guarantee against glob expansion or regular-expression resource exhaustion.
The new assessment was reviewed October 17 and expires October 24, 2026, or earlier
if any bound input changes. It grants no waiver and does not extend older records.

Exact-image non-root/capability/component checks passed for all eight service images
using an isolated replacement shell. They verify selected filesystem locations and
the supplied isolation flags, not normal-entrypoint process state, inherited
descriptors, every alternate executable or native caller. Independent review
confirmed scan/SBOM/hash consistency but identified those coverage and provenance
gaps. Those initial shell checks alone were insufficient for applicability
decisions. The bounded assessments below use additional retained evidence;
runtime and release qualification remain incomplete.
Raw scans, SBOMs, hashes and a machine-readable blocking backlog
are retained in the private release workspace. These local artifacts are not a
hosted CI result or a frozen public candidate. A later sanitized release manifest
must identify the exact artifacts it qualifies.

### Partial Component Assessment

The reviewed source snapshot is
`95801c4057c87dc5f0add6c4ba973f4f95d9f4e7e2e9c051074a7ece15d1c037`.
Its first component reconciliation verified 169 retained evidence files and 33
raw finding identities. A separate nsenter reconciliation checked 199 retained
input hashes and 54 additional finding identities; these file sets overlap and
must not be summed as unique files. Each new assessment identifies
the scanner, image, installed package, advisory, runtime scope, reachability,
fix availability, rationale and evidence. These new assessments expire October 24,
2026, or become inapplicable sooner when their bound inputs change. They do not
extend the October 5 historical assessments.

- **21 infocmp records:** the affected command is absent from the merged runnable
  filesystem. The flaw is in its private `analyze_string` implementation, not the
  retained ncurses libraries. [Debian advisory](https://security-tracker.debian.org/tracker/CVE-2025-69720)
  and [upstream build mapping](https://raw.githubusercontent.com/ThomasDickey/ncurses-snapshots/v6_5_20250216/progs/Makefile.in).
- **12 systemd-homed records:** the affected daemon and helper are absent. Retained
  libsystemd/libudev packages do not contain that daemon's home-record handler.
  [Upstream advisory](https://github.com/systemd/systemd/security/advisories/GHSA-jm29-p7hh-vjhv)
  and [source ownership](https://raw.githubusercontent.com/systemd/systemd/v257.13/src/home/meson.build).
- **54 nsenter records:** the affected util-linux executable is absent from the
  five relevant Debian images (six service entries). The cgroup descriptor state
  belongs to that program, not retained libmount. This does not claim that every
  image lacks an `nsenter` command: the PostgreSQL and Redis images include a
  separate BusyBox implementation and have no records in this subset.
  [Upstream advisory](https://github.com/util-linux/util-linux/security/advisories/GHSA-55fx-f4gg-cfhj)
  and [program build mapping](https://raw.githubusercontent.com/util-linux/util-linux/v2.41.5/sys-utils/Makemodule.am).
- **162 libmount records:** the library remains shipped and is not claimed fixed.
  Nine retained native consumers import 103 reviewed data/query APIs, outside the
  affected mount-context and hook paths. The generated-application supplement
  found no additional application caller into those paths. This is a bounded
  call-path determination for the frozen application, not library absence.
  [Helper-failure advisory](https://github.com/util-linux/util-linux/security/advisories/GHSA-m25x-3hj9-m26f),
  [subdirectory advisory](https://github.com/util-linux/util-linux/security/advisories/GHSA-8f2p-47x3-43mv),
  and [bind-source advisory](https://github.com/util-linux/util-linux/security/advisories/GHSA-rh77-686x-2f2m).
- **6 Perl Archive::Tar records:** combined engine/module, native and generated-
  application evidence does not identify the affected module's archive-read path
  in the shipped application. Retained Perl package records or core/XS libraries
  alone do not establish that chain. This is not a claim that every Perl component
  was removed or patched. [Debian advisory and fix tracking](https://security-tracker.debian.org/tracker/CVE-2026-9538).

The new reconciliation binds 168 decisions to their raw findings and exact images,
with 110 retained evidence-file hashes, 45 native-caller bindings, 377 first-party
source-member bindings and 249 application native-member bindings. Independent
AI review found no material binding or scope defect. The API payload enumeration
completed, but its general semantic search remains explicitly incomplete: 614
opaque records in 118 outer files were classified as test-fixture or numerical
data, not executed or deserialized. These observations support the specific
loader/caller questions; they are not complete analysis of every payload or proof
against arbitrary added code. Earlier ledgers and failed attempts are retained.

These are component-absence or reviewed call-path determinations, not patched-
package claims or blanket source-package exceptions. Removed executable bytes may remain in lower image
layers. The assessment covers the merged runtime, not host administration,
reinstalled programs, injected mounts or arbitrary repackaging. It does not rely
on non-root execution alone. In this older ledger, the six ACL image records and
separate Node HIGH finding remained blocked; the new Node assessment above does
not edit that historical record. No risk
acceptance or waiver has been granted. The assessment and original scans are
retained privately; their publication still requires privacy review and exact
candidate qualification. Automated independent review is not human certification.

### ACL Remediation Candidate

The current source removes seven unused final-runtime ACL consumers and their
shared library after package and account setup. It retains scanner-visible package
metadata and licenses. [Pruning scope and acceptance checks](../infra/docker/README.md).
The selected-path image probe now also rejects retained or dangling consumer and
SONAME paths. This probe is not a complete native inventory. Synthetic filesystem
tests do not qualify new images. The first thin API prototype preserved its launch
configuration and passed pruning; the subsequent complete source build passed the
selected-path checks for all eight service entries. Fresh scans and SBOMs are now
retained. The subsequent inventory contains 4,149 ELF records and finds no scoped
ACL filename, dependency, SONAME, undefined import or link matches. Independent
review verified 246 retained metadata hashes and the exact eight removals in each
of five images, with no added or changed surviving ELF payload hashes. This compares
retained records, not a second fresh payload extraction; two Python object records
lack dynamic-symbol coverage. It does not prove absence of statically embedded
code, arbitrary dynamic loading or all possible callers.

The exact-image synthetic runtime passed 15 acceptance checks twice and a Qdrant
restart. Four isolated Next.js serving/control cases also completed: serving did
not load the traced NFT module, while controls exercised the tracer and matcher
without calling the mapped braces entry functions. These are bounded workloads,
not universal reachability proof. Cold backup completed and all four restored
volumes matched file bytes, ownership and modes before startup. Recovery startup
then failed because the test Docker disk was full. After the owner-approved disk
expansion, the same offline restore resumed through the unchanged helper and passed
all 15 verification checks. Exact container identities, ownership guards, disabled
model credentials and internal-only networking were preserved; the original failed
attempt remains retained. A further 23 checks passed on that same isolated copy:
nine Qdrant snapshot checks preserved exact vectors, payloads and IDs in a separate
test collection, and fourteen owner-recovery checks verified session revocation,
code rotation and rejection of sequential code replays. The synthetic owner's
original password was restored; the newly rotated code remains private. The
existing catalog collection was not replaced. All seven services remained healthy
without a restart or identity change. An evidence-copy failure and its subsequent
read-only retrieval are both retained; mutations were not repeated to recover logs.
Concurrent redemption, malicious snapshots, cross-version recovery and other
platforms were not covered. Current image assessments remain required. None of the
older findings was cleared by changing its original evidence.

### Retained Image Identity

New image scans retain the byte-exact Docker save manifest and selected image
configuration before deleting the large temporary layer archive. Each inventory
entry records their hashes plus an allowlisted inspection record containing only
the image ID, platform and filesystem layer identities. Selection must be unique;
malformed, duplicate, oversized or ambiguous metadata fails the scan. The raw scan
must identify the selected configuration. Existing evidence is never overwritten.

These files are private evidence: a built image configuration can include build-time
defaults. The scanner does not retain a running container's environment, arguments
or credentials. Do not publish the raw files without a separate privacy audit.
If metadata validation or compact-evidence persistence fails, the private temporary
archive is retained for diagnosis rather than deleted. Such failures can consume
significant disk space. Archive-parser errors do not print the rejected values.
The match establishes the selected filesystem/platform relationship, not a signed
provenance claim, complete OCI-index verification or vulnerability disposition.
Historical scans without these inputs are preserved as historical evidence.

### Workload Observations

`scripts/observe_runtime_workload.py` adds a separate, read-only observation of
already-running containers in an explicitly selected disposable Compose project:

```sh
.venv/bin/python scripts/observe_runtime_workload.py \
  --project release-qa \
  --images .opencommerce/image-scans/inventory.json \
  --output .opencommerce/workload-observation
```

Use a new output directory for every attempt and the actual project's complete
exact-image scan inventory. The observer neither starts nor restarts services.
It checks project/service ownership, image identity, expected non-root observer
user, configured isolation and unchanged container startup identity around collection.
The probe also rejects UID 0 before reading workload metadata. Process status, mapped
paths, mount metadata and descriptor targets/flags are retained privately; it
does not read process arguments, environment, descriptor contents or store files.
Raw collection is container-wide, excluding the probe shell itself; summarized
workload records exclude unrelated exec-process trees, whose raw metadata is still
retained. Output is byte-bounded while reading, before files are written. Truncation
or timeout retains a bounded prefix and fails observation. Raw bytes are saved and
hashed before strict decoding; invalid encodings fail, and collector diagnostics
are kept separate from the observed stderr. Every collected process must pass
framing and final-identity validation, including processes excluded from the summary.
Descriptor metadata and
process identities are rechecked; a detected reuse/close or generation mismatch
also fails rather than silently omitting the changed record.
The source scripts, inventory and timestamped raw output are hash-bound. These
are local records, not signed or independently anchored attestations.

Seven running services in the isolated recovery fixture were observed with
non-root UIDs, empty capability sets and no-new-privileges. The migration job had
already exited and remains unobserved: the command correctly returns nonzero
instead of borrowing API evidence. Earlier descriptor-race and zombie-process
attempts are preserved. Stable zombie descendants are recorded as inactive,
never as live executable or descriptor evidence. Timeout/health-check helpers can
be reparented into the process tree; membership alone does not prove application
ownership.

A separate observation of the rebuilt ACL candidate again captured seven running
services and honestly reported the already-exited migration as unobserved. A
supplement then observed that exact migration image under its unchanged normal
entrypoint while it waited on a bounded synthetic database lock. The lock released
and migration exited zero. The supplement does not turn the earlier incomplete
receipt into a pass or establish complete startup coverage.

These are bounded process snapshots, not complete startup history, a native-call-
graph proof or guaranteed atomic views of every descriptor. Current per-record
review remains required. No HIGH finding was cleared by these probes alone.

`scripts/probe-image-components.sh` supplies a separate, bounded filesystem
inventory for an isolated copy of an exact image. It records named component
families, package-listed paths, symlink edges and set-ID metadata without executing
the listed packages or reading their payloads. The caller must retain its source,
image identity, isolation settings, raw output, timestamps and hashes. Require both
a zero exit status and a complete trailer; unreadable paths or diagnostics are
incomplete evidence, not proof of absence. Scanner-only access to protected image
directories must be disclosed separately from the ordinary application's privileges.
No host/store mounts, model keys or network access are needed for this inventory.
It does not establish the absence of renamed, statically linked or embedded code.
The corrected local inventory completed for all eight service entries (seven
distinct images), with raw metadata and cleanup receipts retained. PostgreSQL and
Redis image-declared data volumes were newly created scanner volumes, not
store volumes. Their mounts were writable despite the read-only image root, and
other-filesystem descent is outside the probe's declared scope. They were removed
with each owned scanner copy. This inventory does not fill the transient migration
workload or native-call-graph gaps.

The October 5 historical expiration has not been extended. Existing stale-evidence
gates still fail. Current source, deployment and image changes require fresh review,
not a date-only renewal of the simulator assessments.

## Historical Raw Scans

### September 6, 2026 Hosted Addendum

The owner-approved [private hosted run 34001296613](https://github.com/aapplepku/opencommerce/actions/runs/34001296613)
passed all seven jobs at `c2617412d0d926946c0b532c9ea7250cc89eb21d`, now frozen
under annotated `v0.1.0-rc1`. The private normalization verification preserved all
128 retained qualification files and their hashes. No GitHub Release was published.
The raw 863 records, 268 reviewed HIGH/CRITICAL records and October 5 expiration
below remain unchanged. Zero unresolved applicable HIGH/CRITICAL is scoped to
that exact reviewed runtime, not zero vulnerabilities or approval of later changes.

The remaining sections preserve the earlier local checkpoints and their then-current
hosted status. Later private preparation has its own validation and must not be
represented as covered by the frozen RC. See [RC notes](releases/v0.1.0-rc1.md).

### Historical Local Checkpoints

The [build-tool correction checkpoint](../security/reports/2026-09-05-build-tools-arm64/manifest.json)
supersedes the image inputs below with fresh no-cache builds and privilege proofs.
Raw image counts remain unchanged. All 268 records were re-reviewed after build
input changes; 45 also gained advisory metadata. The gate rejected them before
review and passes afterward without weakening any fingerprint or expiry rule.
Setuptools/wheel build requirements were missing from the older dependency audit;
that HIGH coverage gap is corrected with fixed pins and enforced audited coverage.
[Build verification](BUILD_DEPENDENCY_VERIFICATION.md) preserves all original raw
records, eight assessments, patched audit evidence and scope limitations.
These remain local results: hosted attempt 33996463613 failed scanner permissions,
and the corrected scanner identity still requires exact-SHA hosted validation.
Subsequent pre-staging log review also identified a zero-commit false-success
from Gitleaks after the UID change. Those original outputs are incomplete. The
scanner now requires retained error-free/nonzero coverage and the independently
counted history total, with container-only trust for its exact read-only mirror.

The [private RC preparation checkpoint](../security/reports/2026-09-05-private-rc-preparation-arm64/manifest.json)
contains 28 hash-linked files, including all new image scans/SBOMs, fresh runtime
proofs, passing source/history/dependency scans and the expanded per-record reviews.
It includes the corrected web image; the raw counts below remain unchanged.
The new gate reports 268 not-applicable and zero unresolved HIGH/CRITICAL records
within its reviewed scope. This is local evidence, not a hosted run or RC commit.
Later reporting paragraphs are not retroactively included in the scanned source.

The [owner-metadata checkpoint](../security/reports/2026-09-05-owner-legal-arm64/manifest.json)
contains exact-image ARM64 scans. It predates the private RC preparation changes
and must not be treated as a scan of a later hosted image.

| Service    | Critical | High | Medium | Low | Unknown |
| ---------- | -------: | ---: | -----: | --: | ------: |
| API        |        3 |   51 |     56 |  57 |       6 |
| Migration  |        3 |   51 |     56 |  57 |       6 |
| Worker     |        3 |   51 |     56 |  57 |       6 |
| Web        |        3 |   50 |     56 |  56 |       6 |
| Qdrant     |        3 |   50 |     56 |  58 |       6 |
| PostgreSQL |        0 |    0 |      0 |   0 |       0 |
| Redis      |        0 |    0 |      0 |   0 |       0 |
| Total      |       15 |  253 |    280 | 285 |      30 |

These are 863 raw package/advisory records, not 863 unique CVEs. All 268
HIGH/CRITICAL records were reviewed as not applicable to the constrained local
deployment. None of those 268 had a distribution fixed version in the raw scan.
Two lower-severity Qdrant Rust rand records have fixes available. They remain
residual findings; no custom Qdrant rebuild or patched-library claim is made.

Python pip-audit 2.10.0 and pnpm 10.17.1 audits reported no dependency advisories
in that snapshot. Gitleaks 8.30.1 source and six-commit history scans passed.
Trivy 0.74.0 produced the seven image SBOMs and the source inventory. Original
reports, versions, image IDs and compressed/uncompressed hashes are retained in
six checkpoint manifests under `security/reports/`. Historical checkpoints
describe their own inputs, not later code.

The original Gitleaks checksum false positive and negative controls are in
[legal evidence](../security/legal-verification/2026-09-05-arm64/manifest.json).
The exception permits one exact checksum AND manifest path, not a directory,
generic rule or credential. Changed values and alternate paths remain detected.

## Per-record applicability

`security/reviewed-image-findings.json` expands all 268 historical reviewed records
with scanner/version/image, original scan date, explicit automated-review owner,
artifact, architecture, package/version/advisory,
runtime membership, scope, reachability, exposure, fixed-version availability,
decision, concrete evidence, rationale and review/expiration dates.
`security/image-assessments.json` retains the supporting component rules.

All seven historical Compose images, including the migration image, are conservatively
classified as shipped runtime. Build/dev/test dependency audits have no exception
path: any advisory or scanner error blocks until corrected/reviewed. New findings
are not automatically approved by matching a rule name.

The gate requires:

- Every HIGH/CRITICAL raw record has exactly one complete, unexpired assessment.
- Full scanner finding content, version and context match the reviewed hash.
  Image layers and Trivy's artifact-derived fingerprint are provenance, not
  advisory text: the gate recomputes the scanner fingerprint for the exact
  current artifact and verifies image/config identity independently. These fields
  remain in raw reports. All advisory fields, including newly added fields, bind review.
  The formula is documented in [Trivy's upstream fingerprint design](https://github.com/aquasecurity/trivy/issues/9793).
- OS, architecture, scanner image, fixed-version metadata and package identity match.
- Application/dependency/isolation input hashes match the reviewed deployment.
- Supporting rule hash, fresh same-image privilege/component proofs, raw scan
  hashes and SBOM hashes all match.
- Applicable unresolved shipped-runtime findings block even if marked accept or
  mitigate. Only a proven not-applicable record may pass the current gate.

The review expires October 5, 2026. New advisories, altered descriptions or fix
availability, changed deployment inputs, missing proof and expired records require
review. Negative tests cover these cases. Expiry and changed records are failures,
not warnings. Hosted artifacts retain the evaluated per-record dispositions,
current raw scan dates and the original reports even when qualification fails.
Automated reviews are identified as such, not represented as independent human
certification.

## Evidence and limitations

| Component               | Deployment-specific evidence                                                                                                                                                   |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Perl, GNU gzip, infocmp | Affected command-line executables removed and checked inside the image; package metadata retained                                                                              |
| util-linux              | Affected mount/namespace tools removed; required privileged operations unavailable                                                                                             |
| systemd                 | homed service absent; libraries share source-package association                                                                                                               |
| libacl                  | No privileged pathname ACL caller, root UID, capabilities or privilege-gain path in this deployment                                                                            |
| SQLite FTS5             | Library remains installed; Python constructs PostgreSQL/remote Qdrant with SQLite forbidden; Node/Qdrant do not link system SQLite; no application SQLite/database-upload path |

Each record links the relevant primary advisory and proof. These conclusions
do not cover host/admin maintenance shells, arbitrary scripts, plugins, a public
deployment, changed images or new application paths. Native/embedded dependency
detection is incomplete; legal notice inventory does not prove vulnerability
coverage. Low/medium/unknown records remain raw residual risk. Undisclosed
vulnerabilities cannot be excluded.

## Reproduction and retention

After a clean build of the intended Compose project:

```bash
.venv/bin/python scripts/verify-runtime-images.py
.venv/bin/python scripts/scan-source.py
.venv/bin/python scripts/scan-images.py
.venv/bin/python scripts/check-image-findings.py
```

Scanners query public advisory services and download databases; the source scan
runs locally, without uploading source. Image scans use exported images, not a
mounted Docker socket. Use a new output directory per run to retain failures.
Source/history coverage requires a complete clone. Original scan outputs remain
unchanged; historical dependency-export command comments containing personal
paths are separately sanitized, with original hashes and private originals retained.
They are scan inputs, not altered scanner findings.

Hosted artifacts include raw source/image JSON, source/Python/seven image SBOMs,
runtime/legal proofs, assessments, logs, benchmark outputs and a SHA-256 provenance
manifest tied to the exact checkout. Download them before the 30-day hosted
retention expires. A provenance file is not a successful-check attestation;
verify the final workflow conclusion and every required job for that same SHA.

## Hosted boundary

The private RC workflow requires a private repository, exact RC branch and DCO
before qualification. It uses native `ubuntu-24.04-arm`, supported for private
repositories by [GitHub](https://github.blog/changelog/2026-01-29-arm64-standard-runners-are-now-available-in-private-repositories/).
ARM64 matches the reviewed image/notice platform; AMD64 requires a separate review.
Read-only tokens, pinned actions/scanners and disabled persisted checkout
credentials remain. No publication operation exists.

At this earlier local checkpoint, hosted workflows had not run yet; the September 6
addendum above records the later frozen-RC run. Full qualification allows 360 minutes; normal
checks 180. A timeout is a failure, not permission to omit cases. The committed
full reference is verified into a separate primary output, followed by independent
reproduction. Local results do not substitute for hosted evidence.
