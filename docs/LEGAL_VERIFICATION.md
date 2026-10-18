# Owner-approved legal metadata verification

The owner selected Apache-2.0, Copyright 2026 Han Chen, the exact root NOTICE,
DCO 1.1 without a CLA, and the private reporting policy in SECURITY.md. This
record preserves September 5, 2026 local artifact verification and describes the
current packaging checks separately. Historical artifact counts and installed
versions below do not qualify the current source or rebuilt images. It is not
publication approval or an independent legal opinion. Contributors retain their
own copyrights.

**October 18 correction:** collection coverage and matching hashes do not prove
complete attribution. Four upstream original-notice gaps remain in the retained
source-inclusive archives. New source/image checks and collectors reject these
template-only fallbacks. See [dependency attribution status](DEPENDENCY_ATTRIBUTION.md)
for exact packages, reproducible local checks and resolution requirements. The
historical proofs below are preserved, not retroactively upgraded.

The later owner-approved source-only export removes the 78 affected copied files
from its three public derivatives, preserving identities and original hashes as
metadata. First-party exclusion disclosures are not upstream license notices.
Private originals remain intact. Inventory coverage does not resolve runtime
attribution: the same four-package image gate remains failed. See the linked
attribution document for exact derivative identities and scope. Historical counts
below describe the full original collections, not the narrowed public archives.

## Canonical text and metadata

