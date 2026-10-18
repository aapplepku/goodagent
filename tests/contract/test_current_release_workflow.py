"""The promotion boundary consumes approved data, never candidate executable code."""

from __future__ import annotations

import copy
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from scripts import verify_current_release as gate
from scripts.check_release_assessments import GateError, digest
from scripts.release_evidence_archive import pack_bundle

NOW = datetime(2026, 10, 17, 12, tzinfo=UTC)


def encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def file_ref(path: str, raw: bytes = b"example") -> dict[str, Any]:
    return {"path": path, "sha256": digest(raw), "size": len(raw)}


class Fixture(gate.GitHub):
    def __init__(self, root: Path) -> None:
        self.path = root / "approval.json"
        self.data: dict[str, Any] = {
            "schema_version": 1,
            "status": "approved",
            "repository": "example/store",
            "repository_id": 101,
            "environment_id": 1234,
            "reviewer_ids": [500],
            "review_owner": "Synthetic owner",
            "reviewed_at": NOW.isoformat(),
            "expires_at": (NOW + timedelta(days=1)).isoformat(),
            "source_sha256": "a" * 64,
            "build": {
                "run_id": 201,
                "attempt": 1,
                "workflow_id": 301,
                "workflow_path": ".github/workflows/ci.yml",
                "commit": "c" * 40,
            },
            "build_artifact": {
                "artifact_id": 401,
                "name": "build-evidence",
                "digest": "sha256:" + "1" * 64,
                "size": 100,
            },
            "build_provenance": file_ref(gate.PROVENANCE),
            "evidence": {
                "run_id": 202,
                "attempt": 1,
                "workflow_id": 302,
                "workflow_path": ".github/workflows/evidence.yml",
                "commit": "d" * 40,
            },
            "evidence_artifact": {
                "artifact_id": 402,
                "name": "review-evidence",
                "digest": "sha256:" + "2" * 64,
                "size": 200,
            },
            "bundle_sha256": "b" * 64,
            "image_review": file_ref("reviews/images.json"),
            "source_review": file_ref("reviews/source.json"),
            "limitations": ["Synthetic consistency fixture, not a release approval."],
        }
        self.context = gate.Context(
            repository="example/store",
            repository_id=101,
            run_id=203,
            run_attempt=1,
            event="workflow_dispatch",
            policy_commit="e" * 40,
            ref="refs/heads/main",
        )
        self.responses: dict[str, Any] = {
            "": {"id": 101, "default_branch": "main"},
            "/branches/main": {"protected": True, "commit": {"sha": "e" * 40}},
            "/actions/runs/203/attempts/1": {
                "id": 203,
                "run_attempt": 1,
                "event": "workflow_dispatch",
                "path": gate.WORKFLOW,
                "head_sha": "e" * 40,
                "head_branch": "main",
                "repository": {"id": 101},
                "head_repository": {"id": 101},
            },
            f"/environments/{gate.ENVIRONMENT}": {
                "id": 1234,
                "name": gate.ENVIRONMENT,
                "deployment_branch_policy": {
                    "protected_branches": True,
                    "custom_branch_policies": False,
                },
                "protection_rules": [
                    {
                        "type": "required_reviewers",
                        "reviewers": [{"type": "User", "reviewer": {"id": 500}}],
                    }
                ],
            },
            "/actions/runs/203/approvals": [
                {
                    "state": "approved",
                    "user": {"id": 500, "type": "User"},
                    "environments": [{"id": 1234}],
                    "comment": "",
                }
            ],
        }
        for run_key, artifact_key in (
            ("build", "build_artifact"),
            ("evidence", "evidence_artifact"),
        ):
            run, artifact = self.data[run_key], self.data[artifact_key]
            self.responses[f"/actions/runs/{run['run_id']}/attempts/1"] = {
                "id": run["run_id"],
                "run_attempt": 1,
                "workflow_id": run["workflow_id"],
                "path": run["workflow_path"],
                "head_branch": "main",
                "head_sha": run["commit"],
                "status": "completed",
                "run_started_at": (NOW - timedelta(hours=2)).isoformat(),
                "updated_at": (NOW - timedelta(minutes=30)).isoformat(),
                "conclusion": "success",
                "event": "push",
                "repository": {"id": 101},
                "head_repository": {"id": 101},
            }
            self.responses[f"/actions/artifacts/{artifact['artifact_id']}"] = {
                "id": artifact["artifact_id"],
                "name": artifact["name"],
                "digest": artifact["digest"],
                "size_in_bytes": artifact["size"],
                "expired": False,
                "expires_at": (NOW + timedelta(days=2)).isoformat(),
                "created_at": (NOW - timedelta(hours=1)).isoformat(),
                "workflow_run": {
                    "id": run["run_id"],
                    "repository_id": 101,
                    "head_repository_id": 101,
                    "head_sha": run["commit"],
                },
            }
        self.calls: list[str] = []
        self.save()

    def save(self) -> None:
        raw = encoded(self.data)
        self.path.write_bytes(raw)
        self.responses["/actions/runs/203/approvals"][0]["comment"] = "security-review:" + digest(
            raw
        )

    def get(self, suffix: str) -> Any:
        self.calls.append(suffix)
        return copy.deepcopy(self.responses[suffix])

    def prepare(self) -> gate.Prepared:
        return gate.prepare(self.path, self.context, self, NOW)


