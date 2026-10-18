"""Offline verifier contracts: all Docker and native model execution is mocked."""

import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from scripts import verify_learned_search_runtime as verifier

IMAGE = "sha256:" + "a" * 64
CONFIG = "sha256:" + "b" * 64
CONTAINER = "c" * 64


def test_inspect_template_handles_images_without_declared_volumes() -> None:
    # Docker omits this key for the default image; direct field access fails.
    assert '{{json (index .Config "Volumes")}}' in verifier.IMAGE_FORMAT
    assert ".Config.Volumes" not in verifier.IMAGE_FORMAT


def payload() -> dict[str, Any]:
    return {
        "provider": verifier.PROVIDER,
        "model": verifier.MODEL,
        "model_sha256": verifier.MODEL_HASHES,
        "native_versions": verifier.VERSIONS,
        "execution_providers": ["CPUExecutionProvider"],
        "device": "CPU",
        "storage": "postgresql-and-remote-qdrant",
        "telemetry_opt_out": "1",
        "uid": 10001,
        "python_sqlite_connections": 0,
        "dimensions": 384,
        "query_count": 5,
        "document_count": 17,
        "vectors_checked": 39,
        "norm_min": 1.0,
        "norm_max": 1.0,
        "repeat_max_delta": 0.0,
        "batch_max_delta": 0.0,
        "query_document_max_delta": 0.0,
        "related_cosine": 0.8,
        "unrelated_cosine": 0.1,
        "cold_seconds": 1.0,
        "peak_rss_kib": 100000,
        "query_seconds": [0.1] * 5,
        "python": "3.12.11",
    }


@pytest.fixture(autouse=True)
def no_real_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("real subprocess forbidden in verifier tests")

    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.fixture
def models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "public-model"
    directory.mkdir()
    hashes = {}
    for name in verifier.MODEL_HASHES:
        content = ("synthetic public fixture: " + name).encode()
        (directory / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(verifier, "MODEL_HASHES", hashes)
    return directory


class FakeDocker:
    def __init__(self, scenario: str = "success") -> None:
        self.scenario = scenario
        self.commands: list[list[str]] = []
        self.processes: list[Any] = []
        self.name = ""
        self.nonce = ""
        self.inspections = 0

    def popen(self, command: list[str], **kwargs: Any) -> Any:
        self.commands.append(command)
        assert kwargs["start_new_session"] is True
        assert kwargs["preexec_fn"] is verifier.limit_output_files
        process = SimpleNamespace(returncode=None, kill=Mock(), wait=Mock())
        self.processes.append(process)

        def communicate(input: bytes | None, timeout: float) -> None:
            assert 0 < timeout <= 180
            code, out, err = 0, "", ""
            interrupt = False
            if command[1:3] == ["image", "inspect"]:
                identity = (
                    CONFIG if self.scenario == "unmapped" and command[-1] == CONFIG else IMAGE
                )
                out = json.dumps(
                    {"Id": identity, "Architecture": "arm64", "Os": "linux", "Volumes": None}
                )
                if self.scenario == "image-failure":
                    code, err = 1, "image inspection failed"
            elif command[1] == "create":
                self.name = command[command.index("--name") + 1]
                self.nonce = command[command.index("--label") + 1].split("=", 1)[1]
                out = CONTAINER
                if self.scenario == "create-timeout":
                    interrupt = True
            elif command[1:3] == ["container", "inspect"]:
                self.inspections += 1
                info = {
                    "Id": CONTAINER,
                    "Name": "/" + self.name,
                    "Owner": self.nonce,
                    "Image": CONFIG if self.scenario in {"mapped", "unmapped"} else IMAGE,
                    "RequestedImage": IMAGE,
                }
                if self.inspections > 1:
                    for field in ("Id", "Name", "Owner", "Image", "RequestedImage"):
                        if self.scenario == "mismatch-" + field:
                            info[field] = "different"
                    if self.scenario == "inspect-failure":
                        code, err = 1, "daemon unavailable"
                    if self.scenario == "inspect-timeout":
                        interrupt = True
                out = json.dumps(info)
            elif command[1] == "start":
                assert input == Path(verifier.__file__).read_bytes()
                out = json.dumps(payload())
                if self.scenario == "bad-payload":
                    out = out.replace('"uid": 10001', '"uid": 0')
                elif self.scenario == "malformed-payload":
                    out = "partial JSON"
                elif self.scenario == "nonzero":
                    code, out, err = 9, "partial output", "native failure"
                elif self.scenario in {"timeout", "interruption", "sigterm"}:
                    interrupt = True
                elif self.scenario == "output-limit":
                    out = "x" * verifier.OUTPUT_LIMIT
            elif command[1] == "rm":
                assert command[-1] == CONTAINER
                if self.scenario == "remove-failure":
                    code, err = 1, "remove failed"
            elif command[1:3] == ["container", "ls"]:
                assert f"id={CONTAINER}" in command
                if self.scenario == "still-present":
                    out = CONTAINER
                elif self.scenario == "list-failure":
                    code, err = 1, "daemon unavailable"
            else:
                pytest.fail(f"unexpected Docker command: {command}")
            if interrupt:
                kwargs["stdout"].write(b"partial\xffstdout")
                kwargs["stderr"].write(b"partial stderr")
                if self.scenario == "interruption":
                    raise KeyboardInterrupt("test interrupt")
                if self.scenario == "sigterm":
                    handler = signal.getsignal(signal.SIGTERM)
                    assert callable(handler)
                    handler(signal.SIGTERM, None)
                raise subprocess.TimeoutExpired(command, timeout)
            kwargs["stdout"].write(out.encode())
            kwargs["stderr"].write(err.encode())
            process.returncode = code

        process.communicate = communicate
        process.kill.side_effect = lambda: setattr(process, "returncode", -9)
        return process


def run_attempt(
    monkeypatch: pytest.MonkeyPatch, models: Path, output: Path, scenario: str = "success"
) -> tuple[FakeDocker, dict[str, Any]]:
    docker = FakeDocker(scenario)
    monkeypatch.setattr(subprocess, "Popen", docker.popen)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify",
            "--image",
            "example:mutable",
            "--model-directory",
            str(models),
            "--output",
            str(output),
        ],
    )
    if scenario in {"success", "mapped"}:
        verifier.main()
    else:
        with pytest.raises(SystemExit, match="evidence and cleanup outcome retained"):
            verifier.main()
    return docker, json.loads(output.read_text())


