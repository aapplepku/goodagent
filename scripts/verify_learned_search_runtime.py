"""Retain bounded, exact-image offline encoder evidence; never build or fetch images."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import resource
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2@dfa9feb5cece5be2cc8fc23a3cf1f32473a9d56f"
    ":onnx-fp32-mean-l2-v1"
)
MODEL_HASHES = {
    "model.onnx": "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452",
    "tokenizer.json": "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
}
PROVIDER = "open_commerce.search.learned_embeddings.MiniLMEmbeddingProvider"
VERSIONS = {"onnxruntime": "1.29.0", "tokenizers": "0.23.2"}
OWNER_LABEL = "org.opencommerce.learned-runtime-attempt"
OUTPUT_LIMIT = 1024 * 1024
QUERY = "waterproof hiking boots"
DOCUMENTS = [
    QUERY,
    "Waterproof hiking boots for walking on wet mountain trails.",
    "Ceramic dinner plates and porcelain cups for the kitchen table.",
    "Boots",
    "Lightweight hiking footwear with ankle support and a waterproof lining.",
    "Red cotton shirt",
    "A stainless steel saucepan with a glass lid and a handle for everyday cooking.",
    "Socks",
    "A compact travel backpack with separate pockets for maps and water bottles.",
    "Desk lamp",
    "A soft wool blanket for a sofa on cold evenings.",
    "Trail shoes",
    "Durable hiking boots. " * 40,
    "Notebook",
    "An adjustable office chair with armrests and a padded seat.",
    "Garden gloves",
    QUERY,
]
IMAGE_FORMAT = (
    '{"Id":{{json .Id}},"Architecture":{{json .Architecture}},'
    '"Os":{{json .Os}},"Volumes":{{json (index .Config "Volumes")}}}'
)
CONTAINER_FORMAT = (
    '{"Id":{{json .Id}},"Name":{{json .Name}},"Image":{{json .Image}},'
    '"RequestedImage":{{json .Config.Image}},'
    '"Owner":{{json (index .Config.Labels "' + OWNER_LABEL + '")}}}'
)
LIMITATIONS = (
    "Python SQLite constructors are guarded, not native syscalls. Telemetry opt-out is "
    "configuration evidence, not proof of absent native telemetry. Offline construction "
    "does not test PostgreSQL/Qdrant connectivity. The fixed cosine comparison is not "
    "general relevance evaluation. Local timings are not production sizing. A killed host "
    "or unavailable Docker daemon can prevent cleanup; incomplete cleanup fails verification."
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verified_models(directory: Path, destination: Path | None = None) -> dict[str, str]:
    """Read only pinned public regular files; optionally stage their verified bytes."""
    require(not directory.is_symlink() and directory.is_dir(), "invalid model directory")
    require({p.name for p in directory.iterdir()} == set(MODEL_HASHES), "unexpected model files")
    hashes = {}
    for name, expected in MODEL_HASHES.items():
        descriptor = os.open(directory / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as source:
            metadata = os.fstat(source.fileno())
            require(
                stat.S_ISREG(metadata.st_mode) and 0 < metadata.st_size <= 100_000_000,
                "invalid model file",
            )
            content = source.read(100_000_001)
        hashes[name] = hashlib.sha256(content).hexdigest()
        require(hashes[name] == expected, "pinned model checksum mismatch")
        if destination is not None:
            with (destination / name).open("xb") as target:
                target.write(content)
            (destination / name).chmod(0o644)
    return hashes


def vector_norm(vector: Any) -> float:
    require(isinstance(vector, list) and len(vector) == 384, "invalid vector dimensions")
    require(
        all(type(v) in (float, int) and math.isfinite(v) for v in vector),
        "nonfinite vector",
    )
    norm = math.sqrt(sum(v * v for v in vector))
    require(math.isfinite(norm) and norm > 1e-9 and abs(norm - 1) <= 1e-4, "invalid unit norm")
    return norm


async def check_embeddings(provider: Any) -> dict[str, Any]:
    """Exercise repeated queries and every singleton against a mixed 17-document batch."""
    queries, times = [], []
    for _ in range(5):
        start = time.perf_counter()
        queries.append(await provider.embed_query(QUERY))
        times.append(time.perf_counter() - start)
    batch = await provider.embed_documents(DOCUMENTS)
    require(len(batch) == 17, "missing batch vectors")
    singletons = []
    for document in DOCUMENTS:
        result = await provider.embed_documents([document])
        require(len(result) == 1, "missing singleton vector")
        singletons.append(result[0])
    norms = [vector_norm(v) for v in [*queries, *batch, *singletons]]
    repeat_delta = max(abs(a - b) for v in queries[1:] for a, b in zip(queries[0], v, strict=True))
    batch_delta = max(
        abs(a - b)
        for singleton, padded in zip(singletons, batch, strict=True)
        for a, b in zip(singleton, padded, strict=True)
    )
    query_delta = max(abs(a - b) for a, b in zip(queries[0], batch[0], strict=True))
    related = sum(a * b for a, b in zip(queries[0], batch[1], strict=True))
    unrelated = sum(a * b for a, b in zip(queries[0], batch[2], strict=True))
    require(max(repeat_delta, batch_delta, query_delta) <= 1e-5, "inconsistent embeddings")
    require(related > unrelated + 0.1, "fixed related/unrelated cosine check failed")
    return {
        "dimensions": 384,
        "query_count": 5,
        "document_count": 17,
        "vectors_checked": len(norms),
        "norm_min": min(norms),
        "norm_max": max(norms),
        "repeat_max_delta": repeat_delta,
        "batch_max_delta": batch_delta,
        "query_document_max_delta": query_delta,
        "related_cosine": related,
        "unrelated_cosine": unrelated,
        "query_seconds": times,
    }


async def probe() -> dict[str, Any]:
    """Run inside the isolated image; construction never connects to backing services."""
    import importlib.metadata
    from unittest.mock import patch

    import onnxruntime
    import tokenizers
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.async_qdrant_remote import AsyncQdrantRemote
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from open_commerce.config import Settings
    from open_commerce.persistence.db import create_engine
    from open_commerce.persistence.runtime_db import RuntimeDatabase
    from open_commerce.search.durable import DurableSearchService
    from open_commerce.search.learned_embeddings import MiniLMEmbeddingProvider

    hashes = verified_models(Path("/models"))
    versions = {name: importlib.metadata.version(name) for name in VERSIONS}
    require(versions == VERSIONS, "native distribution version mismatch")
    require(
        onnxruntime.__version__ == VERSIONS["onnxruntime"]
        and tokenizers.__version__ == VERSIONS["tokenizers"],
        "native module version mismatch",
    )
    start = time.perf_counter()
    with (
        patch("sqlite3.connect", side_effect=AssertionError("SQLite forbidden")),
        patch("sqlite3.dbapi2.connect", side_effect=AssertionError("SQLite forbidden")),
    ):
        settings = Settings(
            _env_file=None,
            runtime_profile="legacy_demo",
            database_url="postgresql+asyncpg://probe:probe@postgres:5432/probe",
            search_embedding_backend="minilm",
            search_model_directory=Path("/models"),
            qdrant_url="http://qdrant:6333",
        )
        engine = create_engine(settings)
        database = None
        try:
            database = RuntimeDatabase(
                settings, sessions=async_sessionmaker(engine, expire_on_commit=False)
            )
            client = None
            try:
                client = AsyncQdrantClient(url=settings.qdrant_url, check_compatibility=False)
                search = DurableSearchService(database, client=client)
                provider = search.embedding_provider
                if not isinstance(provider, MiniLMEmbeddingProvider):
                    raise ValueError("unexpected embedding provider")
                require(type(provider) is MiniLMEmbeddingProvider, "unexpected embedding provider")
                require(provider.model_id == MODEL, "unexpected model identity")
                require(provider.dimensions == 384, "unexpected provider dimensions")
                require(type(client._client) is AsyncQdrantRemote, "unexpected storage client")
                async with database.sessions() as session:
                    require(session.bind is engine, "unexpected session engine")
                    require(engine.dialect.name == "postgresql", "unexpected database")
                execution_providers = provider.session.get_providers()
                require(
                    execution_providers == ["CPUExecutionProvider"], "unexpected execution provider"
                )
                require(onnxruntime.get_device() == "CPU", "unexpected native device")
                cold = time.perf_counter() - start
                checks = await check_embeddings(provider)
                payload = {
                    **checks,
                    "provider": f"{type(provider).__module__}.{type(provider).__name__}",
                    "model": provider.model_id,
                    "model_sha256": hashes,
                    "native_versions": versions,
                    "execution_providers": execution_providers,
                    "device": onnxruntime.get_device(),
                    "cold_seconds": cold,
                    "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    "telemetry_opt_out": os.environ.get("ORT_DISABLE_TELEMETRY"),
                    "python_sqlite_connections": 0,
                    "storage": "postgresql-and-remote-qdrant",
                    "uid": os.getuid(),
                    "python": sys.version.split()[0],
                }
            finally:
                if client is not None:
                    await client.close()
        finally:
            if database is not None:
                await database.close()
            else:
                await engine.dispose()
    validate_payload(payload)
    return payload


def validate_payload(data: Any) -> None:
    """Independently reject missing, nonfinite or inconsistent outer evidence."""
    require(isinstance(data, dict), "probe payload must be an object")
    expected = {
        "provider": PROVIDER,
        "model": MODEL,
        "model_sha256": MODEL_HASHES,
        "native_versions": VERSIONS,
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
    }
    for key, value in expected.items():
        require(type(data.get(key)) is type(value) and data[key] == value, f"invalid {key}")
    for key, low, high in [
        ("norm_min", 1 - 1e-4, 1 + 1e-4),
        ("norm_max", 1 - 1e-4, 1 + 1e-4),
        ("repeat_max_delta", 0, 1e-5),
        ("batch_max_delta", 0, 1e-5),
        ("query_document_max_delta", 0, 1e-5),
        ("related_cosine", -1.001, 1.001),
        ("unrelated_cosine", -1.001, 1.001),
        ("cold_seconds", 0, 600),
        ("peak_rss_kib", 1, 1024 * 1024),
    ]:
        measurement = data.get(key)
        require(
            type(measurement) in (float, int)
            and math.isfinite(measurement)
            and low <= measurement <= high,
            f"invalid {key}",
        )
    require(data["norm_min"] <= data["norm_max"], "inverted norm bounds")
    require(data["related_cosine"] > data["unrelated_cosine"] + 0.1, "invalid cosine comparison")
    times = data.get("query_seconds")
    require(
        isinstance(times, list)
        and len(times) == 5
        and all(type(t) in (float, int) and math.isfinite(t) and 0 <= t <= 600 for t in times),
        "invalid query timings",
    )
    require(isinstance(data.get("python"), str) and bool(data["python"]), "missing Python version")


def limit_output_files() -> None:
    """Bound each Docker CLI output file in its child process, including during hangs."""
    resource.setrlimit(resource.RLIMIT_FSIZE, (OUTPUT_LIMIT, OUTPUT_LIMIT))


def run_command(
    command: list[str],
    deadline: float,
    directory: Path,
    report: dict[str, Any],
    source: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Files retain partial bytes even when communicate is interrupted or times out."""
    record: dict[str, Any] = {"command": command, "returncode": None}
    number = len(report["commands"])
    report["commands"].append(record)
    stdout, stderr = directory / f"{number:02d}.stdout", directory / f"{number:02d}.stderr"
    process = None
    try:
        with stdout.open("xb") as out, stderr.open("xb") as err:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("verification deadline expired")
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE if source is not None else subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
                preexec_fn=limit_output_files,
            )
            try:
                process.communicate(
                    input=source.encode() if source is not None else None, timeout=remaining
                )
            except BaseException:
                process.kill()
                process.wait(timeout=5)
                raise
    except BaseException as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record["returncode"] = process.returncode if process is not None else None
        for key, path in (("stdout", stdout), ("stderr", stderr)):
            if path.exists():
                with path.open("rb") as stream:
                    content = stream.read(OUTPUT_LIMIT + 1)
                if len(content) >= OUTPUT_LIMIT:
                    record["output_limit_exceeded"] = True
                record[key] = content.decode("utf-8", errors="replace")
                record[f"{key}_file"] = str(path)
                record[f"{key}_sha256"] = hashlib.sha256(content).hexdigest()
    require(not record.get("output_limit_exceeded"), "subprocess output limit reached")
    return subprocess.CompletedProcess(
        command, process.returncode, record["stdout"], record["stderr"]
    )