- LICENSE is the complete, unmodified [Apache 2.0 text](https://www.apache.org/licenses/LICENSE-2.0.txt).
  SHA-256: `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
- DCO.md is the unmodified [DCO 1.1 text](https://developercertificate.org/).
  SHA-256: `f7ac75b443f4ca16b503241344b41aeff9503b0c30bedc2b119551d83cb0fa90`.
- NOTICE contains only the owner's supplied statement, including its final newline.
  SHA-256: `9c4db56c10c1680e2d0f3d6ffa558f5c8d6786240a2a4f8ad4a1bf1f97384275`.
- Python, npm, OpenAPI and project-built image metadata say Apache-2.0. Container
  labels cover first-party additions, not a relicensing of their dependencies.
  Generated package copies are checked byte-for-byte by `make check-openapi`.

No restrictive rider, dual license, copyright assignment, CLA, or bulk per-file
header change was added. Existing third-party legal files were not rewritten.

## Contributions and private reports

`DCO / DCO` checks all commits in the PR range, including merges, and requires
matching author/coauthor sign-off trailers. The workflow executes only the
trusted base's checker, treats fetched PR history as data, uses read-only
permissions and does not persist checkout credentials. Temporary synthetic Git
histories exercise unsigned, malformed, wrong-identity, body-only and coauthor
cases. This is trailer enforcement, not verification of a person's legal rights.
No real commit was signed or history rewritten on another person's behalf.

The owner-verified private fallback is hc414t@gmail.com with subject prefix
`[Open Commerce Agent Security]`. GitHub Private Vulnerability Reporting is the
primary public channel. Required-check settings, private reporting enablement,
administrator notifications and non-admin visibility remain launch-time checks:
the release report records the actual private repository settings separately from
these earlier local legal checks.

## Historical Distributions And Current Checks

The [versioned legal proof](../security/legal-verification/2026-09-05-arm64/manifest.json)
records all four package archives and six project-built image identities, matched
to that historical scanner archive. Its runtime privilege evidence covered seven
service images. The historical native bundle contains 805 files from 387 source
packages; Qdrant's separate collection contains 1,500 files from 782 packages.
These proof files remain unchanged.

The current `scripts/verify_release_legal.py` instead requires five archives:
the Python wheel and sdist plus SDK, operator-web and shopper npm tarballs. Its
image check covers eight Compose services: API, migration, worker, operator web,
shopper, PostgreSQL, Qdrant and Redis. It verifies canonical first-party legal
bytes and metadata where applicable, and checks Redis's separate upstream notices
without applying an Apache label to Redis. Run it against the exact new artifacts;
the September proof is not evidence that these current checks passed.
Local package archives remain private prerelease artifacts, not published or
independently supported installation products.

Containers retain Debian/Alpine and Python/Node package copyright/license files.
Node's base includes `/usr/local/LICENSE` and GNU common-license texts; Python's
base retains `/usr/local/lib/python3.12/LICENSE.txt`. PostgreSQL carries the
unaltered [16.15 COPYRIGHT](https://github.com/postgres/postgres/blob/REL_16_15/COPYRIGHT).

### Web native and JavaScript dependencies

The production build enumerates its actual Next.js standalone dependency graph,
matches installed name/version identities, collects original legal files, and
fails when a new unhandled omission appears. The September verified image covered
21 runtime packages and Next.js compiled notices. Its three reviewed fallbacks preserve
upstream text: Next 15.5.25 for `@next/env`, React 19.2.8 for its `client-only`
marker package, and the tagged sharp-libvips notices for the native bundle.

The sharp-libvips collection preserves its original library/license table,
installed README/version inventory, and full source legal texts for all 28 named
native libraries plus every dependency in their Rust lockfiles. The native
manifest records exact source archive URLs/hashes and every retained file hash;
the production build refuses a different native version inventory. Its exact
tagged build source is commit
`6e5971d333377743163edc3ad9e5d0b897abcbc9` in
[sharp-libvips](https://github.com/lovell/sharp-libvips/tree/6e5971d333377743163edc3ad9e5d0b897abcbc9).
The original table alone was insufficient; `native-notices.tar.gz` now preserves
the additional texts, including FreeType's FTL and the full libvips license.
Five old Rust crates declare MIT but omit standalone text: their original authors,
declarations/source and the unchanged standard template are retained. Separate
upstream notices found for malloc_buf and difflib are also retained at their
recorded commits, without replacing their original copyright statements.
The other three, block 0.1.6, objc-foundation 0.1.1 and objc_id 0.1.1, remain
blocked for original-notice evidence. The template and author fields alone do
not satisfy the current attribution gate.
Applicable source availability and relinking obligations still govern future
redistribution. Use the exact source URLs in the native manifest and the tagged
build scripts/patch URLs above; no anti-relinking restriction was introduced.
This work does not invent upstream attribution or replace those obligations with
the project's Apache label.

### Qdrant

`security/third-party/qdrant-1.19.1/` preserves the shipped upstream SPDX inventory,
the deterministic notice archive and its source/file-hash manifest. The inventory
contains 782 packages, including build/platform dependencies, so the collection
is intentionally overinclusive. There are 1,500 retained legal/attribution files.
The tagged Cargo.lock SHA-1 `fe74ae33437c81bbe84f26564fbdfa62d044d541`
matches the shipped SPDX record. Downloads were read as data, not built/executed.

Seven crates declare an Apache option but omit a standalone text. Their original
declarations/source attribution accompany the unmodified Apache text; exact
choices are recorded in each `license_selection`. Stumpalo 1.0.0 declares BSD
3-Clause but its crate and recorded source revision omit a copyright/license file.
The archive preserves its declarations/source and the unchanged SPDX standard
template, explicitly identified as a template. It does not invent a copyright
holder or claim that template is an upstream copyright notice. Upstream omissions
remain visible for distribution review, not silently filled with project ownership.
The current gate explicitly blocks Stumpalo attribution verification; the old
collection's completeness flag does not resolve this omission.

### Redis: Current Wrapper

The earlier September configuration pulled Redis directly. The current
[Redis Dockerfile](../infra/docker/redis/Dockerfile) builds a local wrapper from
the pinned upstream 7.4.11 image. It updates Alpine packages, retains the upstream
Redis binary and restores upstream legal files under `/usr/share/doc/redis/`.
The resulting image is modified; describing it as an unchanged upstream image
would be incorrect. No Apache license label is applied to Redis.

Its `RSAL-2.0 OR SSPL-1.0` terms are separate from the project's Apache-2.0
license. The [retained Redis collection](../security/third-party/redis-7.4.11/README.md)
records exact sources, hashes and limitations. It is not a complete corresponding-
source distribution or clearance for hosting or binary redistribution. Those
obligations require review for the actual distribution and license choice. No
first-party hosted-service or field-of-use restriction was added.

## Reproduction and limitations

The current recipe includes the shopper archive; it does not reconstruct the
private September artifacts. Use the locked developer environment and a new,
empty artifact directory. Image verification inspects already-built images; it
does not build them or qualify their security. Retain the command output and
exact artifact identities with any new proof.

```bash
python3 scripts/sync_release_legal.py --check
.tools/uv/bin/uv build --package open-commerce-backend --out-dir .opencommerce/distribution-artifacts
npm exec --yes pnpm@10.17.1 -- --dir packages/sdk-typescript pack --pack-destination "$PWD/.opencommerce/distribution-artifacts"
npm exec --yes pnpm@10.17.1 -- --dir apps/web pack --pack-destination "$PWD/.opencommerce/distribution-artifacts"
npm exec --yes pnpm@10.17.1 -- --dir apps/shopper pack --pack-destination "$PWD/.opencommerce/distribution-artifacts"
.venv/bin/python scripts/verify_release_legal.py --artifacts .opencommerce/distribution-artifacts --output .opencommerce/package-legal-proof.json
.venv/bin/python scripts/verify_release_legal.py --images --output .opencommerce/image-legal-proof.json
```

The CI qualification workflow performs these actual archive/image checks before
collecting evidence. Use a clean artifact output directory. Rebuild and refresh
the collections and SBOMs after changing dependencies, base images or platform.
Local arm64 verification does not attest to amd64 images, future artifacts, legal
ownership outside the owner's statement, or fulfillment of every upstream source
distribution obligation. No packages, images, tags or releases were published.
