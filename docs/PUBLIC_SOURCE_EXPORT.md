# Public Source Candidate

The public alpha is a new source snapshot, not a copy of the private repository's
Git history. Historical development and review records remain private. A snapshot
records what was exported at the actual time; it does not establish legal ownership
or backdate authorship. Publication still requires owner approval of the exact SHA.

## Prepare And Inspect

From the private working checkout, choose new paths for each attempt:

```sh
python3 scripts/export_public_source.py --inventory .opencommerce/public-files.json
```

Inspect that private JSON before exporting. It lists every selected relative path,
size, mode and SHA-256, plus exclusions. It includes uncommitted runnable source;
Git-ignored files are never automatically discovered. Private review scripts and
their own tests are excluded together with `qa/`, plans, runtime files and unrelated
archives and non-template environment files (including prefixed names and backups).
Application code, product tests, migrations, lockfiles, licensed
samples and security evidence remain selected. The source tree itself is unchanged.

Two historical hosted API captures contain account-specific annotations and internal
tool wrappers. They are explicitly excluded by path before reading, even if a
hand-edited inventory requests them. Their complete originals remain unchanged in
the private repository. A separate
[sanitized hosted summary](../examples/eval/merchandising-decisions-v2/validation/hosted-public-summary.json)
preserves selected failure/skipped outcomes, observed times and original record
hashes. It is not a raw API response, a fresh hosted run or a way to reconstruct
the omitted originals. The adjacent historical recipes also require private Git
objects and artifact ZIPs that this source export does not provide. Raw vulnerability
reports, applicability assessments and SBOMs are not replaced by this summary.

```sh
python3 scripts/export_public_source.py --manifest .opencommerce/public-files.json \
  --output .opencommerce/public-candidate
```

Inventory and candidate destinations must be outside the checkout or inside its
ignored `.opencommerce/` directory, never under `.git` or exportable source.
Export rejects symlinks, path traversal, changed files and credential-shaped text.
Compressed evidence and license notices are limited to the exact byte identities
in `infra/public-export-archives.json`. This is a retention list, not publication
approval. Their expanded contents are also inspected, without filesystem extraction,
with size and member limits. An archive with private paths or credential-shaped
content blocks export; retain the original privately and resolve its public-copy
policy rather than overwriting historical evidence or bypassing the check.
It never overwrites a destination or initializes Git. `SOURCE_SNAPSHOT.json` in the
new directory inventories the copied bytes; private exclusions and source paths
outside the repository are not included. Run full secret/content/license review on
this exact output, including compressed evidence and image provenance. The built-in
pattern checks are defense in depth, not proof that an export is safe to publish.

Media, every CSV file anywhere in the selected directories (including `.CSV`
and mixed-case extensions), and files in the sample dataset directories require
reviewed exact path/hash entries in `infra/public-export-assets.json`. An image,
PDF, recording or CSV is not public merely because it sits next to source code.
Unlisted assets are excluded without reading their contents; changed listed assets
block the export until reviewed.
Text candidates must be UTF-8 and NUL-free, and checks reject common binary headers,
including PDF headers starting within the first 1 KiB after a preamble. These are
bounded detection checks, not a complete content classifier or privacy review.
The asset manifest retains the
48 attributed sample images and their copies, the explicit dataset files, six
historical simulator screenshots, four earlier interface screenshots and four
inspected current GoodAgent screenshots. The
[current media manifest](assets/alpha/20261018-current/manifest.json) and
[earlier interface manifest](assets/alpha/manifest.json) bind each gallery's source,
mode and exact bytes. This is candidate retention, not rights clearance or
publication approval.
Inspect visible content and provenance before adding entries; never regenerate it
by accepting every file in a directory. The prior shopper illustration was excluded
at the owner's request; the welcome surfaces use attributed ABO sample photos with
visible credits instead. Do not change old snapshots
to remove an excluded file: retain them privately and create a new candidate.