@pytest.fixture
def fixture(tmp_path: Path) -> Fixture:
    return Fixture(tmp_path)


def test_prepare_requires_actual_matching_review_and_exact_runs(fixture: Fixture) -> None:
    prepared = fixture.prepare()
    assert prepared.approval_sha256 == digest(fixture.path.read_bytes())
    assert prepared.reviewer_id == 500 and prepared.security_approved is False
    assert len(fixture.calls) == 9


@pytest.mark.parametrize("run_id", [201, 202, 203])
@pytest.mark.parametrize("suffix", ["@main", "@refs/heads/main", "commit"])
def test_documented_ref_qualified_workflow_paths(
    fixture: Fixture, run_id: int, suffix: str
) -> None:
    run = fixture.responses[f"/actions/runs/{run_id}/attempts/1"]
    run["path"] += "@" + run["head_sha"] if suffix == "commit" else suffix
    assert fixture.prepare().security_approved is False


@pytest.mark.parametrize("run_id", [201, 202, 203])
@pytest.mark.parametrize("suffix", ["@topic", "@", "@main@main", "@main/../main", "@main\n"])
def test_unrelated_or_malformed_workflow_refs_fail(
    fixture: Fixture, run_id: int, suffix: str
) -> None:
    fixture.responses[f"/actions/runs/{run_id}/attempts/1"]["path"] += suffix
    with pytest.raises(GateError):
        fixture.prepare()


@pytest.mark.parametrize("status", ["pending", "revoked", "expired", ""])
def test_unapproved_record_fails_before_any_github_request(fixture: Fixture, status: str) -> None:
    fixture.data["status"] = status
    fixture.save()
    with pytest.raises(GateError, match="approval_pending"):
        fixture.prepare()
    assert fixture.calls == []


@pytest.mark.parametrize("field", ["reviewed_at", "expires_at"])
def test_approval_window_is_current(fixture: Fixture, field: str) -> None:
    fixture.data[field] = (
        NOW + timedelta(seconds=1) if field == "reviewed_at" else NOW
    ).isoformat()
    fixture.save()
    with pytest.raises(GateError):
        fixture.prepare()


@pytest.mark.parametrize("change", ["fork", "rerun", "branch", "changed-policy", "unprotected"])
def test_verification_origin_cannot_be_relabelled(fixture: Fixture, change: str) -> None:
    if change == "fork":
        fixture.context = fixture.context.model_copy(update={"repository_id": 99})
    elif change == "rerun":
        fixture.context = fixture.context.model_copy(update={"run_attempt": 2})
    elif change == "branch":
        fixture.context = fixture.context.model_copy(update={"ref": "refs/heads/topic"})
    elif change == "changed-policy":
        fixture.responses["/branches/main"]["commit"]["sha"] = "f" * 40
    else:
        fixture.responses["/branches/main"]["protected"] = False
    with pytest.raises(GateError):
        fixture.prepare()


