"""Read-only current source-advisory consistency gate, not a release approval.

Use --expected-review-sha256 from protected adoption, never from an unreviewed
submission, and --expected-source-sha256 for the frozen build payload. CI promotion
and authority selection are separate. No private ledger conversion is performed.

Contract v1 binds the public scan-source collector's six reports, two secret logs,
requirements, snapshot manifests and all ten version streams. Older collections
without collection dates/marker provenance cannot qualify by copying assertions.
Marker replay requires the same trusted interpreter bytes, packaging version and
complete default marker environment. This is that environment's dependency audit,
not proof of coverage on other Python versions/platforms. The all-platform lock
inventory is separately reconciled with the source SBOM. No resolver, scanner,
captured program or package is executed by this verifier.

One record is required per Python vulnerability and per Node advisory finding
(version plus its complete ordered paths). Hashes cover the full raw dependency/
advisory and finding, including new fields; raw severities are never downgraded.
Missing Python severity is explicitly UNKNOWN and still requires review. Runtime
permits only not-applicable. Build/dev/test mitigate additionally requires fresh,
concrete remediation and verification proofs. Scope classification and upstream
fix claims remain trusted review judgments, not facts proved by hash consistency.
The collector's passed flag stays false when raw findings remain.

verify_source_collection is a separate acquisition-only API. Its CollectionManifest
contains only schema_version, source, inventory and the 21 file references. It
checks the same collection integrity, chronology, coverage and raw record shapes,
without accepting decisions or constructing a review. Complete means collection
consistency, not clean findings or approval. The existing CLI remains review-only.
"""

from __future__ import annotations

import json
import os
import re
import runpy
import stat
import sys
import tomllib
from collections import Counter
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, cast
from urllib.parse import unquote

import yaml  # type: ignore[import-untyped]
from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from pydantic import Field, ValidationError, model_validator

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import check_release_assessments as shared

REPORTS = {
    "python-audit.json",
    "node-audit.json",
    "python.cdx.json",
    "source.cdx.json",
    "gitleaks-source.json",
    "gitleaks-history.json",
}
TOOLS = {"uv", "pip-audit", "pnpm", "trivy", "gitleaks"}
FILES = (
    REPORTS
    | {
        "python-requirements.txt",
        "source-files.json",
        "source-snapshot.json",
        "gitleaks-source.json.log",
        "gitleaks-history.json.log",
    }
    | {f"{tool}-version.{stream}" for tool in TOOLS for stream in ("stdout", "stderr")}
)
QUESTION = Literal[
    "advisory", "component", "reachability", "exposure", "fix", "remediation", "verification"
]


@lru_cache(maxsize=1)
def collector() -> dict[str, Any]:
    # Only trusted sibling definitions; never code selected by a bundle.
    return runpy.run_path(str(Path(__file__).with_name("scan-source.py")))


class Report(shared.StrictModel):
    report: shared.RelativePath
    exit_code: Annotated[int, Field(ge=0, le=255)]
    coverage_verified: shared.Complete
    status: Literal["clean", "findings"]
    sha256: shared.Digest
    log: shared.RelativePath | None = None
    log_sha256: shared.Digest | None = None


class VersionEvidence(shared.StrictModel):
    exit_code: Annotated[int, Field(ge=0, le=0)]
    verified: shared.Complete
    stdout: shared.RelativePath
    stderr: shared.RelativePath
    stdout_sha256: shared.Digest
    stderr_sha256: shared.Digest


class Snapshot(shared.StrictModel):
    manifest: Literal["source-snapshot.json"]
    sha256: shared.Digest
    source_files_sha256: shared.Digest
    stable: shared.Complete


class MarkerContext(shared.StrictModel):
    schema_version: Literal[1]
    packaging_version: shared.ShortText
    implementation: Literal["cpython"]
    python_version: shared.ShortText
    interpreter_sha256: shared.Digest
    environment: Annotated[dict[str, str], Field(min_length=11, max_length=11)]


class Inventory(shared.StrictModel):
    complete: shared.Complete
    passed: bool
    started_at: shared.Timestamp
    completed_at: shared.Timestamp
    marker_context: MarkerContext
    reports: Annotated[list[Report], Field(min_length=6, max_length=6)]
    tools: Annotated[dict[str, str], Field(min_length=5, max_length=5)]
    tool_version_evidence: Annotated[dict[str, VersionEvidence], Field(min_length=5, max_length=5)]
    snapshot: Snapshot
    scope: shared.Text
    audited_build_requirements: Annotated[
        list[shared.ShortText], Field(min_length=1, max_length=64)
    ]
    expected_history_commits: Annotated[int, Field(ge=1, le=1_000_000)]
    requirements_sha256: shared.Digest
    report_bindings_verified: shared.Complete


