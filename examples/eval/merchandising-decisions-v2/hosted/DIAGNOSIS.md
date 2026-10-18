# Historical Hosted Failure: Execution Did Not Start

Inspected 2026-09-07 UTC. Original run
[34065619247](https://github.com/aapplepku/opencommerce/actions/runs/34065619247)
remains failed at attempt 1. No retry was dispatched.
This link refers to the original private repository and may be inaccessible to
public readers. This document is a sanitized historical summary, not a fresh run.

## Direct evidence

Job `101589007654` did not start its code-validation steps. Account-specific
provider annotations and internal tool-response wrappers are omitted from the
public export. The complete original API record remains private and unchanged;
the [public execution summary](../validation/hosted-public-summary.json) retains
its hash, the observed outcome and timestamps without the private annotation.
The job has no steps, runner ID 0, empty runner name, and a seven-second lifetime
(00:54:41 to 00:54:48 UTC). Log download returns BlobNotFound. These corroborate
the recorded startup failure; they do not establish its underlying cause here.
DCO, core verification, and all four controller partitions passed.

## Independent verification

All five original artifact ZIPs are retained privately, including the complete core
qualification scans, SBOMs, logs, proofs, shard partial journals and provenance.
Their previously inspected bytes matched the GitHub API artifact digests below.
The ZIPs are not distributed with this source snapshot:

| Artifact ID | SHA-256 |
| --- | --- |
| 10000532537 (shard 1) | d78296f4298db82f17c8503344665dd3183404b00bf79ebfe1460f127945ec20 |
| 10000493260 (shard 2) | 891f1ed5aa6e3173999b09d12d25975bd9735056e5f6d42fdf3dd963dee29e82 |
| 10000462972 (shard 0) | 319b85ffbdb8d3c4c1d91dc6693196b2934433efb3b63a33270937016a5c3300 |
| 10000384347 (shard 3) | 6db6540785f3f5d8c75812a118fff811b69e1639b288bcb78cf8621ae07bd5c2 |
| 9999184982 (core) | b443cda6d1c9f0ae8659ae51cc66f2dd716cf496ec0ddd701f9cd001ac485d5c |

The run API's head SHA is `5962b51571a10b84c787a6d8a06aa3b884ce4275`.
The actual PR checkout and shard provenance identify merge SHA
`b2ec9351c225b244c206c0e84854da8148ba7e58`. Both trees are
`28d1ad6623afa2341d289a136b62c5d74b32c496`; their tracked diff is empty.
The unchanged assembler checked that merge SHA, the runtime source fingerprint,
every shard file digest, full seed coverage, complete rows, summaries, no
failures/hard violations and exact reference equality. Both 1,200-case sweeps
match `sha256:a1aeb60320deb3a202a6bc00ac1397f25a0d8b3a59bd2c74ecbe2cd321328e76`.
See `controller-assembly.json`. This is local verification of original hosted
results, not an additional independent benchmark or a hosted job pass.

**Historical private-evidence recipe, not runnable from this export alone.** It
requires the original private Git objects, unchanged base/merge tree, locked
environment and five artifact ZIPs listed above. None of those private Git objects
or ZIPs is supplied here. Public readers can inspect the retained result summaries,
but must not treat that as reproducing the original run.

With those separately authorized private prerequisites:

```bash
mkdir -p .opencommerce/decisions-v2/hosted/shards
unzip original/10000462972.zip -d .opencommerce/decisions-v2/hosted/shards/shard-0
unzip original/10000532537.zip -d .opencommerce/decisions-v2/hosted/shards/shard-1
unzip original/10000493260.zip -d .opencommerce/decisions-v2/hosted/shards/shard-2
unzip original/10000384347.zip -d .opencommerce/decisions-v2/hosted/shards/shard-3
.venv/bin/python scripts/controller-shards.py assemble \
  --directory .opencommerce/decisions-v2/hosted/shards \
  --output .opencommerce/decisions-v2/hosted/assembly \
  --expected-sha b2ec9351c225b244c206c0e84854da8148ba7e58
```

Here `original/` denotes the private retained artifact directory, not a directory
of ZIPs supplied by this public export or a new download. An initial local extraction attempt omitted the parent directory and
therefore failed before artifacts existed; after creating the directory the
unchanged assembler passed. That local setup error is not the hosted failure.

## Decision

No evidence of missing/inconsistent original artifacts, incorrect tested-SHA
handling, or reproduction mismatch. No workflow, source or expected-reference
correction was justified by this historical inspection. A new hosted attempt needs
separate authorization and current prerequisites. A partial rerun also needs deliberate review of the
attempt-specific download pattern so attempt-1 artifacts are not silently mixed
with later work. No retry or account-setting change is implied by this summary.
