# Docker Infrastructure

Docker Compose is defined at the repository root. Use `make setup` for an isolated,
loopback-only self-hosted installation; it preserves existing configuration and data.

The PostgreSQL, Redis and Qdrant wrappers preserve pinned upstream service versions
while applying supported distribution security updates. Application images use the
shared Debian hardening script. Rebuilds can therefore have different OS package
versions and require new exact-image scans, SBOMs and applicability assessments.
Image digests and runtime proofs, not a Dockerfile alone, identify qualified bytes.

Redis retains its upstream licensing; wrapping it does not relicense Redis under
the project's Apache-2.0 license. See `THIRD_PARTY_NOTICES.md` and retained upstream
notices. No image publication is part of local setup.

## Final Runtime ACL Pruning

The shared hardener invokes `prune-runtime-acl.sh` after package upgrades. Account
creation must also finish first. It removes the seven reviewed direct consumers
(`cp`, `install`, `mv`, `sed`, `tar`, `useradd`, `usermod`) together with `libacl`,
not the library alone. Do not run package installation or account creation after
this step. Build-stage tools, package/version/path-list metadata, licenses and
unrelated runtime utilities remain intact; package scanners may still report the
retained `libacl1` package record.

The module accepts only Debian `arm64` (`aarch64-linux-gnu`) and `amd64`
(`x86_64-linux-gnu`). Before any target deletion it requires the expected real
parent directories, usrmerge links, a single architecture-qualified package path
list, seven regular singly-linked consumers, and one package-owned library with
its relative SONAME link. A physical metadata inventory rejects unexpected
library locations/copies, foreign package lists, extra aliases (including directory
and hardlink aliases), cycles and unsupported link metadata. Failures do not start
target deletion. This is a build-time operation on an exclusively owned filesystem,
not a transaction against concurrent mutation or protection from an I/O failure
during deletion. No file contents other than the bounded package path list are read.

Run the focused contracts without Docker or host package-manager operations:

```sh
.venv/bin/pytest -q tests/contract/test_runtime_acl_pruning.py
```

Tests use `--test-root` only with canonical, direct `/tmp` or `/private/tmp`
children named `runtime-acl-prune.*`. The destructive `--image` mode requires the
module installed at `/usr/local/sbin/prune-runtime-acl`; do not invoke it on a host.
The implementation uses shell/awk metadata checks, not an ELF parser. Renamed,
embedded or runtime-loaded code and new native consumers are not ruled out by
name/link checks. Later application copies can introduce dependencies, so complete
**final-image** ELF and filesystem verification remains required on both platforms.

This is an unqualified source candidate, not clearance of existing image findings.
After independent source review, qualify new exact images in disposable projects:
normal entrypoints/health, migrations, owner bootstrap/recovery, catalog and raster
indexing, Qdrant CRUD plus snapshot restore and graceful restart, then the actual
four-volume cold backup/restore drill with byte/uid/gid/mode verification. The
documented helper uses host Python and Docker copy, and Qdrant snapshots use Rust
tar; neither supported workflow requires the removed in-image GNU tar. Preserve
host tooling. Fresh source/image identities, scans, SBOMs and applicability review
are required; old ARM64 records and untested AMD64 images are not qualified by
these synthetic tests. No Docker or model call is part of the focused suite.

## Qdrant Shutdown

The local Qdrant wrapper runs the server directly as PID 1. The pinned upstream
shell entrypoint can return 143 when its wait is interrupted by SIGTERM, before
the child completes its shutdown. Cold backups require a confirmed clean server
exit instead of accepting that status. Optional upstream shell-driven OOM recovery
mode is not enabled in this single-node alpha; preserve the volumes and diagnose
an out-of-memory failure rather than silently starting recovery mode.

## Python Import Caches

API, migration and worker builds disable uv's optional eager bytecode compilation.
They retain the same locked dependencies, Python source, native extensions and
licenses, including the optional learned-search build. Runtime imports compile
source in memory; `PYTHONDONTWRITEBYTECODE=1` prevents writing new caches, but does
not prevent loading a cache supplied by an upstream package or the base image.
See [uv's compilation tradeoff](https://docs.astral.sh/uv/pip/compatibility/#bytecode-compilation).

This removes unnecessary build-generated files, not vulnerabilities. Each new
candidate still needs final-image inspection, import/ranking tests and measured
startup and health-check durations within the existing timeouts. Do not delete
sourceless upstream modules or claim cache absence from Dockerfile settings alone.
Historical compiled-file differences remain unresolved in their original images;
new build identities require new qualification.