@pytest.mark.parametrize(
    "change",
    [
        "environment",
        "branch-policy",
        "reviewers",
        "comment",
        "user",
        "bot",
        "rejected",
        "missing",
        "duplicate",
    ],
)
def test_weak_or_bypassed_environment_does_not_authorize_artifact_download(
    fixture: Fixture, change: str
) -> None:
    env = fixture.responses[f"/environments/{gate.ENVIRONMENT}"]
    reviews = fixture.responses["/actions/runs/203/approvals"]
    if change == "environment":
        env["id"] = 9999
    elif change == "branch-policy":
        env["deployment_branch_policy"] = None
    elif change == "reviewers":
        env["protection_rules"] = []
    elif change == "comment":
        reviews[0]["comment"] = "Ship it"
    elif change == "user":
        reviews[0]["user"]["id"] = 9999
    elif change == "bot":
        reviews[0]["user"]["type"] = "Bot"
    elif change == "rejected":
        reviews[0]["state"] = "rejected"
    elif change == "missing":
        reviews.clear()
    else:
        reviews.append(copy.deepcopy(reviews[0]))
    with pytest.raises(GateError):
        fixture.prepare()
    assert not any("/actions/artifacts/" in call for call in fixture.calls)


@pytest.mark.parametrize("run_id", [201, 202])
@pytest.mark.parametrize(
    "field,value",
    [
        ("run_attempt", 2),
        ("head_sha", "f" * 40),
        ("workflow_id", 1),
        ("path", ".github/workflows/other.yml"),
        ("conclusion", "failure"),
        ("conclusion", "cancelled"),
        ("status", "in_progress"),
        ("event", "pull_request"),
        ("head_repository", {"id": 99}),
    ],
)
def test_wrong_failed_or_fork_build_and_evidence_runs_block(
    fixture: Fixture, run_id: int, field: str, value: Any
) -> None:
    fixture.responses[f"/actions/runs/{run_id}/attempts/1"][field] = value
    with pytest.raises(GateError, match="wrong_or_unsuccessful_run"):
        fixture.prepare()


@pytest.mark.parametrize("artifact_id", [401, 402])
@pytest.mark.parametrize(
    "field,value",
    [
        ("expired", True),
        ("expires_at", NOW.isoformat()),
        ("created_at", (NOW + timedelta(seconds=1)).isoformat()),
        ("digest", "sha256:" + "f" * 64),
        ("size_in_bytes", 0),
        ("name", "different"),
        ("workflow_run", {"id": 999}),
    ],
)
def test_artifact_pins_and_retention_are_checked(
    fixture: Fixture, artifact_id: int, field: str, value: Any
) -> None:
    fixture.responses[f"/actions/artifacts/{artifact_id}"][field] = value
    with pytest.raises(GateError):
        fixture.prepare()


