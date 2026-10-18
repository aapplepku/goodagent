# Dependency Attribution Status

The October 18, 2026 local review found **four unresolved original-notice gaps**.
The original private selection contains copied dependency source inside notice
archives and remains blocked for publication. The separately approved source-only
export excludes those copies as described below. Attribution verification for
affected images remains blocked. It is an evidence gap, not a finding of four
proven license violations or a legal opinion.

| Package | Declared license | Retained collection | Missing evidence |
| --- | --- | --- | --- |
| stumpalo 1.0.0 | BSD-3-Clause | Qdrant 1.19.1 | Original copyright/full license notice applicable to this version |
| block 0.1.6 | MIT | sharp-libvips 1.3.3 and 1.3.4 | Original copyright/full license notice applicable to this version |
| objc-foundation 0.1.1 | MIT | sharp-libvips 1.3.3 and 1.3.4 | Original copyright/full license notice applicable to this version |
| objc_id 0.1.1 | MIT | sharp-libvips 1.3.3 and 1.3.4 | Original copyright/full license notice applicable to this version |

These are seven occurrences across three collections, not seven distinct
packages. The historical manifests' `complete: true` flags describe collection
coverage, not complete attribution or redistribution clearance. The existing
archives, raw scans, SBOMs and frozen candidates remain unchanged.

## What Was Checked

Local cached crate archives match the original source hashes in the manifests.
The exact Stumpalo source revision and five cached repository snapshots for the
other three packages also lack an applicable original notice. Cargo declarations,
author fields and unchanged SPDX templates are retained evidence, but do not fill
in a missing copyright statement. Notices belonging to a different package by
the same author are not treated as permission to invent applicability or years.

Separate original notices for `malloc_buf 0.0.6` and `difflib 0.4.0` are already
retained; they are not among these four gaps. The current check is specifically
for known omissions and MIT/BSD template fallbacks, not an exhaustive dependency
license audit or proof of rights.

## Reproduce Locally

In the locked developer environment, use a new output filename:

```bash
.venv/bin/python scripts/verify_release_legal.py --source-notices \
  --output .opencommerce/attribution-review.json
```

This reads local files only. It validates archive/member hashes and package
coverage against the retained SPDX inventory or native dependency lockfiles,
then records the missing notices with their exact package/source identities.
The current result is exit code **1**, four blocked packages, seven occurrences.
The report deliberately distinguishes `archive_integrity_verified: true` from
`attribution_complete: false`. Existing output files are never overwritten.
The [retained machine-readable result](../security/attribution/2026-10-18/source-notices.json)
binds each collection's manifest, archive, package identities and original source
hashes. Rerun the command for changed bytes rather than editing that dated result.

The dependency-runtime attribution contract test also fails until applicable
evidence is present. Actual image verification and future collectors reject template-only
fallbacks instead of reporting successful notice verification. Passing the text
check alone is not proof of provenance. Template fallbacks additionally require
explicitly reviewed package/version, crate hash, upstream source URL/hash and
notice member/hash; self-consistent newly added text cannot clear the gate.
Applicability still requires review. No network collection runs as part of this
audit.

## How To Resolve

1. Obtain an authentic notice applicable to each exact version from its upstream
   release, history or maintainer. Preserve original text and source/revision/file
   hashes. Do not derive copyright holders or dates from account names or templates.
2. Add the reviewed evidence in a new collection, preserving the historical
   collection separately. Rebuild affected artifacts and rerun attribution,
   export-content, privacy, security and exact-artifact checks as applicable.
3. Alternatively, separately approve and review a new source-only selection that
   does not redistribute the affected copied material. Retain historical evidence
   privately and keep the unresolved dependency disclosure. This is a packaging
   decision, not a waiver or permission to redistribute affected binaries. It has
   now has owner approval for local preparation, with the exact resulting commit
   still subject to publication approval.

## Source-Only Export

The explicit `goodagent-source-only-notices-v1` profile removes all **78 copied
files** from the affected package directories across the three public archive
derivatives. Seven first-party `SOURCE_ONLY_OMISSION.txt` records replace them.
Those records are disclosures, not upstream licenses or permission. The complete
package/version inventory, upstream source URLs/hashes, removed file hashes,
SPDX inventory and Cargo locks remain available for audit.

`scripts/source_only_notices.py` binds both original and public manifest/archive
pairs to exact SHA-256 identities. All other retained member bytes are unchanged.
The exporter also updates the three archive hashes in the public retention list.
Arbitrary replacement bytes, invented notices and a `source_distribution` marker
alone cannot authorize a substitution. Re-export recognizes only the reviewed
public identities. Original full collections remain private and unchanged.

The manifests' `complete` flag still describes inventory coverage, while
`attribution_complete: false` explicitly records the unresolved notices. Builds
can consume the disclosed inventories; actual runtime/image attribution
verification still fails for the same four dependencies. The source snapshot
contains recipes and dependency declarations, not dependency binaries. Do not
publish built images or packages on the strength of source-only approval.

Public collection identities and omission counts can be checked locally:

```bash
python3 -c 'from pathlib import Path; from scripts.source_only_notices import verify_public_collections; print(verify_public_collections(Path.cwd()))'
```

Run that command inside the exported source, not the private original checkout.
The retained October 18 audit result describes the original collections; its old
archive hashes intentionally differ from the labeled public derivatives. It is
not silently rewritten or claimed as current-derivative verification.

No copyright attribution was fabricated, historical record changed, security gate
waived, download performed, or publication authorized. First-party Apache-2.0
and DCO remain unchanged. See [legal verification](LEGAL_VERIFICATION.md) and
[alpha validation](ALPHA_VALIDATION.md) for the separate remaining release gates.