def inspect_image(
    reference: str, deadline: float, directory: Path, report: dict[str, Any]
) -> dict[str, Any]:
    result = run_command(
        ["docker", "image", "inspect", "--format", IMAGE_FORMAT, reference],
        deadline,
        directory,
        report,
    )
    require(result.returncode == 0, "image inspection failed")
    info: dict[str, Any] = json.loads(result.stdout)
    require(bool(re.fullmatch(r"sha256:[0-9a-f]{64}", info.get("Id", ""))), "invalid image ID")
    require(info.get("Os") == "linux" and bool(info.get("Architecture")), "invalid image platform")
    require(info.get("Volumes") in (None, {}), "image declares additional volumes")
    return info


def inspect_owned(deadline: float, directory: Path, report: dict[str, Any]) -> str:
    result = run_command(
        ["docker", "container", "inspect", "--format", CONTAINER_FORMAT, report["container_name"]],
        deadline,
        directory,
        report,
    )
    require(result.returncode == 0, "owned container inspection failed; refusing removal")
    info = json.loads(result.stdout)
    identity = info.get("Id", "")
    require(bool(re.fullmatch(r"[0-9a-f]{64}", identity)), "invalid container ID")
    require(info.get("Name") == "/" + report["container_name"], "container name mismatch")
    require(info.get("Owner") == report["nonce"], "container ownership mismatch")
    require(info.get("RequestedImage") == report["image_id"], "requested image mismatch")
    require(report.get("container_id", identity) == identity, "created container ID mismatch")
    image = info.get("Image", "")
    require(bool(re.fullmatch(r"sha256:[0-9a-f]{64}", image)), "invalid container image")
    if image != report["image_id"]:
        # Containerd can expose distinct manifest/config IDs. Resolve the complete
        # config reference back to the inspected image; never infer a partial match.
        mapped = inspect_image(image, deadline, directory, report)
        require(mapped["Id"] == report["image_id"], "unproven image config mapping")
    report["container_image_id"] = image
    return str(identity)