def test_success_pins_image_and_isolates_only_verified_public_bytes(
    monkeypatch: pytest.MonkeyPatch, models: Path, tmp_path: Path
) -> None:
    docker, report = run_attempt(monkeypatch, models, tmp_path / "attempt.json")
    create = next(c for c in docker.commands if c[1] == "create")
    assert create[-4:] == ["python", IMAGE, "-", "--probe"]
    for key, value in {
        "--pull": "never",
        "--network": "none",
        "--user": "10001:10001",
        "--memory": "1g",
        "--memory-swap": "1g",
        "--cpus": "2",
        "--pids-limit": "128",
        "--cap-drop": "ALL",
        "--security-opt": "no-new-privileges",
        "--ipc": "none",
    }.items():
        assert create[create.index(key) + 1] == value
    assert "--read-only" in create and "--rm" not in create
    assert create.count("--mount") == 1
    mount = create[create.index("--mount") + 1]
    assert mount.endswith(",dst=/models,readonly") and str(models) not in mount
    staged = Path(mount.split("src=", 1)[1].split(",", 1)[0])
    assert staged.parent == (tmp_path / "attempt.json.files").resolve()
    assert not staged.exists()
    assert report["status"] == "passed" and report["cleanup"]["ok"]
    assert report["image_sha256"] == IMAGE[7:]
    assert (
        report["probe_sha256"] == hashlib.sha256(Path(verifier.__file__).read_bytes()).hexdigest()
    )
    assert report["model_sha256"] == verifier.MODEL_HASHES


@pytest.mark.parametrize(
    "scenario",
    [
        "timeout",
        "interruption",
        "sigterm",
        "create-timeout",
        "nonzero",
        "bad-payload",
        "malformed-payload",
        "output-limit",
    ],
)
def test_failures_retain_output_and_remove_only_owned_container(
    monkeypatch: pytest.MonkeyPatch, models: Path, tmp_path: Path, scenario: str
) -> None:
    docker, report = run_attempt(monkeypatch, models, tmp_path / "attempt.json", scenario)
    assert report["status"] != "passed"
    assert report["cleanup"] == {"ok": True, "removed_container_id": CONTAINER}
    assert [c for c in docker.commands if c[1] == "rm"] == [["docker", "rm", "--force", CONTAINER]]
    if scenario in {"timeout", "interruption", "sigterm", "create-timeout"}:
        record = next(r for r in report["commands"] if "error" in r)
        assert Path(record["stdout_file"]).read_bytes() == b"partial\xffstdout"
        assert Path(record["stderr_file"]).read_bytes() == b"partial stderr"
        assert record["stdout_sha256"] == hashlib.sha256(b"partial\xffstdout").hexdigest()
        assert any(p.kill.called and p.wait.called for p in docker.processes)
    elif scenario == "nonzero":
        assert any(r.get("stderr") == "native failure" for r in report["commands"])
    elif scenario == "output-limit":
        assert any(r.get("output_limit_exceeded") for r in report["commands"])