class Identity(shared.StrictModel):
    scanner: Literal["pip-audit", "pnpm"]
    scanner_version: shared.ShortText
    source_tree_sha256: shared.Digest
    inventory_sha256: shared.Digest
    raw_report_sha256: shared.Digest
    sbom_sha256: shared.Digest
    record_pointer: shared.ShortText
    package: shared.ShortText
    installed_version: shared.ShortText
    advisory_id: shared.ShortText
    original_severity: Literal[
        "UNKNOWN",
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
        "unknown",
        "info",
        "low",
        "moderate",
        "medium",
        "high",
        "critical",
    ]
    paths: Annotated[list[shared.ShortText], Field(max_length=4096)]
    finding_sha256: shared.Digest


class Fix(shared.StrictModel):
    scanner_fixed_versions: Annotated[
        list[Annotated[str, Field(max_length=1024)]], Field(max_length=64)
    ]
    scanner_fix_available: bool
    upstream_availability: Literal["available", "unavailable", "unknown"]
    upstream_fixed_versions: Annotated[list[shared.ShortText], Field(max_length=64)]
    rationale: shared.Text

    @model_validator(mode="after")
    def upstream_versions(self) -> Fix:
        shared.require(
            bool(self.upstream_fixed_versions) == (self.upstream_availability == "available")
            and len(self.upstream_fixed_versions) == len(set(self.upstream_fixed_versions)),
            "upstream_fix_versions",
        )
        return self


class Evidence(shared.ObservationRef):
    purpose: QUESTION


class Proof(shared.StrictModel):
    schema_version: Literal[1]
    identity: Identity
    scope: shared.ObservationScope
    purpose: QUESTION
    observed_at: shared.Timestamp
    coverage: Literal["complete-for-question"]
    conclusion: shared.Text
    missing_inputs: Annotated[list[shared.ShortText], Field(max_length=0)]
    limitations: Annotated[list[shared.ShortText], Field(max_length=64)]
    observations: Annotated[list[shared.ObservationRef], Field(min_length=1, max_length=64)]
    reused_exact_bytes: shared.ReusedObservations | None = None


class Assessment(shared.StrictModel):
    identity: Identity
    scope: shared.ObservationScope
    decision: Literal["not-applicable", "mitigate"]
    review_owner: shared.ShortText
    review_method: Literal["human", "ai-assisted", "automated"]
    reviewed_at: shared.Timestamp
    expires_at: shared.Timestamp
    rationale: shared.Text
    reachability: shared.Text
    exposure: shared.Text
    fix: Fix
    missing_inputs: Annotated[list[shared.ShortText], Field(max_length=0)]
    limitations: Annotated[list[shared.ShortText], Field(max_length=64)]
    evidence: Annotated[list[Evidence], Field(min_length=5, max_length=64)]


class CollectionManifest(shared.StrictModel):
    schema_version: Literal[1]
    source: shared.SourceBinding
    inventory: shared.FileRef
    files: Annotated[list[shared.FileRef], Field(min_length=21, max_length=21)]


class ReviewManifest(CollectionManifest):
    hash_format: Literal["source-full-finding-json-v1"]
    review_owner: shared.ShortText
    review_method: Literal["human", "ai-assisted", "automated"]
    reviewed_at: shared.Timestamp
    expires_at: shared.Timestamp
    assessments: Annotated[list[Assessment], Field(max_length=10000)]
    limitations: Annotated[list[shared.ShortText], Field(min_length=1, max_length=64)]


class BoundText:
    """In-memory input for the trusted requirement parser, with no second file read."""

    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def read_text(self) -> str:
        return self.raw.decode("utf-8")


def pinned_tools() -> dict[str, str]:
    module = collector()
    return {
        name: module[key]
        for name, key in {
            "uv": "UV_VERSION",
            "pnpm": "PNPM_VERSION",
            "pip-audit": "PIP_AUDIT_VERSION",
            "trivy": "TRIVY",
            "gitleaks": "GITLEAKS",
        }.items()
    }


