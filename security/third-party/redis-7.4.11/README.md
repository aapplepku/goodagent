# Redis 7.4.11 Upstream Legal Collection

Collected on 2026-10-17 from the public Redis repository without authentication.
All 13 upstream files are unmodified, byte-for-byte copies from the verified
source archive; no line endings, notices or license terms were rewritten.

## Identity And Primary Sources

- [Release 7.4.11](https://github.com/redis/redis/releases/tag/7.4.11) and the
  [tag API](https://api.github.com/repos/redis/redis/git/ref/tags/7.4.11) identify
  commit `aaf0ce63b3239f4b51f86ca1da8711b055721993`.
- [Official source archive](https://github.com/redis/redis/archive/refs/tags/7.4.11.tar.gz):
  SHA-256 `e973da69febfea096ab94690b44bf976482788a1b5e070df373b4f27697d57d4`.
  This matches the `REDIS_DOWNLOAD_SHA` in the retained base-image build history.
- The archive's `src/version.h` declares `REDIS_VERSION "7.4.11"` and
  `REDIS_VERSION_NUM 0x0007040b`. The retained image configuration also declares
  `REDIS_VERSION=7.4.11`. This is static identity evidence, not a new binary run.
- `LICENSE.txt` was also fetched separately from the immutable commit URL below
  and compared byte-for-byte with the archive member.
- [Redis's licensing overview](https://redis.io/legal/licenses/) distinguishes
  Redis Community Edition 7.4's RSALv2/SSPLv1 choice from the later Redis 8 terms.
  The actual tagged `LICENSE.txt`, not a current-version summary, is retained here.

## Scope And Container Design

The wrapper remains based on
`redis:7-alpine@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499`.
It refreshes Alpine packages with `apk upgrade --no-cache`, preserves the upstream
Redis binary, copies this directory to `/usr/share/doc/redis/`, and retains
`USER redis`. No Apache license label is added to Redis. The upstream build
history downloads the archive above, builds Redis with TLS and jemalloc, and
removes `/usr/src/redis`; the wrapper explicitly restores these legal materials.

The collection includes every standalone LICENSE/COPYING/COPYRIGHT file in that
archive: the complete Redis RSALv2 and SSPLv1 text plus fpconv, hdr_histogram,
hiredis, jemalloc and Lua terms. Linenoise and the four bundled Lua extensions
carry notices inside their source; those five original files are retained whole
to preserve the copyright holders and full notices without constructing a new
license text. They are documentation only, not compiled or executed by this
wrapper. The original version header is included as provenance.

The manifest's `license` describes Redis, not all bundled components. Their
original Boost, CC0/BSD, BSD and MIT terms remain in the files below; no dependency
is relicensed under the project's Apache-2.0 license. This bounded collection is
not a full corresponding-source distribution, an audit of every source header or
Alpine package, or legal clearance for hosting or binary redistribution. Such
obligations still require review for the actual distribution and license choice.
Existing large source/image evidence archives are not changed or superseded.

## Exact Files

The table names original paths relative to `redis-7.4.11/` inside the source
archive; links pin the immutable upstream commit. Local copies of the two
extensionless `COPYING` files and the six `.c`/`.h` files have an additional `.txt`
suffix so they survive the existing public-source export policy. Their bytes
are unchanged. `manifest.json` records every such name in
`upstream_path_overrides` and supplies the local-path hashes to
`scripts/verify_release_legal.py`; these are hashes of original file bytes, not
rewritten or summarized notices.

| Upstream file | SHA-256 |
| --- | --- |
| [LICENSE.txt](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/LICENSE.txt) | `abffee3703161c0a6a0cd7f635b2c1ebb3b81bd199e9d18ea89652d678ae4287` |
| [deps/fpconv/LICENSE.txt](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/deps/fpconv/LICENSE.txt) | `c9bff75738922193e67fa726fa225535870d2aa1059f91452c411736284ad566` |
| [deps/hdr_histogram/COPYING.txt](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/deps/hdr_histogram/COPYING.txt) | `a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499` |
| [deps/hdr_histogram/LICENSE.txt](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/deps/hdr_histogram/LICENSE.txt) | `c124afa369aae960fa33f6944c82e161e482f2e998d6f07b37ae2c018f3c6c69` |
| [deps/hiredis/COPYING](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/deps/hiredis/COPYING) | `dca05ce8fc87a8261783b4aed0deef8becc9350b6aa770bc714d0c1833b896eb` |
| [deps/jemalloc/COPYING](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/deps/jemalloc/COPYING) | `94aa2caa98c25d942f58b956c71dba6a99ff98fc3a31cbc669fe2a4cd0268b53` |
| [deps/linenoise/linenoise.h](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/deps/linenoise/linenoise.h) | `a4e9aed50c78edf16fb3d7203e519c7ca104bd207f5131812d70724ecc26270b` |
| [deps/lua/COPYRIGHT](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/deps/lua/COPYRIGHT) | `ee5e3e82af1e1b543c4f216e399d7c8cfee797711913f349e385101c4ae60a79` |
| [deps/lua/src/lua_bit.c](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/deps/lua/src/lua_bit.c) | `78e10247b33d0db026cbe906d19b4bd3636840f195a63e93ce08c5dee9fb578a` |
| [deps/lua/src/lua_cjson.c](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/deps/lua/src/lua_cjson.c) | `20bcf34ee652800d41d769847022315d2e04beffb5c3070b8321f0e7f69d0054` |
| [deps/lua/src/lua_cmsgpack.c](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/deps/lua/src/lua_cmsgpack.c) | `0d2fd82fb47fc247a0e6f0a287f5429e81b7eb6735665e8d851bfb109961640d` |
| [deps/lua/src/lua_struct.c](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/deps/lua/src/lua_struct.c) | `57bc18e91a747a846ba76c070d9213452283c0ed9e652861ee7fabf87d590878` |
| [src/version.h](https://raw.githubusercontent.com/redis/redis/aaf0ce63b3239f4b51f86ca1da8711b055721993/src/version.h) | `9fa5ed92da961ec8030876760e89881670ebd2370add4f77ae582eaabb103a24` |

## Validation And Updates

Offline contracts pin the source identity, exact file set and hashes, Docker COPY
source/destination, public-export inclusion, preserved non-root user and absence
of Apache relabeling. They
exercise the image verifier against these actual bytes and reject each missing or
modified member. Run `.venv/bin/pytest tests/contract/test_redis_legal.py -q`.

The integration was prepared without Docker execution or builds. A fresh build
and `scripts/verify_release_legal.py --images` are still required to attest the
actual image filesystem. Changing the Redis base/version requires reviewing its
source identity, terms and notices again; update the collection, verifier policy
and tests together. Do not reuse historical image qualification for this layer.
