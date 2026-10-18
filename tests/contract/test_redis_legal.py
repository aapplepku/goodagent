"""Bind the Redis image copy to exact, offline-verifiable upstream legal bytes."""

import hashlib
import json
import shlex
from pathlib import Path

import pytest
from scripts import verify_release_legal as legal
from scripts.export_public_source import inspect_text, omission

ROOT = Path(__file__).resolve().parents[2]
COLLECTION = ROOT / "security/third-party/redis-7.4.11"
COMMIT = "aaf0ce63b3239f4b51f86ca1da8711b055721993"
ARCHIVE_SHA = "e973da69febfea096ab94690b44bf976482788a1b5e070df373b4f27697d57d4"
BASE_IMAGE = (
    "redis:7-alpine@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499"
)
UPSTREAM_HASHES = {
    "LICENSE.txt": "abffee3703161c0a6a0cd7f635b2c1ebb3b81bd199e9d18ea89652d678ae4287",
    "deps/fpconv/LICENSE.txt": "c9bff75738922193e67fa726fa225535870d2aa1059f91452c411736284ad566",
    "deps/hdr_histogram/COPYING.txt": (
        "a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499"
    ),
    "deps/hdr_histogram/LICENSE.txt": (
        "c124afa369aae960fa33f6944c82e161e482f2e998d6f07b37ae2c018f3c6c69"
    ),
    "deps/hiredis/COPYING.txt": "dca05ce8fc87a8261783b4aed0deef8becc9350b6aa770bc714d0c1833b896eb",
    "deps/jemalloc/COPYING.txt": "94aa2caa98c25d942f58b956c71dba6a99ff98fc3a31cbc669fe2a4cd0268b53",
    "deps/linenoise/linenoise.h.txt": (
        "a4e9aed50c78edf16fb3d7203e519c7ca104bd207f5131812d70724ecc26270b"
    ),
    "deps/lua/COPYRIGHT": "ee5e3e82af1e1b543c4f216e399d7c8cfee797711913f349e385101c4ae60a79",
    "deps/lua/src/lua_bit.c.txt": (
        "78e10247b33d0db026cbe906d19b4bd3636840f195a63e93ce08c5dee9fb578a"
    ),
    "deps/lua/src/lua_cjson.c.txt": (
        "20bcf34ee652800d41d769847022315d2e04beffb5c3070b8321f0e7f69d0054"
    ),
    "deps/lua/src/lua_cmsgpack.c.txt": (
        "0d2fd82fb47fc247a0e6f0a287f5429e81b7eb6735665e8d851bfb109961640d"
    ),
    "deps/lua/src/lua_struct.c.txt": (
        "57bc18e91a747a846ba76c070d9213452283c0ed9e652861ee7fabf87d590878"
    ),
    "src/version.h.txt": "9fa5ed92da961ec8030876760e89881670ebd2370add4f77ae582eaabb103a24",
}
UPSTREAM_PATH_OVERRIDES = {
    "deps/hiredis/COPYING.txt": "deps/hiredis/COPYING",
    "deps/jemalloc/COPYING.txt": "deps/jemalloc/COPYING",
    "deps/linenoise/linenoise.h.txt": "deps/linenoise/linenoise.h",
    "deps/lua/src/lua_bit.c.txt": "deps/lua/src/lua_bit.c",
    "deps/lua/src/lua_cjson.c.txt": "deps/lua/src/lua_cjson.c",
    "deps/lua/src/lua_cmsgpack.c.txt": "deps/lua/src/lua_cmsgpack.c",
    "deps/lua/src/lua_struct.c.txt": "deps/lua/src/lua_struct.c",
    "src/version.h.txt": "src/version.h",
}