@pytest.mark.parametrize(
    "scenario",
    [
        "mismatch-Id",
        "mismatch-Name",
        "mismatch-Owner",
        "mismatch-Image",
        "mismatch-RequestedImage",
        "inspect-failure",
        "inspect-timeout",
        "unmapped",
    ],
)
def test_uncertain_ownership_or_image_never_removes_a_container(
    monkeypatch: pytest.MonkeyPatch, models: Path, tmp_path: Path, scenario: str
) -> None:
    docker, report = run_attempt(monkeypatch, models, tmp_path / "attempt.json", scenario)
    assert report["status"] == "failed" and report["cleanup"]["ok"] is False
    assert not any(c[1] == "rm" for c in docker.commands)


@pytest.mark.parametrize("scenario", ["remove-failure", "still-present", "list-failure"])
def test_cleanup_must_be_confirmed_even_after_successful_probe(
    monkeypatch: pytest.MonkeyPatch, models: Path, tmp_path: Path, scenario: str
) -> None:
    _, report = run_attempt(monkeypatch, models, tmp_path / "attempt.json", scenario)
    assert report["payload"]["uid"] == 10001
    assert report["status"] == "failed" and report["cleanup"]["ok"] is False


def test_manifest_config_mapping_requires_exact_resolved_image(
    monkeypatch: pytest.MonkeyPatch, models: Path, tmp_path: Path
) -> None:
    docker, report = run_attempt(monkeypatch, models, tmp_path / "attempt.json", "mapped")
    assert report["container_image_id"] == CONFIG and report["image_id"] == IMAGE
    assert (
        len([c for c in docker.commands if c[1:3] == ["image", "inspect"] and c[-1] == CONFIG]) == 2
    )


def test_image_inspection_failure_is_retained_before_creation(
    monkeypatch: pytest.MonkeyPatch, models: Path, tmp_path: Path
) -> None:
    docker, report = run_attempt(monkeypatch, models, tmp_path / "attempt.json", "image-failure")
    assert len(docker.commands) == 1
    assert report["cleanup"] == {"ok": True, "not_created": True}


def test_evidence_is_exclusive_even_after_failed_attempt(
    monkeypatch: pytest.MonkeyPatch, models: Path, tmp_path: Path
) -> None:
    output = tmp_path / "attempt.json"
    docker, _ = run_attempt(monkeypatch, models, output, "nonzero")
    evidence = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    count = len(docker.commands)
    with pytest.raises(SystemExit, match="Refusing to replace"):
        verifier.main()
    assert len(docker.commands) == count
    assert all(p.read_bytes() == content for p, content in evidence.items())


@pytest.mark.parametrize("kind", ["extra", "symlink", "fifo", "modified", "directory"])
def test_model_allowlist_rejects_nonpublic_or_unpinned_files(models: Path, kind: str) -> None:
    target = models / "model.onnx"
    if kind == "extra":
        (models / "private.txt").write_text("must not mount")
    elif kind == "modified":
        target.write_text("changed")
    else:
        target.unlink()
        if kind == "symlink":
            target.symlink_to(models / "tokenizer.json")
        elif kind == "fifo":
            os.mkfifo(target)
        else:
            target.mkdir()
    with pytest.raises((ValueError, OSError)):
        verifier.verified_models(models)


def test_snapshot_contains_only_verified_bytes(models: Path, tmp_path: Path) -> None:
    destination = tmp_path / "snapshot"
    destination.mkdir()
    assert verifier.verified_models(models, destination) == verifier.MODEL_HASHES
    assert {p.name for p in destination.iterdir()} == set(verifier.MODEL_HASHES)
    for name in verifier.MODEL_HASHES:
        assert (destination / name).read_bytes() == (models / name).read_bytes()


