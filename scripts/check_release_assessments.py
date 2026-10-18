"""Standalone current-artifact assessment verifier; deliberately not wired into CI.

The caller must obtain --expected-review-sha256 from a protected adoption channel,
NOT calculate it from an unreviewed submission. --expected-source-sha256 identifies
the already-built payload. Neither argument is an approval signature. A successful
check establishes byte/identity/coverage/date consistency of adopted rationale, not
its truth, human authorship, whole-program safety, or permission to publish.

Contract v1 uses the existing scan-images inventory and export_public_source source
snapshot formats. Every referenced file is relative to one immutable, public-safe
bundle. Image refs are whole files; evidence may select a typed Proof with an RFC6901
JSON pointer (not a URI fragment). Proofs answer five required questions for an exact
record and scope. Unrelated limitations remain explicit; relevant missing inputs
must be empty. All eight services are shipped runtime, so only not-applicable is
accepted. There is no accept/mitigate override, date override, or output-file write.

Every proof binds at least one observation's actual bytes and optional JSON pointer.
Selected JSON must contain nonblank observation content, not just status/claim fields;
selected failed/incomplete receipts are rejected. An empty result requires the typed
scoped-empty-result envelope, matching the proof scope and naming what was examined.
Historical documents need no global completeness field: a pointer may select the
relevant observation subtree without adopting unrelated incomplete work.
Scanner fix metadata is reconciled only with raw Trivy FixedVersion. Independently,
upstream availability is available/unavailable/unknown, with nonempty version labels
only when available. Empty scanner metadata does not establish upstream unavailability,
and an upstream fix does not establish that the shipped package contains it. Bound
fix observations support the trusted review's claim; this verifier does not prove it.

Finding hashes are SHA256(json.dumps(full_finding, sort_keys=True,
separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")), with NO
field removal. This is not the legacy normalized digest. The source digest retains
export_public_source's sorted-key, indent=2, newline-terminated files-list encoding.
Schemas can be inspected with ReviewManifest.model_json_schema(). Future integration
must define protected verifier/approval selection and collect-once artifact promotion;
private ledgers are not automatically converted or approved by this program.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import runpy
import stat
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, Never, Self, cast

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, model_validator

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_FILES = 8192
MAX_JSON_NODES = 500_000
SERVICES = {"api", "migrate", "worker", "web", "shopper", "postgres", "redis", "qdrant"}
QUESTIONS = {"advisory", "component", "reachability", "exposure", "fix"}
SCANNER = (
    "aquasec/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969"
)


class GateError(ValueError):
    """Only fixed, content-free diagnostics cross the CLI boundary."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise GateError(code)


def relative_path(value: object) -> str:
    require(isinstance(value, str), "unsafe_path")
    value = cast(str, value)
    require(
        re.fullmatch(r"[A-Za-z0-9_.@\[\]-][A-Za-z0-9_./@\[\]-]{0,511}", value) is not None
        and str(PurePosixPath(value)) == value
        and not any(part in {".", ".."} for part in value.split("/"))
        and not value.endswith("/"),
        "unsafe_path",
    )
    return value


def text(value: object) -> str:
    require(isinstance(value, str), "invalid_text")
    value = cast(str, value)
    require(bool(value.strip()) and "\x00" not in value, "invalid_text")
    return value


def utc_time(value: object) -> datetime:
    if isinstance(value, str):
        require(
            re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|\+00:00)", value)
            is not None,
            "invalid_utc_time",
        )
        value = datetime.fromisoformat(value)
    require(isinstance(value, datetime), "invalid_utc_time")
    value = cast(datetime, value)
    require(
        value.tzinfo is not None and value.utcoffset() == UTC.utcoffset(value), "invalid_utc_time"
    )
    return value.astimezone(UTC)