def test_vendored_redis_collection_matches_verified_tag_and_bytes() -> None:
    manifest = json.loads((COLLECTION / "manifest.json").read_bytes())
    assert manifest["version"] == legal.REDIS_VERSION == "7.4.11"
    assert manifest["license"] == legal.REDIS_LICENSE == "RSAL-2.0 OR SSPL-1.0"
    assert manifest["base_image"] == BASE_IMAGE
    assert manifest["source"] == {
        "repository": "https://github.com/redis/redis",
        "tag": "7.4.11",
        "commit": COMMIT,
        "archive_url": "https://github.com/redis/redis/archive/refs/tags/7.4.11.tar.gz",
        "archive_sha256": ARCHIVE_SHA,
        "raw_file_base_url": f"https://raw.githubusercontent.com/redis/redis/{COMMIT}/",
    }
    assert manifest["files"] == UPSTREAM_HASHES
    assert manifest["upstream_path_overrides"] == UPSTREAM_PATH_OVERRIDES
    actual = {}
    for path in COLLECTION.rglob("*"):
        assert not path.is_symlink()
        if path.is_file():
            actual[path.relative_to(COLLECTION).as_posix()] = path.read_bytes()
    assert set(actual) == set(UPSTREAM_HASHES) | {"README.md", "manifest.json"}
    for name, expected in UPSTREAM_HASHES.items():
        assert hashlib.sha256(actual[name]).hexdigest() == expected
    assert actual["src/version.h.txt"] == (
        b'#define REDIS_VERSION "7.4.11"\n#define REDIS_VERSION_NUM 0x0007040b\n'
    )
    assert b"Redis Source Available License 2.0" in actual["LICENSE.txt"]
    assert b"Server Side Public License" in actual["LICENSE.txt"]
    assert actual["LICENSE.txt"] != (ROOT / "LICENSE").read_bytes()
    readme = actual["README.md"].decode()
    assert COMMIT in readme and ARCHIVE_SHA in readme
    for name, expected in UPSTREAM_HASHES.items():
        upstream = UPSTREAM_PATH_OVERRIDES.get(name, name)
        assert f"{manifest['source']['raw_file_base_url']}{upstream}" in readme
        assert expected in readme


def test_redis_dockerfile_copies_reviewed_bytes_without_relicensing() -> None:
    instructions = [
        shlex.split(line)
        for line in (ROOT / legal.IMAGE_DOCKERFILES["redis"]).read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert instructions[0] == ["FROM", BASE_IMAGE]
    assert [line for line in instructions if line[0] == "COPY"] == [
        ["COPY", f"{legal.REDIS_NOTICES}/", f"{legal.REDIS_IMAGE_NOTICES}/"]
    ]
    assert ["RUN", "apk", "upgrade", "--no-cache"] in instructions
    assert instructions[-1] == ["USER", "redis"]
    assert not any("Apache-2.0" in item for line in instructions for item in line)
    config = (ROOT / "docker-compose.yml").read_text()
    assert "dockerfile: infra/docker/redis/Dockerfile" in config


def test_redis_legal_collection_survives_public_export() -> None:
    for path in COLLECTION.rglob("*"):
        if path.is_file():
            relative = path.relative_to(ROOT).as_posix()
            assert omission(relative) is None, relative
            inspect_text(path.read_bytes(), relative, check_paths=True)


@pytest.mark.parametrize(
    ("name", "missing_or_changed"),
    [("LICENSE.txt", None)]
    + [(name, problem) for name in sorted(UPSTREAM_HASHES) for problem in ("missing", "changed")],
)
def test_real_redis_collection_is_enforced_in_image(
    monkeypatch: pytest.MonkeyPatch, name: str, missing_or_changed: str | None
) -> None:
    monkeypatch.chdir(ROOT)
    copied = {path: (COLLECTION / path).read_bytes() for path in UPSTREAM_HASHES}
    if missing_or_changed == "missing":
        del copied[name]
    elif missing_or_changed == "changed":
        copied[name] += b"changed"

    def container_files(image: str, directory: str) -> dict[str, bytes]:
        assert image == "fixture-image"
        assert directory == "/usr/share/doc/redis"
        return copied

    monkeypatch.setattr(legal, "container_files", container_files)
    info = {"Id": "fixture-image", "Config": {"Env": ["REDIS_VERSION=7.4.11"]}}
    if missing_or_changed is None:
        assert legal.redis_notices(info) == copied
    else:
        with pytest.raises(ValueError, match="upstream notice missing or changed"):
            legal.redis_notices(info)