def bind_collection(
    reader: shared.BundleReader, manifest: CollectionManifest, inventory: Inventory
) -> dict[str, bytes]:
    parent = PurePosixPath(manifest.inventory.path).parent
    expected = {str(parent / name): name for name in FILES}
    shared.require(len({r.path for r in manifest.files}) == len(FILES), "duplicate_collection_ref")
    shared.require({r.path for r in manifest.files} == set(expected), "collection_files")
    raw = {expected[ref.path]: reader.bound(ref) for ref in manifest.files}
    rows = {r.report: r for r in inventory.reports}
    shared.require(len(rows) == 6 and set(rows) == REPORTS, "report_coverage")
    for name, row in rows.items():
        shared.require(shared.digest(raw[name]) == row.sha256, "report_hash")
        if name.startswith("gitleaks-"):
            shared.require(row.log == name + ".log", "secret_log")
            shared.require(shared.digest(raw[name + ".log"]) == row.log_sha256, "secret_log_hash")
        else:
            shared.require(row.log is None and row.log_sha256 is None, "unexpected_log")
    shared.require(inventory.tools == pinned_tools(), "tool_pins")
    shared.require(set(inventory.tool_version_evidence) == TOOLS, "version_coverage")
    prefixes = {
        "uv": "uv 0.8.15",
        "pip-audit": "pip-audit 2.10.0",
        "pnpm": "10.17.1",
        "trivy": "Version: 0.74.0",
        "gitleaks": "v8.30.1",
    }
    for name, evidence in inventory.tool_version_evidence.items():
        for stream in ("stdout", "stderr"):
            file = f"{name}-version.{stream}"
            shared.require(getattr(evidence, stream) == file, "version_path")
            shared.require(
                shared.digest(raw[file]) == getattr(evidence, stream + "_sha256"), "version_hash"
            )
        shared.require(type(evidence.exit_code) is int, "version_exit")
        shared.require(
            raw[f"{name}-version.stdout"] == (prefixes[name] + "\n").encode()
            if name == "gitleaks"
            else re.match(
                re.escape(prefixes[name]) + r"(?:\s|$)", raw[f"{name}-version.stdout"].decode()
            )
            is not None,
            "version_output",
        )
    for name, expected_hash in (
        ("python-requirements.txt", inventory.requirements_sha256),
        ("source-files.json", inventory.snapshot.source_files_sha256),
        ("source-snapshot.json", inventory.snapshot.sha256),
    ):
        shared.require(shared.digest(raw[name]) == expected_hash, "collection_input_hash")
    return raw


def verify_snapshot(
    reader: shared.BundleReader, manifest: CollectionManifest, raw: dict[str, bytes]
) -> dict[str, bytes]:
    directory = str(PurePosixPath(manifest.inventory.path).parent / "source")
    expected_members = reader.source_memberships[manifest.source.directory]
    expected_paths, directories = expected_members
    shared.require(
        reader.source_tree_paths(directory) == expected_members, "saved_source_membership"
    )
    reader.source_memberships[directory] = expected_members
    files = shared.strict_json(raw["source-files.json"])
    members = shared.strict_json(raw["source-snapshot.json"])
    shared.require(
        isinstance(files, dict) and set(files) == expected_paths, "source_files_manifest"
    )
    shared.require(isinstance(members, dict), "snapshot_manifest")
    saved: dict[str, bytes] = {}
    for path in sorted(expected_paths):
        approved, mode = reader.read(manifest.source.directory + "/" + path)
        ref = shared.FileRef(
            path=directory + "/" + path, size=len(approved), sha256=shared.digest(approved)
        )
        saved[path] = reader.bound(ref)
        shared.require(reader.read(ref.path)[1] == mode, "saved_source_mode")
        shared.require(
            files[path] == ref.sha256
            and members.get(path)
            == {
                "kind": "file",
                "mode": mode,
                "sha256": ref.sha256,
            },
            "snapshot_file",
        )
    shared.require(set(members) == expected_paths | directories, "snapshot_members")
    for path in directories:
        fd = reader.directory(directory if path == "." else directory + "/" + path)
        try:
            shared.require(
                members[path] == {"kind": "directory", "mode": stat.S_IMODE(os.fstat(fd).st_mode)},
                "snapshot_directory",
            )
        finally:
            os.close(fd)
    return saved