def true_flag(value: object) -> bool:
    require(value is True, "incomplete")
    return True


Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ImageID = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
RelativePath = Annotated[str, BeforeValidator(relative_path)]
Text = Annotated[str, BeforeValidator(text), Field(max_length=16384)]
ShortText = Annotated[str, BeforeValidator(text), Field(max_length=1024)]
Timestamp = Annotated[datetime, BeforeValidator(utc_time)]
Complete = Annotated[bool, BeforeValidator(true_flag)]
Count = Annotated[int, Field(ge=0, le=1_000_000)]
Service = Literal["api", "migrate", "worker", "web", "shopper", "postgres", "redis", "qdrant"]
Severity = Literal["UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
Purpose = Literal["advisory", "component", "reachability", "exposure", "fix"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    @model_validator(mode="before")
    @classmethod
    def literal_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and "schema_version" in value:
            require(type(value["schema_version"]) is int, "invalid_schema")
        return value


class FileRef(StrictModel):
    path: RelativePath
    sha256: Digest
    size: Annotated[int, Field(ge=0, le=MAX_FILE_BYTES)]


class Platform(StrictModel):
    os: Literal["linux"]
    architecture: Literal["arm64", "amd64"]


class ObservationScope(StrictModel):
    membership: Literal["shipped-runtime", "build", "dev", "test"]
    boundaries: Text
    exclusions: Annotated[list[ShortText], Field(max_length=64)]


class Scope(ObservationScope):
    membership: Literal["shipped-runtime"]


class RecordIdentity(StrictModel):
    service: Service
    image_id: ImageID
    image_config_id: ImageID
    platform: Platform
    scanner_image: ShortText
    scanner_version: Literal["0.74.0"]
    source_tree_sha256: Digest
    raw_scan_sha256: Digest
    sbom_sha256: Digest
    artifact: ShortText
    result_index: Count
    finding_index: Count
    target: ShortText
    result_class: Literal["os-pkgs", "lang-pkgs"]
    result_type: ShortText
    package: ShortText
    package_id: ShortText | None
    package_path: ShortText | None
    installed_version: ShortText
    vulnerability_id: ShortText
    original_severity: Literal["HIGH", "CRITICAL"]
    finding_sha256: Digest


class ObservationRef(StrictModel):
    file: FileRef
    pointer: Annotated[str, Field(max_length=2048)] | None = None


class EmptyObservation(StrictModel):
    schema_version: Literal[1]
    kind: Literal["scoped-empty-result"]
    scope: ObservationScope
    complete: Complete
    examined: Annotated[list[ShortText], Field(min_length=1, max_length=128)]
    results: Annotated[list[Any], Field(max_length=0)]


class ReusedObservations(StrictModel):
    rationale: Text
    verified_at: Timestamp
    current_source_tree_sha256: Digest
    current: Annotated[list[ObservationRef], Field(min_length=1, max_length=64)]


class Proof(StrictModel):
    schema_version: Literal[1]
    identity: RecordIdentity
    scope: Scope
    purpose: Purpose
    observed_at: Timestamp
    coverage: Literal["complete-for-question"]
    conclusion: Text
    missing_inputs: Annotated[list[ShortText], Field(max_length=0)]
    limitations: Annotated[list[ShortText], Field(max_length=64)]
    observations: Annotated[list[ObservationRef], Field(min_length=1, max_length=64)]
    reused_exact_bytes: ReusedObservations | None = None


class EvidenceRef(ObservationRef):
    purpose: Purpose


class Fix(StrictModel):
    scanner_fixed_version: ShortText | None
    scanner_fix_available: bool
    upstream_availability: Literal["available", "unavailable", "unknown"]
    upstream_fixed_versions: Annotated[list[ShortText], Field(max_length=64)]
    rationale: Text

    @model_validator(mode="after")
    def upstream_versions(self) -> Self:
        require(
            bool(self.upstream_fixed_versions) == (self.upstream_availability == "available")
            and len(self.upstream_fixed_versions) == len(set(self.upstream_fixed_versions)),
            "upstream_fix_versions",
        )
        return self


class Assessment(StrictModel):
    identity: RecordIdentity
    scope: Scope
    decision: Literal["not-applicable"]
    review_owner: ShortText
    review_method: Literal["human", "ai-assisted", "automated"]
    reviewed_at: Timestamp
    expires_at: Timestamp
    rationale: Text
    reachability: Text
    exposure: Text
    fix: Fix
    missing_inputs: Annotated[list[ShortText], Field(max_length=0)]
    limitations: Annotated[list[ShortText], Field(max_length=64)]
    evidence: Annotated[list[EvidenceRef], Field(min_length=5, max_length=64)]


class ImageArtifacts(StrictModel):
    service: Service
    scan: FileRef
    sbom: FileRef
    manifest: FileRef
    config: FileRef
    inspection: FileRef


class SourceBinding(StrictModel):
    manifest: FileRef
    directory: RelativePath
    source_tree_sha256: Digest


class ReviewManifest(StrictModel):
    schema_version: Literal[1]
    hash_format: Literal["trivy-full-finding-json-v1"]
    review_owner: ShortText
    review_method: Literal["human", "ai-assisted", "automated"]
    reviewed_at: Timestamp
    expires_at: Timestamp
    source: SourceBinding
    inventory: FileRef
    images: Annotated[list[ImageArtifacts], Field(min_length=8, max_length=8)]
    assessments: Annotated[list[Assessment], Field(max_length=10000)]
    residual_policy: Literal["retain-low-medium-unknown-without-approval"]
    limitations: Annotated[list[ShortText], Field(min_length=1, max_length=64)]


class SourceFile(StrictModel):
    path: RelativePath
    source: RelativePath
    sha256: Digest
    bytes: Annotated[int, Field(ge=0, le=MAX_FILE_BYTES)]
    mode: Annotated[int, Field(ge=0, le=0o777)]


class SourceSnapshot(StrictModel):
    schema_version: Literal[1]
    created_at: Timestamp
    purpose: Text
    provenance: Text
    files: Annotated[list[SourceFile], Field(min_length=1, max_length=4096)]
    source_tree_sha256: Digest


class InventoryRef(StrictModel):
    file: RelativePath
    sha256: Digest


class InventoryConfigRef(InventoryRef):
    archive_member: RelativePath


class IdentityInputs(StrictModel):
    manifest: InventoryRef
    config: InventoryConfigRef
    inspection: InventoryRef


class InventoryImage(StrictModel):
    service: Service
    reference: ShortText
    image_id: ImageID
    image_config_id: ImageID
    identity_inputs: IdentityInputs
    identity_match_fields: list[Literal["Architecture", "Os", "RootFS"]]
    repo_digests: Annotated[list[ShortText], Field(max_length=128)]
    architecture: Literal["arm64", "amd64"]
    user: Annotated[str, Field(max_length=1024)] | None
    scanner: ShortText
    scan: RelativePath
    sbom: RelativePath
    complete: Complete
    scan_sha256: Digest
    sbom_sha256: Digest
    counts: dict[Severity, Count]
    fix_available_count: Count
    untriaged_high_critical_count: Count


class Inventory(StrictModel):
    complete: Complete
    images: Annotated[list[InventoryImage], Field(min_length=8, max_length=8)]
    started_at: Timestamp
    completed_at: Timestamp


def strict_json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def constant(_value: str) -> Any:
        raise GateError("nonfinite_json")

    def floating(value: str) -> float:
        number = float(value)
        require(math.isfinite(number), "nonfinite_json")
        return number

    try:
        require(len(raw) <= MAX_FILE_BYTES, "file_budget")
        result = json.loads(
            raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=floating
        )
        pending = [(result, 0)]
        nodes = 0
        while pending:
            item, depth = pending.pop()
            nodes += 1
            require(nodes <= MAX_JSON_NODES and depth <= 64, "json_budget")
            if isinstance(item, dict):
                pending.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list):
                pending.extend((v, depth + 1) for v in item)
        return result
    except (UnicodeError, ValueError, RecursionError, OverflowError):
        raise GateError("invalid_json") from None


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def finding_digest(finding: dict[str, Any]) -> str:
    return digest(
        json.dumps(
            finding, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")
    )


def json_pointer(value: Any, pointer: str | None) -> Any:
    if pointer is None or pointer == "":
        return value
    require(len(pointer) <= 2048 and pointer.startswith("/"), "invalid_pointer")
    tokens = pointer[1:].split("/")
    require(len(tokens) <= 64, "pointer_budget")
    for raw in tokens:
        require(re.search(r"~(?![01])|[\x00-\x1f]", raw) is None, "invalid_pointer")
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            require(token in value, "missing_pointer")
            value = value[token]
        elif isinstance(value, list):
            require(re.fullmatch(r"0|[1-9][0-9]{0,9}", token) is not None, "invalid_pointer_index")
            index = int(token)
            require(index < len(value), "missing_pointer")
            value = value[index]
        else:
            raise GateError("missing_pointer")
    return value


class BundleReader:
    """Descriptor-relative traversal refuses symlinks, special files and aliasing."""

    def __init__(self, root: Path) -> None:
        self.fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in root.absolute().parts[1:]:
                require(part not in {".", ".."}, "unsafe_root")
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
                os.close(self.fd)
                self.fd = child
        except BaseException:
            os.close(self.fd)
            raise
        self.cache: dict[str, tuple[bytes, int]] = {}
        self.identities: dict[str, tuple[int, ...]] = {}
        self.pins: dict[str, tuple[str, int]] = {}
        self.total = 0
        self.source_memberships: dict[str, tuple[set[str], set[str]]] = {}

    def close(self) -> None:
        os.close(self.fd)

    @staticmethod
    def identity(info: os.stat_result) -> tuple[int, ...]:
        return (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_nlink,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )

    def directory(self, path: str) -> int:
        fd = os.dup(self.fd)
        try:
            for part in relative_path(path).split("/"):
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            return fd
        except BaseException:
            os.close(fd)
            raise

    def source_paths(self, path: str) -> set[str]:
        return self.source_tree_paths(path)[0]

    def source_tree_paths(self, path: str) -> tuple[set[str], set[str]]:
        found: set[str] = set()
        directories = {"."}
        entries = 0

        def walk(fd: int, prefix: str, depth: int) -> None:
            nonlocal entries
            require(depth <= 64, "source_directory_depth")
            with os.scandir(fd) as listing:
                for item in listing:
                    entries += 1
                    require(entries <= MAX_FILES, "source_directory_budget")
                    name = relative_path(prefix + item.name)
                    info = item.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        directories.add(name)
                        child = os.open(
                            item.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                        )
                        try:
                            walk(child, name + "/", depth + 1)
                        finally:
                            os.close(child)
                    else:
                        require(stat.S_ISREG(info.st_mode), "source_special_file")
                        found.add(name)

        fd = self.directory(path)
        try:
            walk(fd, "", 0)
        finally:
            os.close(fd)
        return found, directories

    def recheck(self) -> None:
        for directory, expected_members in self.source_memberships.items():
            require(
                self.source_tree_paths(directory) == expected_members,
                "source_directory_membership",
            )
        for path, expected in self.identities.items():
            parent, _, leaf = path.rpartition("/")
            fd = self.directory(parent) if parent else os.dup(self.fd)
            try:
                require(
                    self.identity(os.stat(leaf, dir_fd=fd, follow_symlinks=False)) == expected,
                    "file_changed",
                )
            finally:
                os.close(fd)

    def read(self, path: str) -> tuple[bytes, int]:
        path = relative_path(path)
        if path in self.cache:
            return self.cache[path]
        require(len(self.cache) < MAX_FILES, "file_count_budget")
        fd = os.dup(self.fd)
        try:
            parts = path.split("/")
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(leaf, "rb") as stream:
                before = os.fstat(stream.fileno())
                require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "not_regular_file")
                require(before.st_size <= MAX_FILE_BYTES, "file_budget")
                require(self.total + before.st_size <= MAX_TOTAL_BYTES, "total_byte_budget")
                raw = stream.read(before.st_size + 1)
                after = os.fstat(stream.fileno())
                named = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
                identity = self.identity(before)
                require(
                    identity == self.identity(after) == self.identity(named)
                    and len(raw) == before.st_size,
                    "file_changed",
                )
            self.total += len(raw)
            result = (raw, stat.S_IMODE(before.st_mode))
            self.cache[path] = result
            self.identities[path] = identity
            return result
        finally:
            os.close(fd)

    def bound(self, ref: FileRef) -> bytes:
        pin = (ref.sha256, ref.size)
        require(ref.path not in self.pins or self.pins[ref.path] == pin, "conflicting_file_refs")
        self.pins[ref.path] = pin
        raw, _ = self.read(ref.path)
        require(len(raw) == ref.size and digest(raw) == ref.sha256, "file_binding_mismatch")
        return raw

    def document(self, ref: FileRef) -> Any:
        return strict_json(self.bound(ref))


@lru_cache(maxsize=1)
def coverage_validator() -> Callable[..., None]:
    # Execute only our sibling module's definitions, never a script supplied by evidence.
    module = runpy.run_path(str(Path(__file__).with_name("check-image-findings.py")))
    return cast(Callable[..., None], module["validate_scan_coverage"])


def unique_services(items: list[Any]) -> dict[str, Any]:
    names = [item.service for item in items]
    require(len(names) == len(set(names)) and set(names) == SERVICES, "service_coverage")
    return dict(zip(names, items, strict=True))


def date_window(reviewed: datetime, expires: datetime, now: datetime) -> None:
    require(reviewed <= now < expires and reviewed < expires, "invalid_review_window")


def validate_source(reader: BundleReader, binding: SourceBinding, expected: str) -> datetime:
    source = SourceSnapshot.model_validate(reader.document(binding.manifest))
    require(binding.source_tree_sha256 == expected == source.source_tree_sha256, "source_binding")
    records = [entry.model_dump() for entry in source.files]
    raw = (json.dumps(records, sort_keys=True, indent=2) + "\n").encode()
    require(digest(raw) == expected, "source_tree_digest")
    paths = [entry.path for entry in source.files]
    require(len(paths) == len(set(paths)) and paths == sorted(paths), "source_manifest_paths")
    expected_paths = set(paths)
    prefix = binding.directory + "/"
    if binding.manifest.path.startswith(prefix):
        expected_paths.add(binding.manifest.path.removeprefix(prefix))
    expected_directories = {"."}
    for path in expected_paths:
        expected_directories.update(str(parent) for parent in PurePosixPath(path).parents)
    expected_members = (expected_paths, expected_directories)
    require(
        reader.source_tree_paths(binding.directory) == expected_members,
        "source_directory_membership",
    )
    reader.source_memberships[binding.directory] = expected_members
    for entry in source.files:
        path = relative_path(binding.directory + "/" + entry.path)
        reader.bound(FileRef(path=path, sha256=entry.sha256, size=entry.bytes))
        require(reader.read(path)[1] == entry.mode, "source_mode")
    return source.created_at


def validate_image(
    reader: BundleReader, inventory_path: str, item: InventoryImage, artifacts: ImageArtifacts
) -> tuple[dict[str, Any], dict[str, Any]]:
    parent = PurePosixPath(inventory_path).parent
    refs = {"scan": (item.scan, item.scan_sha256), "sbom": (item.sbom, item.sbom_sha256)}
    for name in ("manifest", "config", "inspection"):
        ref = getattr(item.identity_inputs, name)
        refs[name] = (ref.file, ref.sha256)
    documents: dict[str, Any] = {}
    for name, (file, checksum) in refs.items():
        bound: FileRef = getattr(artifacts, name)
        require(bound.path == str(parent / file) and bound.sha256 == checksum, "inventory_ref")
        documents[name] = reader.document(bound)
    require(item.identity_match_fields == ["Architecture", "Os", "RootFS"], "identity_fields")
    require(item.scanner == SCANNER, "scanner_identity")
    inspection, config = documents["inspection"], documents["config"]
    require(isinstance(inspection, dict) and isinstance(config, dict), "image_identity")
    require(set(inspection) == {"Id", "Architecture", "Os", "RootFS"}, "inspection_fields")
    rootfs = config.get("rootfs")
    require(isinstance(rootfs, dict) and set(rootfs) == {"type", "diff_ids"}, "rootfs_identity")
    layers = rootfs["diff_ids"]
    require(
        rootfs["type"] == "layers" and isinstance(layers, list) and 0 < len(layers) <= 4096,
        "rootfs_identity",
    )
    require(
        all(isinstance(v, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", v) for v in layers),
        "rootfs_identity",
    )
    require(
        inspection
        == {
            "Id": item.image_id,
            "Architecture": item.architecture,
            "Os": "linux",
            "RootFS": {"Type": "layers", "Layers": layers},
        }
        and config.get("architecture") == item.architecture
        and config.get("os") == "linux"
        and item.image_config_id == "sha256:" + artifacts.config.sha256,
        "image_identity",
    )
    manifest = documents["manifest"]
    require(isinstance(manifest, list) and len(manifest) == 1, "ambiguous_image_manifest")
    selected = manifest[0]
    require(
        isinstance(selected, dict) and set(selected) <= {"Config", "RepoTags", "Layers"},
        "image_manifest",
    )
    require(selected.get("Config") == item.identity_inputs.config.archive_member, "selected_config")
    saved_layers = selected.get("Layers")
    require(isinstance(saved_layers, list) and len(saved_layers) == len(layers), "manifest_layers")
    for layer in saved_layers:
        relative_path(layer)
    report, sbom = documents["scan"], documents["sbom"]
    require(isinstance(report, dict) and isinstance(sbom, dict), "scan_document")
    require(
        report.get("Metadata", {}).get("ImageConfig", {}).get("rootfs") == rootfs
        and report["Metadata"]["ImageConfig"].get("os") == "linux"
        and report["Metadata"].get("DiffIDs") == layers,
        "scan_rootfs",
    )
    return report, sbom


def raw_identity(
    item: InventoryImage,
    report: dict[str, Any],
    result: dict[str, Any],
    finding: dict[str, Any],
    result_index: int,
    finding_index: int,
    source_sha256: str,
) -> RecordIdentity:
    return RecordIdentity(
        service=item.service,
        image_id=item.image_id,
        image_config_id=item.image_config_id,
        platform=Platform(os="linux", architecture=item.architecture),
        scanner_image=item.scanner,
        scanner_version=report["Trivy"]["Version"],
        source_tree_sha256=source_sha256,
        raw_scan_sha256=item.scan_sha256,
        sbom_sha256=item.sbom_sha256,
        artifact=report["ArtifactName"],
        result_index=result_index,
        finding_index=finding_index,
        target=result["Target"],
        result_class=result["Class"],
        result_type=result["Type"],
        package=finding["PkgName"],
        package_id=finding.get("PkgID"),
        package_path=finding.get("PkgPath"),
        installed_version=finding["InstalledVersion"],
        vulnerability_id=finding["VulnerabilityID"],
        original_severity=finding["Severity"],
        finding_sha256=finding_digest(finding),
    )


def validate_assessment(
    reader: BundleReader,
    record: Assessment,
    expected: RecordIdentity,
    finding: dict[str, Any],
    manifest: ReviewManifest,
    completed: datetime,
    source_created: datetime,
    now: datetime,
) -> None:
    require(record.identity == expected, "finding_identity")
    date_window(record.reviewed_at, record.expires_at, now)
    require(
        completed <= record.reviewed_at <= manifest.reviewed_at
        and manifest.expires_at <= record.expires_at,
        "assessment_dates",
    )
    fixed = finding.get("FixedVersion")
    require(fixed is None or isinstance(fixed, str), "fix_metadata")
    require(
        record.fix.scanner_fixed_version == (fixed or None)
        and record.fix.scanner_fix_available == bool(fixed),
        "fix_binding",
    )
    require({ref.purpose for ref in record.evidence} == QUESTIONS, "required_proof_questions")
    seen: set[tuple[str, str]] = set()
    for ref in record.evidence:
        key = (ref.file.path, ref.pointer or "")
        require(key not in seen, "duplicate_evidence_ref")
        seen.add(key)
        proof = Proof.model_validate(json_pointer(reader.document(ref.file), ref.pointer))
        require(proof.identity == expected and proof.scope == record.scope, "proof_scope")
        require(proof.purpose == ref.purpose, "proof_question")
        require(proof.observed_at <= record.reviewed_at, "proof_date")
        observed = validate_observations(reader, proof.observations, proof.scope)
        if proof.reused_exact_bytes is not None:
            reuse = proof.reused_exact_bytes
            require(
                source_created <= reuse.verified_at <= record.reviewed_at
                and proof.observed_at <= reuse.verified_at
                and reuse.current_source_tree_sha256 == expected.source_tree_sha256,
                "reuse_scope_or_date",
            )
            current = validate_observations(reader, reuse.current, proof.scope)
            require(observed == current, "reused_bytes_mismatch")
        elif proof.purpose in {"component", "reachability", "exposure"}:
            require(source_created <= proof.observed_at, "predating_runtime_observation")


def meaningful_observation(value: Any, scope: ObservationScope) -> bool:
    """Check selected content, not the truth of arbitrary historical report formats."""
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        # Visit every child so an earlier valid entry cannot hide a failed receipt.
        return any([meaningful_observation(item, scope) for item in value])
    if not isinstance(value, dict):
        return False
    if value.get("kind") == "scoped-empty-result":
        empty = EmptyObservation.model_validate(value)
        require(empty.scope.model_dump() == scope.model_dump(), "empty_observation_scope")
        return True
    flags = {"complete", "enumeration_complete", "search_complete", "success"}
    errors = {"error", "errors", "failure", "failures"}
    for key in flags & value.keys():
        require(value[key] is True, "incomplete_observation")
    for key in errors & value.keys():
        require(value[key] in (None, "", [], {}), "failed_observation")
    require(
        not isinstance(value.get("status"), str)
        or value["status"].strip().lower()
        not in {"failed", "error", "incomplete", "partial", "blocked"},
        "failed_observation",
    )
    result_fields = {"results", "observations", "findings", "matches", "hits"} & value.keys()
    require(
        not result_fields or not all(value[key] in (None, "", [], {}) for key in result_fields),
        "empty_observation_requires_envelope",
    )
    metadata = (
        flags
        | errors
        | {
            "schema_version",
            "kind",
            "status",
            "scope",
            "identity",
            "purpose",
            "observed_at",
            "coverage",
            "conclusion",
            "rationale",
            "limitations",
            "missing_inputs",
        }
    )
    return any(
        [meaningful_observation(item, scope) for key, item in value.items() if key not in metadata]
    )


def validate_observations(
    reader: BundleReader, refs: list[ObservationRef], scope: ObservationScope
) -> Counter[tuple[str, int, str]]:
    seen: set[tuple[str, str]] = set()
    bindings: Counter[tuple[str, int, str]] = Counter()
    for ref in refs:
        key = (ref.file.path, ref.pointer or "")
        require(key not in seen, "duplicate_observation_ref")
        seen.add(key)
        raw = reader.bound(ref.file)
        require(bool(raw.strip()), "empty_observation")
        if ref.pointer is not None or ref.file.path.endswith(".json"):
            selected = json_pointer(strict_json(raw), ref.pointer)
            require(meaningful_observation(selected, scope), "empty_observation")
        bindings[(ref.file.sha256, ref.file.size, ref.pointer or "")] += 1
    return bindings


def verify_bundle(
    root: Path,
    review_path: str,
    expected_review_sha256: str,
    expected_source_sha256: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate an immutable bundle. Clock injection is for tests, not a CLI bypass."""
    for checksum in (expected_review_sha256, expected_source_sha256):
        require(re.fullmatch(r"[0-9a-f]{64}", checksum) is not None, "trusted_pin_format")
    clock = utc_time(now if now is not None else datetime.now(UTC))
    reader = BundleReader(root)
    try:
        raw, _ = reader.read(review_path)
        require(digest(raw) == expected_review_sha256, "trusted_manifest_mismatch")
        reader.pins[review_path] = (expected_review_sha256, len(raw))
        manifest = ReviewManifest.model_validate(strict_json(raw))
        date_window(manifest.reviewed_at, manifest.expires_at, clock)
        created = validate_source(reader, manifest.source, expected_source_sha256)
        inventory = Inventory.model_validate(reader.document(manifest.inventory))
        require(
            created <= inventory.started_at <= inventory.completed_at <= manifest.reviewed_at,
            "collection_dates",
        )
        images, artifacts = unique_services(inventory.images), unique_services(manifest.images)
        assessments: dict[tuple[str, int, int], Assessment] = {}
        for record in manifest.assessments:
            key: tuple[str, int, int] = (
                record.identity.service,
                record.identity.result_index,
                record.identity.finding_index,
            )
            require(key not in assessments, "duplicate_assessment")
            assessments[key] = record
        matched: set[tuple[str, int, int]] = set()
        counts: Counter[str] = Counter()
        for service in sorted(SERVICES):
            item = images[service]
            report, sbom = validate_image(reader, manifest.inventory.path, item, artifacts[service])
            try:
                coverage_validator()(item.model_dump(), report, sbom, today=clock.date())
            except (ValueError, TypeError, KeyError):
                raise GateError("scan_coverage") from None
            for value in (report["CreatedAt"], sbom["metadata"]["timestamp"]):
                require(
                    inventory.started_at <= utc_time(value) <= inventory.completed_at,
                    "scan_collection_time",
                )
            for ri, result in enumerate(report["Results"]):
                for vi, finding in enumerate(result.get("Vulnerabilities", [])):
                    counts[finding["Severity"]] += 1
                    if finding["Severity"] not in {"HIGH", "CRITICAL"}:
                        continue
                    key = (service, ri, vi)
                    require(key in assessments, "missing_assessment")
                    expected = raw_identity(
                        item, report, result, finding, ri, vi, expected_source_sha256
                    )
                    validate_assessment(
                        reader,
                        assessments[key],
                        expected,
                        finding,
                        manifest,
                        inventory.completed_at,
                        created,
                        clock,
                    )
                    matched.add(key)
        require(set(assessments) == matched, "extra_assessment")
        reader.recheck()
        return {
            "schema_version": 1,
            "valid": True,
            "services": len(images),
            "raw_severity_counts": dict(sorted(counts.items())),
            "high_critical_assessments": len(matched),
            "verified_files": len(reader.pins),
            "verified_bytes": reader.total,
            "rationale_truth_verified": False,
            "release_approved": False,
        }
    finally:
        reader.close()


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise GateError("invalid_arguments")


def main(argv: list[str] | None = None) -> int:
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("--bundle-root", type=Path, required=True)
        parser.add_argument("--review-manifest", required=True)
        parser.add_argument("--expected-review-sha256", required=True)
        parser.add_argument("--expected-source-sha256", required=True)
        args = parser.parse_args(argv)
        result = verify_bundle(
            args.bundle_root,
            args.review_manifest,
            args.expected_review_sha256,
            args.expected_source_sha256,
        )
    except (
        GateError,
        ValidationError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        RecursionError,
        OverflowError,
    ):
        print(json.dumps({"schema_version": 1, "valid": False, "error": "invalid_bundle"}))
        return 1
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