def build_files(root: Path, fixture: Fixture) -> tuple[Any, Any]:
    files: dict[str, bytes] = {}

    def child(prefix: str, name: str) -> str:
        raw = ("synthetic retained data:" + name).encode()
        files[prefix + name] = raw
        return digest(raw)

    image_prefix = gate.IMAGE_INVENTORY.rsplit("/", 1)[0] + "/"
    source_prefix = gate.SOURCE_INVENTORY.rsplit("/", 1)[0] + "/"
    image_inventory = {
        "images": [
            {
                "scan": "api.scan.json",
                "scan_sha256": child(image_prefix, "api.scan.json"),
                "sbom": "api.cdx.json",
                "sbom_sha256": child(image_prefix, "api.cdx.json"),
                "identity_inputs": {
                    key: {
                        "file": f"api.{key}.json",
                        "sha256": child(image_prefix, f"api.{key}.json"),
                    }
                    for key in ("config", "manifest", "inspection")
                },
            }
        ],
    }
    source_inventory = {
        "snapshot": {
            "manifest": "source-snapshot.json",
            "sha256": child(source_prefix, "source-snapshot.json"),
            "source_files_sha256": child(source_prefix, "source-files.json"),
        },
        "requirements_sha256": child(source_prefix, "python-requirements.txt"),
        "reports": [
            {
                "report": "audit.json",
                "sha256": child(source_prefix, "audit.json"),
                "log": "audit.log",
                "log_sha256": child(source_prefix, "audit.log"),
            }
        ],
        "tool_version_evidence": {
            "scanner": {
                "stdout": "scanner.stdout",
                "stdout_sha256": child(source_prefix, "scanner.stdout"),
                "stderr": "scanner.stderr",
                "stderr_sha256": child(source_prefix, "scanner.stderr"),
            }
        },
    }
    files[gate.IMAGE_INVENTORY] = encoded(image_inventory)
    files[gate.SOURCE_INVENTORY] = encoded(source_inventory)
    rows = []
    for name, raw in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        rows.append({"path": name, "sha256": digest(raw), "bytes": len(raw)})
    provenance = encoded(
        {
            "commit_sha": "c" * 40,
            "expected_commit_sha": "c" * 40,
            "commit_matches": True,
            "run_attempt": "1",
            "workflow_url": "https://github.com/example/store/actions/runs/201",
            "files": rows,
        }
    )
    path = root / gate.PROVENANCE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(provenance)
    fixture.data["build_provenance"] = file_ref(gate.PROVENANCE, provenance)
    fixture.save()
    return tuple(
        {"inventory": file_ref(name, files[name])}
        for name in (gate.IMAGE_INVENTORY, gate.SOURCE_INVENTORY)
    )  # type: ignore[return-value]


def test_build_provenance_and_retained_raw_files_are_bound(
    tmp_path: Path, fixture: Fixture
) -> None:
    image, source = build_files(tmp_path / "build", fixture)
    approval, _ = gate.load_approval(fixture.path, NOW)
    gate.verify_build_evidence(tmp_path / "build", approval, image, source)
    (tmp_path / "build/.opencommerce/source-scans/source-files.json").write_bytes(b"changed")
    with pytest.raises(GateError, match="file_binding_mismatch"):
        gate.verify_build_evidence(tmp_path / "build", approval, image, source)


def test_self_reported_replacement_provenance_does_not_change_trusted_pin(
    tmp_path: Path, fixture: Fixture
) -> None:
    image, source = build_files(tmp_path / "build", fixture)
    approval, _ = gate.load_approval(fixture.path, NOW)
    (tmp_path / "build" / gate.PROVENANCE).write_bytes(encoded({"commit_matches": True}))
    with pytest.raises(GateError, match="file_binding_mismatch"):
        gate.verify_build_evidence(tmp_path / "build", approval, image, source)


@pytest.mark.parametrize("run_id,artifact_id", [(201, 401), (202, 402)])
def test_artifact_from_an_earlier_attempt_cannot_be_reused(
    fixture: Fixture, run_id: int, artifact_id: int
) -> None:
    fixture.responses[f"/actions/artifacts/{artifact_id}"]["created_at"] = (
        NOW - timedelta(hours=3)
    ).isoformat()
    with pytest.raises(GateError, match="artifact_outside_run_attempt"):
        fixture.prepare()


def test_declared_raw_artifacts_cannot_be_omitted_from_build_provenance(
    tmp_path: Path, fixture: Fixture
) -> None:
    root = tmp_path / "build"
    image, source = build_files(root, fixture)
    provenance = json.loads((root / gate.PROVENANCE).read_bytes())
    provenance["files"] = [
        row for row in provenance["files"] if not row["path"].endswith("python-requirements.txt")
    ]
    raw = encoded(provenance)
    (root / gate.PROVENANCE).write_bytes(raw)
    fixture.data["build_provenance"] = file_ref(gate.PROVENANCE, raw)
    fixture.save()
    approval, _ = gate.load_approval(fixture.path, NOW)
    with pytest.raises(GateError, match="raw_build_evidence_missing"):
        gate.verify_build_evidence(root, approval, image, source)


