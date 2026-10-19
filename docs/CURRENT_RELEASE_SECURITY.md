# Current Release Security Verification

## Status

The current alpha is **not qualified for publication**. The new manual workflow is
an additional read-only verifier, not a replacement for existing checks. Its
committed approval record is deliberately `pending`. No approved current bundle,
protected-environment verification run, or publication authorization is implied by
the implementation or its synthetic tests. Historical failed gates remain visible.

This flow checks whether reviewed evidence is complete, current and internally
consistent. It does not prove arbitrary rationale text true, grant a vulnerability
waiver, or authorize a tag, repository visibility change, package or image release.
Keep [raw counts and bounded applicability conclusions](SECURITY_VERIFICATION.md)
separate; a passing consistency check is not a claim of zero vulnerabilities.

## Dependency Remediation In Progress

On October 17, the working-tree lock was updated from Mako 1.4.1 to 1.4.2,
the upstream fix for the Windows template-path traversal advisory
[GHSA-5639-2j2p-m4mx / CVE-2026-102991](https://github.com/sqlalchemy/mako/security/advisories/GHSA-5639-2j2p-m4mx).
No other locked package changed in this update. Mako is an Alembic dependency;
the application does not gain a new templating interface. The contract regression
uses synthetic Windows path semantics and trusted text, not customer templates,
and checks that normal Alembic revision generation still works.

This is a dependency remediation, not a claim that the existing Linux images
were exploitable or that other HIGH findings are resolved. Earlier image scans,
SBOMs and reviews retain their original Mako version and source identity. Rebuild
and rescan the final candidate before claiming it contains the patched artifact.

## Trust Boundary

The workflow `current-release-security.yml` runs manually from the protected
default branch. That checkout supplies the verifier and locked dependencies. The
candidate source and evidence are downloaded into temporary directories as data;
the workflow never executes code from either artifact. Repository permissions are
read-only, and there are no pull-request or `workflow_run` triggers.

Three commits may differ: the candidate build commit, the reviewed evidence
producer commit, and the default-branch verification-policy commit. Results record
the candidate and policy commits separately. Do not tag the policy commit merely
because its verification workflow passed. A source change needs new affected
checks and evidence, not reuse of a previous candidate's review.

The workflow requires the `alpha-security-review` environment, protected-branch
deployment restrictions, and at least one explicitly approved human reviewer.
After the environment review, the verifier reads GitHub's actual review history
and requires the approving comment to be exactly:

```text
security-review:<SHA-256 of the approved current-release-approval.json bytes>
```

This binds that review to the adopted pins. Clicking an environment bypass without
the matching review is insufficient. Reruns are rejected; dispatch a fresh run and
review it again. A single owner can review; this is not two-person approval. The
branch's protected flag is checked, not every repository rule. Full branch
protections remain a separate release requirement. If the account cannot support
the required environment/review APIs, stop rather than remove this requirement.

See GitHub's [environment API](https://docs.github.com/en/rest/deployments/environments),
[run attempts and approval history](https://docs.github.com/en/rest/actions/workflow-runs),
and [immutable artifact metadata](https://docs.github.com/en/rest/actions/artifacts).

## Evidence And Approval

### Acquiring A Candidate

`collect-release-evidence.yml` is a separate, manual **acquisition-only** workflow.
It accepts no candidate URL or arbitrary commands. Run it on the default branch of
the reviewed private export repository, after its initial source snapshot has been
committed. It intentionally refuses the original dirty development checkout,
shallow or unrelated history, and files/modes that differ from the committed
`SOURCE_SNAPSHOT.json`. It does not accept arbitrary existing repository history.

An explicit follow-up mode now accepts a clean, bounded linear descendant of the
audited history-free root `949910304aa5e978826df034e65b1de579d9e330`. The root is a
literal pin in trusted default-branch workflow policy, not a dispatch input or a
value read from an unreviewed evidence bundle. It must be the actual parentless
root; unrelated refs, merges, shallow history, external Git storage and more than
256 commits are rejected. All raw commit objects and current manifest/blob/mode
bindings are checked. DCO is checked for every commit including that root. This
does not inspect intermediate commits for personal data or approve future source
changes; prior review and complete history secret scanning remain necessary.
The default standalone verifier still permits only a one-commit export unless a
separately trusted `--export-root` is explicitly supplied. Source and image
receipts bind the same complete history selection. This removes a reproduced
local two-commit acquisition failure, not the remaining security findings or the
need for an actual hosted run. The workflow change remains local until separately
reviewed and adopted; no hosted compatibility or approval is inferred.

The workflow installs locked tools, binds the checkout before and after work,
collects source scans, and builds and scans all eight Compose service images. It
does not start the applications or use model/provider credentials. Build and scan
commands share a controlled environment, an explicit Compose file/example env file,
and an isolated project name; inherited local Compose settings are not accepted.

The source collection validator requires complete raw reports, successful secret
checks, matching source and scanner identity, and a matching original scanner exit.
An advisory-bearing scan retains `passed: false`. Collection may complete while
findings still need review; neither an empty assessment nor automatic waiver is
created. The resulting receipt always says `qualification_passed: false`,
`security_approved: false`, and `release_approved: false`.

Artifacts retain original source reports, image reports/SBOMs, identity records,
stage outcomes and hashes. The source archive is created only after complete clean
secret checks, checked against the source manifest after safe extraction, and
uploaded only after successful full acquisition. Image JSON is staged once and
separately secret-checked before upload; final packaging checks those same files
against the validated image references, without recopying unscreened originals.
The complete collection also pins the exact source receipt. Final staging rejects
a replaced receipt even if its summary is unchanged and provenance was regenerated.
Older collections without this pin require a fresh collection; do not edit their
retained receipts to manufacture compatibility.
The image check uses the committed scanner configuration. Its only image-specific
exception matches the exact published Python signing-key fingerprint in a
`GPG_KEY` field, and only in API/migration/worker image-config and scan JSON paths.
This is public verification material, not a credential; other fields, fingerprints
and paths remain scanned. See the official
[Python image build source](https://github.com/docker-library/python/blob/master/3.12/slim-trixie/Dockerfile).
The artifact retains the canonical `.opencommerce/` relative paths so later
verification can resolve the recorded references. Failed full-image archives, source mirrors,
tool caches, credentials and build logs are not uploaded. Secret-bearing image
evidence is deliberately withheld, not claimed as safely retained in GitHub;
investigate it in a secured environment. Download permitted artifacts before their
30-day retention expires. Secret scanning reduces risk but is not a guarantee that
data is suitable for public disclosure.

This collector does not resolve the matched-interpreter/platform replay limitation
below. A green acquisition run is not a replacement for assessment review, runtime
tests, or the protected security-verification workflow. No hosted run is claimed
until its actual URL, commit and results have been inspected.

The strict models in `scripts/verify_current_release.py` define the approval format.
Do not turn the pending record into an approval by mechanically copying outputs
from an unreviewed candidate. A human must review the exact evidence and limitations
before adopting these fields through the protected default branch:

| Fields | Required identity |
| --- | --- |
| Repository and environment | Repository name and numeric ID; environment numeric ID; permitted human reviewer IDs |
| Review window | Named reviewer, actual UTC review time and future expiration |
| Candidate | Exact source-tree SHA-256 and build commit |
| Build and evidence runs | Run ID, attempt, workflow ID/path, commit; successful same-repository push or manual run |
| Both artifacts | Immutable artifact ID/name, API digest and size; unexpired and created during the selected attempt |
| Build provenance | Exact path, size and SHA-256 of the original build's provenance document |
| Review bundle | SHA-256 of `release-evidence.tar`; image and source review document paths, sizes and hashes |
| Limitations | Concrete remaining boundaries, never an empty list |

The original build artifact must retain `.opencommerce/ci-evidence/provenance.json`,
`.opencommerce/security-scans/final/`, and `.opencommerce/source-scans/`. The verifier
rechecks provenance file hashes against the original downloaded files, then
compares every inventory child digest with its provenance entry. Inventories alone
are insufficient: scans, SBOMs, image identity inputs, source manifests, exported
requirements, scanner version streams and secret-scan logs must be present.

The separately assembled review bundle includes the same bound inventories and
raw evidence, frozen source files/modes, typed assessments and referenced proof.
An approved manifest hash must come from the adopted record, not from an untrusted
artifact telling the verifier which hash to expect. Both the image and source
verifiers must pass against the same approved source identity.

For an already reviewed bundle, standalone checks are available without GitHub:

```sh
.venv/bin/python scripts/check_release_assessments.py \
  --bundle-root release-evidence --review-manifest reviews/images.json \
  --expected-review-sha256 "$APPROVED_IMAGE_REVIEW_SHA256" \
  --expected-source-sha256 "$APPROVED_SOURCE_SHA256"
.venv/bin/python scripts/check_source_assessments.py \
  --bundle-root release-evidence --review-manifest reviews/source.json \
  --expected-review-sha256 "$APPROVED_SOURCE_REVIEW_SHA256" \
  --expected-source-sha256 "$APPROVED_SOURCE_SHA256"
```

These commands verify consistency only; they do not create approval. In hosted
verification, a short-lived prepared receipt is also bound to the policy commit,
current run, reviewer and exact approval bytes. It is temporary same-run state,
not a transferable signature or standalone authorization.

## Source And Image Boundaries

The legacy `scripts/check-image-findings.py` gate also requires hashed retained
manifest, config, inspection, scan and SBOM files, checked through the current
strict image-relationship validator before any disposition. Image/index IDs need
not equal config IDs: the selected platform and filesystem relationship must
match. Legacy reviews now require schema 4 and an exact
`reviewed_image_config_id` for every record; missing evidence, schema-3 reviews,
and changed config pins fail closed. There is no automatic migration or authority
to add pins to historical reviews. The record digest binds the whole finding,
including layer provenance and fingerprint; policy/proof output hashes use the
same byte snapshots that were validated. Historical JSON, raw evidence, expiration and
deployment mismatches remain unchanged; synthetic regression success neither
qualifies scans nor approves a release.

Source collections require current collector timestamps, marker provenance, all
six reports, both secret logs, requirements and all ten tool-version streams.
Older collections cannot be qualified by adding assertions to their inventories.
The marker replay requires identical trusted interpreter bytes, packaging version
and marker environment; coverage on a different platform or interpreter is not
inferred. Use a matched collector/verifier environment. This compatibility must be
demonstrated in the hosted run, not assumed from the local tests.

Every Python advisory and Node advisory finding requires an exact assessment,
including Python findings whose scanner supplies no severity. Changed raw fields,
versions, finding paths, evidence, dates or source identity invalidate the old
assessment. Secrets, missing/expired reviews, and applicable runtime findings have
no waiver path here. Non-runtime source findings may use a scoped mitigation only
with bound remediation and verification evidence. Runtime findings may pass only
through reviewed not-applicable determinations; hash validation does not establish
the truth of scope, reachability or upstream-fix judgments.

The collector's raw `passed: false` remains false when advisories exist. Assessments
are a separate layer, not edited scanner output. Preserve earlier failures and all
raw scans, SBOMs, review versions and hashes for audit.

## Safe Transport

`scripts/release_evidence_archive.py` provides `pack_bundle` and `unpack_bundle`.
Packing is deterministic, preserves permission bits and normalizes owner/time
metadata. It does not choose files, redact secrets or approve their disclosure.
Privacy-review the selected tree first. An archive preserves modes that GitHub's
normal ZIP artifact upload would not: [artifact permission limits](https://github.com/actions/upload-artifact#permission-loss).

Only canonical uncompressed USTAR with ASCII paths is accepted. Limits are 32 MiB
per file, 256 MiB total contents, 8,192 members including directories/root, and
64 path components, plus USTAR name/prefix limits. Links, devices, sparse files,
extensions, duplicates, traversal and special permission bits are rejected. The
entire archive hash is checked before extraction into a fresh destination under
an empty caller-owned `0700` parent. No extracted file is executed. I/O failures
can leave private partial output; never consume a failed attempt. Same-user or
privileged hostile concurrent filesystem changes are not an isolation guarantee.

## Remaining Adoption Work

1. Collect fresh exact-candidate evidence with a matched environment and retain a successful, pinned build/evidence-producing run.
2. Assemble and independently review the current typed bundle; privacy-review every file before artifact upload.
3. Configure and verify the protected environment and repository protections; adopt the exact approval pins with owner approval.
4. Dispatch and inspect the hosted verification, including real API response compatibility and artifact retention.
5. Prove this mandatory current path before changing the role of historical qualification gates. Preserve their evidence and failures.
6. Complete all non-security release gates and separately seek publication approval for the exact candidate.

The workflow uploads only its prepared receipt and result, not the downloaded raw
bundle. Audit these outputs before public use. No step here makes a repository
public or publishes a product.