@pytest.mark.parametrize("value", ["29", "601", "0", "-1"])
def test_timeout_cannot_disable_parent_deadline(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        verifier.timeout_seconds(value)


def test_timeout_endpoints_and_child_output_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    assert verifier.timeout_seconds("30") == 30
    assert verifier.timeout_seconds("600") == 600
    limit = Mock()
    monkeypatch.setattr(resource, "setrlimit", limit)
    verifier.limit_output_files()
    limit.assert_called_once_with(resource.RLIMIT_FSIZE, (verifier.OUTPUT_LIMIT,) * 2)


@pytest.mark.parametrize(
    "field,value",
    [
        ("uid", 0),
        ("uid", "10001"),
        ("provider", "HashEmbeddingProvider"),
        ("model", "different"),
        ("model_sha256", {}),
        ("native_versions", {}),
        ("execution_providers", ["CUDAExecutionProvider"]),
        ("device", "GPU"),
        ("storage", "sqlite"),
        ("python_sqlite_connections", False),
        ("telemetry_opt_out", None),
        ("dimensions", 383),
        ("document_count", 16),
        ("vectors_checked", 38),
        ("norm_min", 0.0),
        ("norm_max", float("nan")),
        ("batch_max_delta", 0.01),
        ("repeat_max_delta", float("inf")),
        ("query_document_max_delta", -1.0),
        ("related_cosine", 0.15),
        ("query_seconds", [float("nan")] * 5),
    ],
)
def test_outer_payload_fails_closed(field: str, value: Any) -> None:
    data = payload()
    verifier.validate_payload(data)
    data[field] = value
    with pytest.raises(ValueError):
        verifier.validate_payload(data)


@pytest.mark.parametrize(
    "vector",
    [[0.0] * 384, [1.0] * 384, [float("nan")] * 384, [float("inf")] * 384, [1.0] + [0.0] * 382],
)
def test_vector_validation_rejects_invalid_values(vector: list[float]) -> None:
    with pytest.raises(ValueError):
        verifier.vector_norm(vector)


async def test_probe_exercises_mixed_batch_and_all_singletons() -> None:
    def embed(text: str) -> list[float]:
        return ([0.0, 1.0] if text == verifier.DOCUMENTS[2] else [1.0, 0.0]) + [0.0] * 382

    provider = SimpleNamespace(
        embed_query=AsyncMock(side_effect=embed),
        embed_documents=AsyncMock(side_effect=lambda texts: [embed(t) for t in texts]),
    )
    checks = await verifier.check_embeddings(provider)
    assert checks["vectors_checked"] == 39
    assert checks["related_cosine"] > checks["unrelated_cosine"]
    assert provider.embed_query.await_count == 5
    assert [len(c.args[0]) for c in provider.embed_documents.call_args_list] == [17] + [1] * 17
    assert len({len(t) for t in verifier.DOCUMENTS}) > 2


@pytest.mark.parametrize("fault", ["batch", "repeat", "semantics"])
async def test_probe_rejects_inconsistent_or_degenerate_encoder(fault: str) -> None:
    count = 0

    def query(text: str) -> list[float]:
        nonlocal count
        count += 1
        return ([0.0, 1.0] if fault == "repeat" and count > 1 else [1.0, 0.0]) + [0.0] * 382

    def documents(texts: list[str]) -> list[list[float]]:
        return [
            (
                [0.0, 1.0]
                if (fault == "batch" and len(texts) == 17)
                or (fault != "semantics" and t == verifier.DOCUMENTS[2])
                else [1.0, 0.0]
            )
            + [0.0] * 382
            for t in texts
        ]

    with pytest.raises(ValueError):
        await verifier.check_embeddings(
            SimpleNamespace(
                embed_query=AsyncMock(side_effect=query),
                embed_documents=AsyncMock(side_effect=documents),
            )
        )


@pytest.mark.parametrize("failure", ["database", "client", "service", "client-close"])
async def test_construction_and_close_failures_release_owned_resources(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import importlib.metadata

    from open_commerce.persistence import db, runtime_db
    from open_commerce.search import durable

    engine = SimpleNamespace(dispose=AsyncMock())
    database = SimpleNamespace(close=AsyncMock())
    client = SimpleNamespace(close=AsyncMock())
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(__version__="1.29.0"))
    monkeypatch.setitem(sys.modules, "tokenizers", SimpleNamespace(__version__="0.23.2"))
    monkeypatch.setattr(importlib.metadata, "version", lambda name: verifier.VERSIONS[name])
    monkeypatch.setattr(verifier, "verified_models", lambda _: verifier.MODEL_HASHES)
    monkeypatch.setattr(db, "create_engine", lambda _: engine)
    monkeypatch.setattr(
        runtime_db,
        "RuntimeDatabase",
        Mock(
            side_effect=ValueError("database") if failure == "database" else None,
            return_value=database,
        ),
    )
    monkeypatch.setattr(
        "qdrant_client.AsyncQdrantClient",
        Mock(
            side_effect=ValueError("client") if failure == "client" else None, return_value=client
        ),
    )
    monkeypatch.setattr(durable, "DurableSearchService", Mock(side_effect=ValueError("service")))
    if failure == "client-close":
        client.close.side_effect = ValueError("client-close")
    with pytest.raises(ValueError, match=failure):
        await verifier.probe()
    if failure == "database":
        engine.dispose.assert_awaited_once()
    else:
        database.close.assert_awaited_once()
    if failure in {"service", "client-close"}:
        client.close.assert_awaited_once()