Notice archives use the separately reviewed source-only profile documented in
[dependency attribution](DEPENDENCY_ATTRIBUTION.md). Export replaces three exact
manifest/archive pairs with deterministic derivatives excluding all copied files
of four known attribution-gap packages, and updates their three archive-retention
hashes. Original files remain unchanged in the private checkout. Seven first-party
exclusion disclosures retain dependency coverage without claiming upstream notice
or runtime redistribution clearance. Source and derivative identities are pinned
in `scripts/source_only_notices.py`; matching self-edited metadata is insufficient.
The other retained archives, raw scans, SBOMs and assessments are not rewritten.

The CI source substitution is explicit: `infra/github/public-ci.yml` becomes the
candidate's `.github/workflows/ci.yml`. It removes the private-repository-only guard
for the separate repository and supports DCO checks on a root commit. It retains
read-only workflow permissions, trusted-base DCO checking for pull requests, and
all qualification jobs. Every push and manual run checks all reachable commits,
including the initial public snapshot. A previous push is not treated as a passed
check, so a signed follow-up cannot hide an unsigned ancestor. Pull requests still
check their contribution range against the trusted base. Complete commit messages are
parsed without treating Markdown horizontal rules as email-patch dividers; each
author and final-trailer coauthor still needs a matching sign-off. Messages containing
Git's reserved scissors delimiter are rejected as ambiguous: Git would silently
ignore the suffix even if it is present in the stored commit. Ordinary Markdown
horizontal rules are allowed. This checker never rewrites a commit. The original
private CI and its historical baseline protections are unchanged.
Pushes, pull requests and manual runs invoke qualification, whose artifact-upload
steps can run after test/security failures, but uploads require successful provenance
and privacy checks. An exclusive hash-bound staging tree is screened with the pinned
offline secret scanner, including bounded expansion of gzip reports, and rechecked
before upload. Selected diagnostic artifacts are retained for 30 days. They include
service/provenance logs, raw scan reports, benchmark results and the filtered Compose
browser receipt. Binary browser traces, screenshots and recordings require separate
review and are not automatically uploaded. A privacy failure withholds diagnostics;
retain originals privately before removing the runner, and do not call that run a
complete evidence collection. Read-only permissions do not prevent artifact uploads.
Review the selected paths and generated contents before enabling these hosted runs;
use only disposable synthetic fixtures and no model or store credentials. A local
commit runs no hosted job. These workflows do not deploy, change visibility, create
a release/tag, or publish packages or container images.

## Experimental Source Disclosure

The owner may approve an experimental source snapshot before alpha qualification
is complete. This is source disclosure, not a qualified release or authorization
to deploy a public service. Keep failed checks, incomplete reviews, absent recordings
and known limitations explicit. Do not suppress failing gates or imply that an
earlier scan qualifies changed source.

Before creating the history-free commit, review the exact inventory, contents,
licenses and asset provenance. Secrets, customer data, private conversations,
unrelated personal documents and unreviewed redistribution assets must not be
included. Check the documentation links and media against the staged tree.
Initialize a separate private repository with the owner's confirmed author identity
and truthful DCO certification; do not copy `.git` or invent historical commits.
Record actual preparation timestamps, the source manifest hash, exact commit SHA,
licenses and independent review evidence. Publication requires the owner's approval
of the exact separate repository and commit. Keep the original repository private.

## Qualified Alpha Follow-Up

Before claiming a qualified alpha, install locked dependencies in the candidate and
run the full documented checks, clean Linux CI, container scans, current
HIGH/CRITICAL applicability review, backup restoration, browser journeys and model
evaluation. Complete the planned reviews and recordings. Historical reports do not
qualify new bytes, and expired assessments intentionally fail their gates. Any
source change requires affected qualification to run again. Source publication
does not waive these requirements or accept unresolved vulnerabilities.

Current export tooling prepares a candidate, not a qualified release. It does not
create a repository, upload files, change visibility or push a tag. Credential
rotation, review and exact-candidate approval remain separate responsibilities.
Use the [publication checklist](PUBLIC_RELEASE_CHECKLIST.md) to keep source
disclosure approval separate from the later alpha qualification decision.