@pytest.mark.parametrize(
    "name",
    [
        ".opencommerce/security-scans/final/" + item
        for item in (
            "api.scan.json",
            "api.cdx.json",
            "api.config.json",
            "api.manifest.json",
            "api.inspection.json",
        )
    ]
    + [
        ".opencommerce/source-scans/" + item
        for item in (
            "source-snapshot.json",
            "source-files.json",
            "python-requirements.txt",
            "audit.json",
            "audit.log",
            "scanner.stdout",
            "scanner.stderr",
        )
    ],
)
def test_inventory_and_provenance_cannot_disagree_on_child_bytes(
    tmp_path: Path, fixture: Fixture, name: str
) -> None:
    root = tmp_path / "build"
    image, source = build_files(root, fixture)
    replacement = b"different retained artifact"
    (root / name).write_bytes(replacement)
    provenance = json.loads((root / gate.PROVENANCE).read_bytes())
    for row in provenance["files"]:
        if row["path"] == name:
            row.update(sha256=digest(replacement), bytes=len(replacement))
    raw = encoded(provenance)
    (root / gate.PROVENANCE).write_bytes(raw)
    fixture.data["build_provenance"] = file_ref(gate.PROVENANCE, raw)
    fixture.save()
    approval, _ = gate.load_approval(fixture.path, NOW)
    with pytest.raises(GateError, match="build_inventory_child_mismatch"):
        gate.verify_build_evidence(root, approval, image, source)


