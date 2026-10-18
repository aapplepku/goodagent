# Historical Private v0.1.0-rc1 Procedure

This preserves the September 2026 simulator RC procedure and its then-current
limitations. It is not authorization or a checklist for publishing the later
self-hosted alpha. The original authorization covered private hosted validation,
not a public release; package versions were `0.1.0rc1` (Python) and `0.1.0-rc1` (Node).
The detailed release report is retained privately outside the public source export.
See [historical RC notes](releases/v0.1.0-rc1.md) for the later RC outcome and
[public source qualification](PUBLIC_SOURCE_EXPORT.md) for the current process.

## Authorized sequence

1. Finish the reviewed RC corrections, portable documentation and strict
   vulnerability assessments. Preserve raw evidence and all simulator-only gates.
2. Use the verified private destination `aapplepku/opencommerce` and repository-local
   identity `Han Chen <hc414t@gmail.com>`. Never alter global Git configuration.
3. Run local checks, inspect the entire staged tree, then create exactly one
   initial DCO-signed commit on `release/v0.1.0-rc1`. Do not rewrite historical commits.
4. Verify repository visibility is private before pushing. Configure protections
   for the RC/default branches using the actual emitted required check names.
   Require pull requests, DCO, qualification, up-to-date checks, review dismissal
   after new commits and resolved conversations; prohibit force pushes/deletion
   and enforce protections for administrators. Verify account-plan support.
5. Run the private RC workflow against the exact SHA. Inspect all hosted checks,
   raw failures/findings and artifacts, not only a green summary.
6. Download the immutable hosted artifact before its retention expires. Produce a
   final report with workflow URLs, environment/commands, test/scan counts,
   assessments, remaining risks, SBOM locations and SHA-256 hashes.
7. Stop before tagging or any publication and obtain separate approval.

The workflow automatically runs on a push to the exact RC branch. Manual dispatch
is also defined; GitHub may require the workflow on the repository's default
branch before dispatch becomes available. Do not create extra branches or commits
merely to work around dispatch availability.

## Exact-commit evidence rule

The hosted results refer to the tested commit. Adding those results to that same
commit changes its SHA and invalidates the exact-SHA assertion. Preserve post-run
reports as hosted/local evidence artifacts instead. The owner authorizes
evidence-backed qualification fixes as additional DCO-signed commits, each with a
new candidate SHA and complete SHA-sensitive rerun. This is not feature authorization.
Never amend a passing commit and reuse its checks.

## Current limitations

The third candidate `4702a4e5236f451f969f275ce33eb9c421868037` passed hosted core
qualification including DCO, fresh source/image scans and nine SBOMs, confirming
the build/scanner corrections below. It is nevertheless superseded: review found
measurement defects (unsupported units/revenue series, unavailable CAC as zero,
incorrect chart labels/signs) and a smoke-artifact retention omission. Its full
benchmark was cancelled with all partial journals retained. The corrective
candidate must rerun every hosted gate; no partial pass transfers to a new SHA.

The private repository and initial signed-off SHA
`d490eeccd473e5c8f8cb2e6508679c8035a24e88` exist. Its hosted attempt passed clean
setup/build/migrations, complete checks, browser/recovery/reset and DCO, then was
cancelled after benchmark timing exposed a scheduling risk. It is not a qualified
SHA. A qualification-only fix partitions the unchanged two 1,200-case sweeps
across four independently migrated PostgreSQL jobs and retains partial journals.
The final assembly gate requires exact SHA/source/byte provenance, all cases,
no failures or hard violations, and agreement with the committed full reference
and independent reproduction. A new signed-off SHA must rerun every hosted gate.
The follow-up hosted attempt also failed scanner report creation because its
capability-dropped containers did not own runner bind mounts. Replacement
preparation uses the runner UID/GID and patches the newly disclosed, previously
unaudited Python build pins. [The correction record](BUILD_DEPENDENCY_VERIFICATION.md)
preserves the original findings, strict audit coverage and fresh image re-review.
Neither existing SHA is qualified; all four interrupted journals from the second
attempt remain evidence, not completed benchmark results.
Final protection verification and exact-SHA review remain pending. The progress fill was
reclassified as MEDIUM because it could misrepresent measurement attainment;
the RC correction removes the inferred ratio and tests authoritative values.

All 268 earlier raw HIGH/CRITICAL records remain with scoped, expiring
not-applicable assessments, not patched-package or zero-vulnerability claims.
See [security methodology](SECURITY_VERIFICATION.md). This is a trusted
loopback-bound simulator with synthetic data, not production authentication.

The [legal verification](LEGAL_VERIFICATION.md) covers Apache-2.0, the exact
NOTICE, DCO 1.1, upstream notices and private security contact. Native distribution
terms and upstream omissions remain explicit; Redis is not Apache-2.0.
The stable-version patch in `docs/releases/` is historical and unapplied.
It must not be used during this RC stage.

## Proposed tag command

Not executed. Only after the exact SHA passes all required hosted checks and
the owner separately authorizes tag creation:

```bash
: "${RC_SHA:?Set the exact fully qualified RC commit SHA}"
test "$(git rev-parse --verify "${RC_SHA}^{commit}")" = "$RC_SHA"
git tag -a v0.1.0-rc1 "$RC_SHA" -m "Open Commerce Agent v0.1.0-rc1"
```

There is deliberately no tag push or release-publication command in this stage.

## Proposed public-release checklist

- Obtain explicit approval for visibility change, tag push, publication and
  announcements separately; none follows automatically from passing RC checks.
- Resolve or explicitly review all remaining findings; refresh scans and expiry
  against the exact proposed artifact. Preserve raw counts and accepted risk.
- Independently review license/notice/source/relinking obligations for any binary
  distribution. Prepare source availability without assuming package/image publication.
- Establish a supported deployment/authentication boundary before any hosted demo;
  keep live commerce and advertising providers disabled.
- Verify branch protections, DCO enforcement and required checks from a non-admin
  account; ensure administrators receive security notifications.
- Enable/test GitHub Private Vulnerability Reporting when supported at the public
  transition, before announcement; retain the verified private email fallback.
- Download all hosted raw evidence/SBOMs, verify hashes and archive the exact SHA
  and workflow links beyond hosted retention.
- Review README, threat model, limitations, benchmark methodology and release
  notes for accurate simulator-only claims and no personal/temp environment data.
- Decide separately whether/when a stable `v0.1.0` is warranted; it is not
  authorized by the present RC decision.