def node_lock(raw: bytes) -> tuple[set[tuple[str, str]], int]:
    """Only bounded, alias-free pnpm v9 YAML; never construct custom YAML objects."""
    shared.require(len(raw) <= 2 * 1024 * 1024, "lock_budget")
    depth = 0
    for index, event in enumerate(yaml.parse(raw, Loader=yaml.SafeLoader)):
        shared.require(index < 100_000 and not isinstance(event, yaml.AliasEvent), "yaml_budget")
        if isinstance(event, yaml.MappingStartEvent | yaml.SequenceStartEvent):
            depth += 1
            shared.require(depth <= 64, "yaml_depth")
        elif isinstance(event, yaml.MappingEndEvent | yaml.SequenceEndEvent):
            depth -= 1

    class UniqueLoader(yaml.SafeLoader):  # type: ignore[misc]
        pass

    def mapping(loader: Any, node: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            shared.require(isinstance(key, str) and key not in result, "yaml_key")
            result[key] = loader.construct_object(value_node)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    data = yaml.load(raw, Loader=UniqueLoader)
    shared.strict_json(json.dumps(data, allow_nan=False).encode())
    shared.require(
        isinstance(data, dict) and data.get("lockfileVersion") == "9.0", "node_lock_schema"
    )
    packages, snapshots, importers = data["packages"], data["snapshots"], data["importers"]
    shared.require(
        isinstance(packages, dict) and isinstance(snapshots, dict) and bool(packages),
        "node_lock_packages",
    )
    shared.require(isinstance(importers, dict) and "." in importers, "node_importers")
    for name, value in importers.items():
        if name != ".":
            shared.relative_path(name)
        shared.require(isinstance(value, dict), "node_importer")
    shared.require(all(isinstance(value, dict) for value in snapshots.values()), "node_snapshot")
    identities = set()
    for key, value in packages.items():
        name, separator, version = key.rpartition("@")
        shared.require(
            bool(name and separator and version) and "(" not in key and isinstance(value, dict),
            "node_lock_package",
        )
        identities.add((name, version))
    shared.require(
        {key.split("(", 1)[0] for key in snapshots} == set(packages), "node_snapshot_coverage"
    )
    # pnpm 10.17.1 includes workspace importers in audit's totalDependencies.
    return identities, len(snapshots) + len(importers)


def python_lock(
    saved: dict[str, bytes], raw_requirements: bytes, environment: dict[str, str]
) -> tuple[set[tuple[str, str]], set[tuple[str, str]], list[str]]:
    """Reconcile the bounded current uv v1 graph, all workspace extras plus dev.

    Unrecognized source/edge shapes and ambiguous resolutions fail, not silently
    disappear. This does not try to resolve new packages or emulate uv generally.
    """
    data = tomllib.loads(saved["uv.lock"].decode())
    shared.strict_json(json.dumps(data, allow_nan=False).encode())
    shared.require(type(data.get("version")) is int and data["version"] == 1, "python_lock_schema")
    shared.require(
        environment["python_full_version"] in SpecifierSet(data["requires-python"]),
        "python_lock_interpreter",
    )
    packages = data["package"]
    shared.require(isinstance(packages, list) and 0 < len(packages) <= 4096, "python_lock_packages")
    all_packages: dict[tuple[str, str], dict[str, Any]] = {}
    registry: dict[tuple[str, str], set[str]] = {}
    roots: list[tuple[str, str]] = []
    for package in packages:
        identity: tuple[str, str] = (
            canonicalize_name(shared.text(package["name"])),
            shared.text(package["version"]),
        )
        shared.require(identity not in all_packages, "duplicate_python_package")
        all_packages[identity] = package
        source = package["source"]
        shared.require(isinstance(source, dict) and len(source) == 1, "python_source")
        if "registry" in source:
            archive_hashes = {a["hash"] for a in package.get("wheels", [])}
            if "sdist" in package:
                archive_hashes.add(package["sdist"]["hash"])
            shared.require(
                bool(archive_hashes)
                and all(re.fullmatch(r"sha256:[0-9a-f]{64}", h) for h in archive_hashes),
                "python_archive_hashes",
            )
            registry[identity] = archive_hashes
        else:
            shared.require(set(source) in ({"editable"}, {"virtual"}), "python_source")
            roots.append(identity)
    shared.require(bool(roots and registry), "python_workspace")
    exported: dict[tuple[str, str], set[str]] = {}
    for line in raw_requirements.decode().replace("\\\n", "").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement_text, *hashes = re.split(r"\s+--hash=", line.strip())
        requirement = Requirement(requirement_text)
        pins = list(requirement.specifier)
        shared.require(
            len(pins) == 1 and pins[0].operator == "==" and not requirement.url, "requirement_pin"
        )
        identity = (canonicalize_name(requirement.name), pins[0].version)
        shared.require(identity not in exported, "duplicate_requirement")
        exported[identity] = {h.strip() for h in hashes}
    shared.require(exported == registry, "requirements_lock_binding")
    expected = cast(
        set[tuple[str, str]],
        collector()["python_requirements"](BoundText(raw_requirements), environment),
    )
    pending = [
        (identity, set(all_packages[identity].get("optional-dependencies", {})))
        for identity in roots
    ]
    processed: dict[tuple[str, str], set[str]] = {}
    visits = 0
    edge_count = 0
    while pending:
        visits += 1
        shared.require(visits <= 32768, "python_graph_budget")
        identity, extras = pending.pop()
        shared.require(len(extras) <= 128, "python_extras_budget")
        old = processed.get(identity)
        if old is not None and extras <= old:
            continue
        processed[identity] = extras | (old or set())
        package = all_packages[identity]
        edges = list(package.get("dependencies", [])) if old is None else []
        if identity in roots and old is None:
            edges.extend(package.get("dev-dependencies", {}).get("dev", []))
        for extra in extras - (old or set()):
            edges.extend(package.get("optional-dependencies", {}).get(extra, []))
        edge_count += len(edges)
        shared.require(edge_count <= 32768, "python_graph_budget")
        for edge in edges:
            shared.require(
                set(edge) <= {"name", "version", "source", "marker", "extra"}, "python_edge"
            )
            if "marker" in edge and not Marker(edge["marker"]).evaluate(environment=environment):
                continue
            candidates = [
                key
                for key, p in all_packages.items()
                if key[0] == canonicalize_name(edge["name"])
                and ("version" not in edge or key[1] == edge["version"])
                and ("source" not in edge or p["source"] == edge["source"])
            ]
            shared.require(len(candidates) == 1, "python_edge_resolution")
            pending.append((candidates[0], set(edge.get("extra", []))))
        shared.require(len(processed) <= 4096 and len(pending) <= 32768, "python_graph_budget")
    shared.require(expected == set(processed) & set(registry), "python_marker_coverage")
    project = tomllib.loads(saved["pyproject.toml"].decode())
    dev = {str(Requirement(r)) for r in project["dependency-groups"]["dev"]}
    projects = {"pyproject.toml"}
    for pattern in project["tool"]["uv"]["workspace"]["members"]:
        shared.require(
            isinstance(pattern, str)
            and ".." not in pattern.split("/")
            and not pattern.startswith("/"),
            "workspace_path",
        )
        projects.update(
            name
            for name in saved
            if name.endswith("/pyproject.toml") and PurePosixPath(name).parent.match(pattern)
        )
    build = set()
    for path in projects:
        for value in (
            tomllib.loads(saved[path].decode()).get("build-system", {}).get("requires", [])
        ):
            requirement = Requirement(value)
            pins = list(requirement.specifier)
            shared.require(
                not requirement.url
                and not requirement.marker
                and not requirement.extras
                and len(pins) == 1
                and pins[0].operator == "=="
                and "*" not in pins[0].version
                and str(requirement) in dev,
                "build_pin",
            )
            shared.require(
                (canonicalize_name(requirement.name), pins[0].version) in expected, "build_coverage"
            )
            build.add(str(requirement))
    shared.require(bool(build), "missing_build_requirements")
    return expected, set(all_packages), sorted(build)


def source_sbom_packages(data: dict[str, Any]) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    packages: dict[str, set[tuple[str, str]]] = {"npm": set(), "pypi": set()}
    for component in data["components"]:
        if component["type"] == "application":
            continue
        shared.require(component["type"] == "library", "source_component_type")
        purl = component.get("purl")
        shared.require(
            isinstance(purl, str) and purl.startswith(("pkg:npm/", "pkg:pypi/")), "source_purl"
        )
        ecosystem, path = purl[4:].split("/", 1)
        name, sep, version = unquote(path).rpartition("@")
        actual_name = (component["group"] + "/" if component.get("group") else "") + component[
            "name"
        ]
        shared.require(
            bool(sep) and (name, version) == (actual_name, component["version"]),
            "source_component_identity",
        )
        identity = (canonicalize_name(name) if ecosystem == "pypi" else name, version)
        shared.require(identity not in packages[ecosystem], "source_duplicate_component")
        packages[ecosystem].add(identity)
    return packages["pypi"], packages["npm"]


def coverage(
    raw: dict[str, bytes], inventory: Inventory, saved: dict[str, bytes]
) -> tuple[dict[str, Any], dict[str, Any]]:
    module = collector()
    shared.require(
        inventory.marker_context.model_dump() == module["marker_context"](),
        "marker_interpreter_mismatch",
    )
    expected, all_python, build = python_lock(
        saved, raw["python-requirements.txt"], inventory.marker_context.environment
    )
    shared.require(inventory.audited_build_requirements == build, "audited_build_requirements")
    all_node, node_total = node_lock(saved["pnpm-lock.yaml"])
    docs = {name: shared.strict_json(raw[name]) for name in REPORTS}
    rows = {row.report: row for row in inventory.reports}
    for name, tool in (("python-audit.json", "pip-audit"), ("node-audit.json", "pnpm")):
        status = module["dependency_audit_status"](raw[name], tool, rows[name].exit_code, expected)
        shared.require(status != "error" and status == rows[name].status, "dependency_coverage")
    shared.require(
        docs["node-audit.json"]["metadata"]["totalDependencies"] == node_total,
        "node_dependency_coverage",
    )
    python_ids = {v["id"] for d in docs["python-audit.json"]["dependencies"] for v in d["vulns"]}
    for name, tool in (("python.cdx.json", "pip-audit"), ("source.cdx.json", "trivy")):
        shared.require(module["sbom_complete"](raw[name], tool, expected), "sbom_coverage")
        timestamp = shared.utc_time(docs[name]["metadata"]["timestamp"])
        shared.require(inventory.started_at <= timestamp <= inventory.completed_at, "sbom_date")
        if tool == "pip-audit":
            ids = [v["id"] for v in docs[name].get("vulnerabilities", [])]
            shared.require(
                len(ids) == len(set(ids)) and set(ids) == python_ids, "sbom_vulnerability_coverage"
            )
            exit_code = int(bool(python_ids))
        else:
            shared.require(
                source_sbom_packages(docs[name]) == (all_python, all_node), "source_sbom_packages"
            )
            exit_code = 0
        shared.require(
            rows[name].exit_code == exit_code
            and rows[name].status == ("findings" if exit_code else "clean"),
            "sbom_status",
        )
    for name in ("gitleaks-source.json", "gitleaks-history.json"):
        shared.require(
            module["clean_secret_report"](raw[name]) and docs[name] == [], "secret_findings"
        )
        commits = inventory.expected_history_commits if name == "gitleaks-history.json" else None
        shared.require(
            module["secret_scan_complete"](raw[name + ".log"].decode(), commits), "secret_coverage"
        )
        shared.require(rows[name].exit_code == 0 and rows[name].status == "clean", "secret_status")
    shared.require(
        inventory.passed == all(row.exit_code == 0 for row in inventory.reports),
        "collection_passed",
    )
    for advisory in docs["node-audit.json"]["advisories"].values():
        for finding in advisory["findings"]:
            shared.require(
                (advisory["module_name"], finding["version"]) in all_node, "node_finding_package"
            )
    return docs["python-audit.json"], docs["node-audit.json"]


def records(
    manifest: CollectionManifest,
    raw: dict[str, bytes],
    python: dict[str, Any],
    node: dict[str, Any],
) -> list[tuple[Identity, list[str], bool]]:
    found: list[tuple[Identity, list[str], bool]] = []
    for index, dependency in enumerate(python["dependencies"]):
        seen = set()
        for vi, vuln in enumerate(dependency["vulns"]):
            shared.require(vuln["id"] not in seen, "duplicate_python_advisory")
            seen.add(vuln["id"])
            fixes = vuln.get("fix_versions")
            shared.require(
                isinstance(fixes, list) and all(isinstance(v, str) and v.strip() for v in fixes),
                "python_fix_metadata",
            )
            identity = Identity(
                scanner="pip-audit",
                scanner_version="2.10.0",
                source_tree_sha256=manifest.source.source_tree_sha256,
                inventory_sha256=manifest.inventory.sha256,
                raw_report_sha256=shared.digest(raw["python-audit.json"]),
                sbom_sha256=shared.digest(raw["python.cdx.json"]),
                record_pointer=f"/dependencies/{index}/vulns/{vi}",
                package=dependency["name"],
                installed_version=dependency["version"],
                advisory_id=vuln["id"],
                original_severity=vuln.get("severity", "UNKNOWN"),
                paths=[],
                finding_sha256=shared.finding_digest(
                    {"dependency": dependency, "vulnerability_index": vi, "vulnerability": vuln}
                ),
            )
            found.append((identity, fixes, bool(fixes)))
    for key, advisory in node["advisories"].items():
        seen_findings: set[tuple[str, tuple[str, ...]]] = set()
        for index, finding in enumerate(advisory["findings"]):
            paths = finding["paths"]
            key_version = (finding["version"], tuple(paths))
            shared.require(
                len(paths) == len(set(paths)) and key_version not in seen_findings,
                "duplicate_node_finding",
            )
            seen_findings.add(key_version)
            fixed = advisory.get("patched_versions")
            shared.require(isinstance(fixed, str), "node_fix_metadata")
            identity = Identity(
                scanner="pnpm",
                scanner_version="10.17.1",
                source_tree_sha256=manifest.source.source_tree_sha256,
                inventory_sha256=manifest.inventory.sha256,
                raw_report_sha256=shared.digest(raw["node-audit.json"]),
                sbom_sha256=shared.digest(raw["source.cdx.json"]),
                record_pointer=f"/advisories/{key}/findings/{index}",
                package=advisory["module_name"],
                installed_version=finding["version"],
                advisory_id=advisory.get("github_advisory_id") or key,
                original_severity=advisory["severity"],
                paths=paths,
                finding_sha256=shared.finding_digest(
                    {"advisory": advisory, "finding_index": index, "finding": finding}
                ),
            )
            found.append((identity, [fixed], fixed not in {"", "<0.0.0"}))
    shared.require(len(found) <= 10000, "record_budget")
    return found


def assessment(
    reader: shared.BundleReader,
    record: Assessment,
    identity: Identity,
    fixes: list[str],
    available: bool,
    manifest: ReviewManifest,
    inventory: Inventory,
    source_created: datetime,
    clock: datetime,
) -> None:
    shared.require(record.identity == identity, "record_identity")
    shared.date_window(record.reviewed_at, record.expires_at, clock)
    shared.require(
        inventory.completed_at <= record.reviewed_at <= manifest.reviewed_at
        and manifest.expires_at <= record.expires_at,
        "assessment_dates",
    )
    shared.require(
        record.fix.scanner_fixed_versions == fixes
        and record.fix.scanner_fix_available == available,
        "scanner_fix_binding",
    )
    shared.require(
        record.scope.membership != "shipped-runtime" or record.decision == "not-applicable",
        "runtime_mitigation",
    )
    questions = shared.QUESTIONS | (
        {"remediation", "verification"} if record.decision == "mitigate" else set()
    )
    shared.require({ref.purpose for ref in record.evidence} == questions, "proof_questions")
    seen = set()
    for ref in record.evidence:
        key = (ref.file.path, ref.pointer or "")
        shared.require(key not in seen, "duplicate_proof")
        seen.add(key)
        proof = Proof.model_validate(shared.json_pointer(reader.document(ref.file), ref.pointer))
        shared.require(
            proof.identity == identity
            and proof.scope == record.scope
            and proof.purpose == ref.purpose,
            "proof_scope",
        )
        shared.require(proof.observed_at <= record.reviewed_at, "proof_date")
        observed = shared.validate_observations(reader, proof.observations, proof.scope)
        if proof.reused_exact_bytes is not None:
            reuse = proof.reused_exact_bytes
            shared.require(
                source_created <= reuse.verified_at <= record.reviewed_at
                and proof.observed_at <= reuse.verified_at
                and reuse.current_source_tree_sha256 == identity.source_tree_sha256,
                "reuse_date_scope",
            )
            shared.require(
                observed == shared.validate_observations(reader, reuse.current, proof.scope),
                "reused_bytes_mismatch",
            )
        elif proof.purpose not in {"advisory", "fix"}:
            shared.require(source_created <= proof.observed_at, "predating_observation")


def read_pinned_manifest(reader: shared.BundleReader, path: str, expected_sha256: str) -> Any:
    raw, _ = reader.read(path)
    shared.require(shared.digest(raw) == expected_sha256, "trusted_manifest_mismatch")
    reader.bound(shared.FileRef(path=path, sha256=expected_sha256, size=len(raw)))
    return shared.strict_json(raw)


def validate_collection(
    reader: shared.BundleReader,
    manifest: CollectionManifest,
    expected_source_sha256: str,
    collected_by: datetime,
) -> tuple[
    datetime,
    Inventory,
    dict[str, bytes],
    dict[str, Any],
    list[tuple[Identity, list[str], bool]],
]:
    created = shared.validate_source(reader, manifest.source, expected_source_sha256)
    inventory = Inventory.model_validate(reader.document(manifest.inventory))
    shared.require(
        created <= inventory.started_at <= inventory.completed_at <= collected_by,
        "collection_dates",
    )
    raw = bind_collection(reader, manifest, inventory)
    saved = verify_snapshot(reader, manifest, raw)
    python, node = coverage(raw, inventory, saved)
    observed = records(manifest, raw, python, node)
    rawcounts = {
        "python_advisories": sum(len(d["vulns"]) for d in python["dependencies"]),
        "node_advisories_by_severity": node["metadata"]["vulnerabilities"],
        "records_by_raw_severity": dict(
            sorted(Counter(i.original_severity for i, _, _ in observed).items())
        ),
        "secret_findings": 0,
    }
    return created, inventory, raw, rawcounts, observed


def verify_source_collection(
    root: Path,
    manifest_path: str,
    expected_manifest_sha256: str,
    expected_source_sha256: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Check acquisition consistency only; findings still need separate assessment.

    Callers supply the selected manifest/source pins and must treat any exception
    as incomplete. This function writes nothing and never evaluates review claims.
    The optional UTC clock supports deterministic tests, not a freshness override.
    """
    for checksum in (expected_manifest_sha256, expected_source_sha256):
        shared.require(re.fullmatch(r"[0-9a-f]{64}", checksum) is not None, "trusted_pin_format")
    clock = shared.utc_time(now if now is not None else datetime.now(UTC))
    reader = shared.BundleReader(root)
    try:
        manifest = CollectionManifest.model_validate(
            read_pinned_manifest(reader, manifest_path, expected_manifest_sha256)
        )
        _, inventory, raw, rawcounts, observed = validate_collection(
            reader, manifest, expected_source_sha256, clock
        )
        verify_snapshot(reader, manifest, raw)
        reader.recheck()
        return {
            "schema_version": 1,
            "complete": True,
            "rawcounts": rawcounts,
            "raw_passed": inventory.passed,
            "assessments_required": len(observed),
            "verified_files": len(reader.pins),
            "verified_bytes": reader.total,
            "rationale_truth_verified": False,
            "security_approved": False,
            "release_approved": False,
        }
    finally:
        reader.close()


def verify_source_bundle(
    root: Path,
    review_path: str,
    expected_review_sha256: str,
    expected_source_sha256: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate current adopted bytes; injected UTC clock is for tests, not CLI."""
    for checksum in (expected_review_sha256, expected_source_sha256):
        shared.require(re.fullmatch(r"[0-9a-f]{64}", checksum) is not None, "trusted_pin_format")
    clock = shared.utc_time(now if now is not None else datetime.now(UTC))
    reader = shared.BundleReader(root)
    try:
        manifest = ReviewManifest.model_validate(
            read_pinned_manifest(reader, review_path, expected_review_sha256)
        )
        shared.date_window(manifest.reviewed_at, manifest.expires_at, clock)
        created, inventory, raw, rawcounts, observed = validate_collection(
            reader, manifest, expected_source_sha256, manifest.reviewed_at
        )
        adopted = {(r.identity.scanner, r.identity.record_pointer): r for r in manifest.assessments}
        shared.require(
            len(adopted) == len(manifest.assessments) == len(observed), "assessment_coverage"
        )
        matched = set()
        for identity, fixes, available in observed:
            key = (identity.scanner, identity.record_pointer)
            shared.require(key in adopted and key not in matched, "missing_assessment")
            assessment(
                reader,
                adopted[key],
                identity,
                fixes,
                available,
                manifest,
                inventory,
                created,
                clock,
            )
            matched.add(key)
        shared.require(set(adopted) == matched, "extra_assessment")
        verify_snapshot(reader, manifest, raw)
        reader.recheck()
        return {
            "schema_version": 1,
            "valid": True,
            "rawcounts": rawcounts,
            "assessments": len(observed),
            "verified_files": len(reader.pins),
            "verified_bytes": reader.total,
            "rationale_truth_verified": False,
            "release_approved": False,
        }
    finally:
        reader.close()


def main(argv: list[str] | None = None) -> int:
    try:
        parser = shared.SafeParser(description=__doc__)
        parser.add_argument("--bundle-root", type=Path, required=True)
        parser.add_argument("--review-manifest", required=True)
        parser.add_argument("--expected-review-sha256", required=True)
        parser.add_argument("--expected-source-sha256", required=True)
        args = parser.parse_args(argv)
        result = verify_source_bundle(
            args.bundle_root,
            args.review_manifest,
            args.expected_review_sha256,
            args.expected_source_sha256,
        )
    except (
        shared.GateError,
        ValidationError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        RecursionError,
        OverflowError,
        yaml.YAMLError,
    ):
        print(json.dumps({"schema_version": 1, "valid": False, "error": "invalid_bundle"}))
        return 1
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