@pytest.fixture
def verification(
    tmp_path: Path, fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    from scripts import check_source_assessments

    build = tmp_path / "build"
    image, source = build_files(build, fixture)
    bundle = tmp_path / "bundle-input"
    (bundle / "reviews").mkdir(parents=True)
    for name, value in (("images", image), ("source", source)):
        raw = encoded(value)
        path = f"reviews/{name}.json"
        (bundle / path).write_bytes(raw)
        fixture.data["image_review" if name == "images" else "source_review"] = file_ref(path, raw)
    marker = tmp_path / "untrusted-code-ran"
    (bundle / "scripts").mkdir()
    (bundle / "scripts/check_source_assessments.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        "raise RuntimeError('untrusted')\n"
    )
    archive = tmp_path / "release-evidence.tar"
    fixture.data["bundle_sha256"] = pack_bundle(bundle, archive)
    fixture.save()
    prepared = tmp_path / "prepared.json"
    prepared.write_text(fixture.prepare().model_dump_json())
    state: dict[str, Any] = {
        "prepared": prepared,
        "archive": archive,
        "build": build,
        "marker": marker,
        "calls": [],
        "fail": None,
    }

    def check(
        kind: str, root: Path, path: str, review_sha: str, source_sha: str, **kwargs: Any
    ) -> dict[str, Any]:
        assert root != bundle
        assert digest((root / path).read_bytes()) == review_sha
        assert source_sha == fixture.data["source_sha256"] and kwargs["now"] == NOW
        state["calls"].append(kind)
        return {"valid": kind != state["fail"], "raw_findings": 1, "release_approved": False}

    monkeypatch.setattr(gate, "verify_bundle", lambda *a, **k: check("images", *a, **k))
    monkeypatch.setattr(
        check_source_assessments, "verify_source_bundle", lambda *a, **k: check("source", *a, **k)
    )
    return state


def check_fixture(fixture: Fixture, state: dict[str, Any], now: datetime = NOW) -> dict[str, Any]:
    return gate.verify(
        fixture.path, state["prepared"], state["archive"], state["build"], now, fixture.context
    )


def test_verify_uses_both_trusted_checkers_and_does_not_execute_artifact_code(
    fixture: Fixture, verification: dict[str, Any]
) -> None:
    result = check_fixture(fixture, verification)
    assert verification["calls"] == ["images", "source"]
    assert not verification["marker"].exists()
    assert result["security_consistency_verified"] is True
    assert result["publication_approved"] is False
    assert result["candidate_commit"] == "c" * 40
    assert result["policy_commit"] == "e" * 40
    assert result["images"]["raw_findings"] == result["source"]["raw_findings"] == 1


@pytest.mark.parametrize("kind", ["images", "source"])
def test_either_assessment_failure_blocks_qualification(
    fixture: Fixture, verification: dict[str, Any], kind: str
) -> None:
    verification["fail"] = kind
    with pytest.raises(GateError, match="assessment_failed"):
        check_fixture(fixture, verification)


@pytest.mark.parametrize(
    "change", ["approval", "archive", "receipt", "stale", "replay", "reviewer"]
)
def test_verification_cannot_reuse_changed_or_wrong_run_state(
    fixture: Fixture, verification: dict[str, Any], change: str
) -> None:
    now = NOW
    if change == "approval":
        fixture.data["limitations"].append("Changed approval")
        fixture.save()
    elif change == "archive":
        with verification["archive"].open("ab") as stream:
            stream.write(b"changed archive")
    elif change == "receipt":
        verification["prepared"].write_text("{}")
    elif change == "stale":
        now += timedelta(seconds=1801)
    elif change == "replay":
        fixture.context = fixture.context.model_copy(update={"run_id": 999})
    else:
        data = json.loads(verification["prepared"].read_text())
        data["reviewer_id"] = 999
        verification["prepared"].write_bytes(encoded(data))
    with pytest.raises((ValueError, OSError)):
        check_fixture(fixture, verification, now)
    assert verification["calls"] == []


def test_pending_cli_is_content_free_and_does_not_access_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name, value in {
        "GITHUB_REPOSITORY": "example/store",
        "GITHUB_REPOSITORY_ID": "101",
        "GITHUB_RUN_ID": "203",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": "e" * 40,
        "GITHUB_REF": "refs/heads/main",
        "GH_TOKEN": "unit-test-placeholder",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        sys,
        "argv",
        ["verify_current_release", "prepare", "--prepared", str(tmp_path / "prepared.json")],
    )
    monkeypatch.setattr(gate.GitHub, "get", lambda *_: pytest.fail("unexpected network request"))
    assert gate.main() == 1
    assert json.loads(capsys.readouterr().out) == {
        "security_consistency_verified": False,
        "error": "qualification_blocked",
    }
    assert not (tmp_path / "prepared.json").exists()


def test_workflow_is_read_only_and_never_executes_artifact_sources() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/current-release-security.yml").read_text())
    assert set(workflow[True]) == {"workflow_dispatch"}
    assert workflow[True]["workflow_dispatch"] is None
    assert workflow["permissions"] == {"contents": "read", "actions": "read"}
    job = workflow["jobs"]["verify"]
    assert job["environment"] == gate.ENVIRONMENT
    assert all(not step.get("continue-on-error") for step in job["steps"])
    checkouts = [
        step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")
    ]
    assert len(checkouts) == 1
    assert checkouts[0]["with"]["ref"] == "${{ github.sha }}"
    assert checkouts[0]["with"]["persist-credentials"] is False
    downloads = [
        step
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/download-artifact@")
    ]
    assert len(downloads) == 2
    for step in downloads:
        assert step["with"]["path"].startswith("${{ runner.temp }}/")
        assert "artifact-ids" in step["with"] and "name" not in step["with"]
    upload = job["steps"][-1]["with"]["path"]
    assert "build-evidence" not in upload and "review-evidence" not in upload
    assert "security-result.json" in upload
    pending = json.loads(Path("security/current-release-approval.json").read_text())
    assert pending["status"] == "pending"
    qualification = yaml.safe_load(Path(".github/workflows/qualification.yml").read_text())
    commands = [
        step.get("run", "") for job in qualification["jobs"].values() for step in job["steps"]
    ]
    assert any("rhysd/actionlint" in command and gate.WORKFLOW in command for command in commands)
