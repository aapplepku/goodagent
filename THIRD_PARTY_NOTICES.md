# Third-party software and notices

Apache-2.0 covers this project's first-party work, not a relicensing of its
dependencies. Copyright and license terms in upstream, vendored and generated
files remain unchanged. Root NOTICE is the owner's attribution statement, not
a dependency inventory. External contributors retain their own copyrights.

## Distribution contents

- Python wheel and source distributions carry LICENSE, NOTICE and this document.
  Dependencies are separately installed from the lockfile; their original
  `.dist-info` licenses/notices and bundled-library attributions remain in the
  installed environment and backend containers.
- The TypeScript SDK is distributed as source with LICENSE, NOTICE and this
  document. Its npm dependencies are not bundled into the SDK archive and retain
  their own installed license files.
- The standalone operator and shopper images additionally carry unmodified-byte collections of
  notices from the actual installed runtime dependency graph, including Next.js's
  compiled dependencies. Its manifest records file hashes and package versions.
- Application, PostgreSQL and Qdrant containers carry canonical first-party legal files under
  `/usr/share/doc/open-commerce-agent/`. Third-party runtime and operating-system
  notices remain separate; the image's Apache-2.0 label describes first-party
  additions only and does not override base-image or dependency terms.
- Qdrant's upstream SPDX inventory and the exact-source notice archive identify
  its bundled Rust dependencies. PostgreSQL/Redis upstream attribution and
  base-system terms are preserved separately from the project NOTICE.

The Redis service is built locally from a digest-pinned upstream image, retaining
its Redis binary while applying supported Alpine package updates. It is not an
unchanged pulled image. Redis's upstream license texts are preserved separately
under `/usr/share/doc/redis/`; no container image is published by this project.
The pinned binary reports Redis 7.4.11, whose
[upstream terms](https://github.com/redis/redis/blob/7.4.11/LICENSE.txt) offer
RSALv2 or SSPLv1, not Apache-2.0. Those separate terms have not been changed,
replaced or added to the first-party project license. This release work does
not authorize hosting or redistribution of Redis under a different license.

## Inventory and updates

The experimental source-only export uses explicitly labeled notice derivatives.
All copied files of stumpalo 1.0.0, block 0.1.6, objc-foundation 0.1.1 and objc_id
0.1.1 are excluded because their applicable original notices remain unresolved.
Their package identities, source/file hashes and first-party exclusion disclosures
remain in the inventory. Those disclosures grant no upstream permission. No
dependency binary is included in the source snapshot; image/runtime attribution
remains blocked. See `docs/DEPENDENCY_ATTRIBUTION.md` for provenance and limits.

Versioned scanner SBOMs and exact image identities are recorded under
`security/reports/`. They describe detected components, not blanket permission
to redistribute them. Notice collection records source provenance and preserves
upstream legal text; it does not rewrite authorship or add project restrictions.

Regenerate and inspect legal collections when dependencies or target platforms
change. Keep license/NOTICE files distributed with each separately bundled
component. Source archives, required source availability and system-library
relinking obligations, where applicable, remain governed by the upstream terms.
No container, binary package or public release is published by local verification.