def cleanup(directory: Path, report: dict[str, Any]) -> None:
    deadline = time.monotonic() + 30
    report["cleanup"] = {"ok": False}
    try:
        identity = inspect_owned(deadline, directory, report)
        result = run_command(["docker", "rm", "--force", identity], deadline, directory, report)
        require(result.returncode == 0, "owned container removal failed")
        result = run_command(
            [
                "docker",
                "container",
                "ls",
                "--all",
                "--no-trunc",
                "--filter",
                f"id={identity}",
                "--format",
                "{{.ID}}",
            ],
            deadline,
            directory,
            report,
        )
        require(
            result.returncode == 0 and not result.stdout.strip(), "container removal not confirmed"
        )
        report["cleanup"] = {"ok": True, "removed_container_id": identity}
    except Exception as exc:
        report["cleanup"]["error"] = f"{type(exc).__name__}: {exc}"


def timeout_seconds(value: str) -> int:
    result = int(value)
    if not 30 <= result <= 600:
        raise argparse.ArgumentTypeError("timeout must be between 30 and 600 seconds")
    return result


def interrupt(signum: int, frame: Any) -> None:
    raise KeyboardInterrupt(f"received signal {signum}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=timeout_seconds, default=180)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise SystemExit("Refusing to replace retained runtime evidence") from exc
    nonce = uuid4().hex
    directory = args.output.with_name(args.output.name + ".files")
    source = Path(__file__).read_text()
    report: dict[str, Any] = {
        "status": "failed",
        "started_at": datetime.now(UTC).isoformat(),
        "nonce": nonce,
        "container_name": f"oc-learned-probe-{nonce}",
        "requested_image": args.image,
        "timeout_seconds": args.timeout_seconds,
        "cleanup_grace_seconds": 30,
        "commands": [],
        "probe_source": source,
        "probe_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "limitations": LIMITATIONS,
        "cleanup": {"ok": True, "not_created": True},
    }
    previous = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    attempted_create = False
    with os.fdopen(descriptor, "w") as evidence:
        try:
            directory.mkdir(mode=0o700)
            for sig in previous:
                signal.signal(sig, interrupt)
            deadline = time.monotonic() + args.timeout_seconds
            # Docker Desktop/Colima may not share macOS's system temporary directory.
            # Keep the verified public bytes beside evidence in the shared workspace.
            with tempfile.TemporaryDirectory(
                prefix="oc-public-model-", dir=directory.resolve()
            ) as temporary:
                models = Path(temporary)
                report["model_sha256"] = verified_models(args.model_directory, models)
                models.chmod(0o755)
                require(not any(c in str(models) for c in ",\n\r"), "unsafe model mount path")
                info = inspect_image(args.image, deadline, directory, report)
                report.update(
                    image_id=info["Id"],
                    image_sha256=info["Id"][7:],
                    architecture=info["Architecture"],
                )
                command = [
                    "docker",
                    "create",
                    "--pull",
                    "never",
                    "--name",
                    report["container_name"],
                    "--label",
                    f"{OWNER_LABEL}={nonce}",
                    "--network",
                    "none",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--user",
                    "10001:10001",
                    "--memory",
                    "1g",
                    "--memory-swap",
                    "1g",
                    "--cpus",
                    "2",
                    "--pids-limit",
                    "128",
                    "--ulimit",
                    "core=0:0",
                    "--ulimit",
                    "nofile=1024:1024",
                    "--ipc",
                    "none",
                    "--interactive",
                    "--log-driver",
                    "none",
                    "--no-healthcheck",
                    "--env",
                    "PYTHONDONTWRITEBYTECODE=1",
                    "--env",
                    "ORT_DISABLE_TELEMETRY=1",
                    "--mount",
                    f"type=bind,src={models},dst=/models,readonly",
                    "--entrypoint",
                    "python",
                    info["Id"],
                    "-",
                    "--probe",
                ]
                try:
                    attempted_create = True
                    result = run_command(command, deadline, directory, report)
                    require(result.returncode == 0, "container creation failed")
                    identity = result.stdout.strip()
                    require(
                        bool(re.fullmatch(r"[0-9a-f]{64}", identity)), "invalid create response"
                    )
                    report["container_id"] = identity
                    inspect_owned(deadline, directory, report)
                    result = run_command(
                        ["docker", "start", "--attach", "--interactive", identity],
                        deadline,
                        directory,
                        report,
                        source,
                    )
                    require(result.returncode == 0, "offline learned runtime execution failed")
                    payload = json.loads(result.stdout)
                    validate_payload(payload)
                    report["payload"] = payload
                    report["status"] = "passed"
                finally:
                    # A second terminal signal must not skip ownership checks or evidence.
                    for sig in previous:
                        signal.signal(sig, signal.SIG_IGN)
                    if attempted_create:
                        cleanup(directory, report)
        except (Exception, KeyboardInterrupt) as exc:
            report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            report["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            if not report["cleanup"]["ok"]:
                report["status"] = "failed"
            report["finished_at"] = datetime.now(UTC).isoformat()
            json.dump(report, evidence, sort_keys=True, indent=2, allow_nan=False)
            evidence.write("\n")
            evidence.flush()
            os.fsync(evidence.fileno())
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    if report["status"] != "passed":
        raise SystemExit(
            "offline learned runtime verification failed; evidence and cleanup outcome retained"
        )
    print(json.dumps(report["payload"], sort_keys=True))


if __name__ == "__main__":
    if sys.argv[1:] == ["--probe"]:
        print(json.dumps(asyncio.run(probe()), sort_keys=True, allow_nan=False))
    else:
        main()
