"""Read-only hosted security verification of a separately adopted evidence bundle.

Run only from the protected default-branch checkout, never from an artifact. The
pending approval is deliberately unusable. This tool neither creates approvals nor
publishes anything; successful security consistency checks are not release approval.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, ValidationError

from scripts.check_release_assessments import (
    BundleReader,
    Digest,
    FileRef,
    GateError,
    SafeParser,
    ShortText,
    StrictModel,
    Timestamp,
    date_window,
    digest,
    require,
    strict_json,
    utc_time,
    verify_bundle,
)

PositiveID = Annotated[int, Field(gt=0, le=2**53 - 1)]
Commit = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
Repository = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")]
ENVIRONMENT = "alpha-security-review"
WORKFLOW = ".github/workflows/current-release-security.yml"
IMAGE_INVENTORY = ".opencommerce/security-scans/final/inventory.json"
SOURCE_INVENTORY = ".opencommerce/source-scans/inventory.json"
PROVENANCE = ".opencommerce/ci-evidence/provenance.json"


class RunPin(StrictModel):
    run_id: PositiveID
    attempt: PositiveID
    workflow_id: PositiveID
    workflow_path: Annotated[str, Field(pattern=r"^\.github/workflows/[a-zA-Z0-9_-]+\.yml$")]
    commit: Commit


class ArtifactPin(StrictModel):
    artifact_id: PositiveID
    name: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")]
    digest: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    size: Annotated[int, Field(gt=0, le=300 * 1024 * 1024)]


class Approval(StrictModel):
    schema_version: Literal[1]
    status: Literal["approved"]
    repository: Repository
    repository_id: PositiveID
    environment_id: PositiveID
    reviewer_ids: Annotated[list[PositiveID], Field(min_length=1, max_length=6)]
    review_owner: ShortText
    reviewed_at: Timestamp
    expires_at: Timestamp
    source_sha256: Digest
    build: RunPin
    build_artifact: ArtifactPin
    build_provenance: FileRef
    evidence: RunPin
    evidence_artifact: ArtifactPin
    bundle_sha256: Digest
    image_review: FileRef
    source_review: FileRef
    limitations: Annotated[list[ShortText], Field(min_length=1, max_length=64)]


class Context(StrictModel):
    repository: Repository
    repository_id: PositiveID
    run_id: PositiveID
    run_attempt: PositiveID
    event: Literal["workflow_dispatch"]
    policy_commit: Commit
    ref: ShortText


class Prepared(StrictModel):
    schema_version: Literal[1]
    approval_sha256: Digest
    policy_commit: Commit
    verification_run_id: PositiveID
    verified_at: Timestamp
    reviewer_id: PositiveID
    security_approved: Literal[False]


def load_approval(path: Path, now: datetime) -> tuple[Approval, str]:
    require(path.is_file() and not path.is_symlink(), "approval_missing")
    raw = path.read_bytes()
    data = strict_json(raw)
    require(isinstance(data, dict) and data.get("status") == "approved", "approval_pending")
    approval = Approval.model_validate(data)
    date_window(approval.reviewed_at, approval.expires_at, now)
    require(len(set(approval.reviewer_ids)) == len(approval.reviewer_ids), "duplicate_reviewer")
    return approval, digest(raw)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        raise GateError("github_redirect_refused")


class GitHub:
    """GET only, fixed origin, no inherited proxy, no token in URLs or diagnostics."""

    def __init__(self, repository: str, token: str) -> None:
        require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)), "repository")
        require(bool(token) and "\n" not in token and "\r" not in token, "github_token_missing")
        self.prefix = f"https://api.github.com/repos/{repository}"
        self.token = token
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def get(self, suffix: str) -> Any:
        require(suffix == "" or suffix.startswith("/"), "github_endpoint")
        request = urllib.request.Request(
            self.prefix + suffix,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "open-commerce-release-verifier",
            },
            method="GET",
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                require(response.status == 200, "github_response")
                raw = response.read(4 * 1024 * 1024 + 1)
            require(len(raw) <= 4 * 1024 * 1024, "github_response_budget")
            return strict_json(raw)
        except (OSError, urllib.error.URLError):
            raise GateError("github_read_failed") from None


def workflow_path_matches(actual: Any, expected: str, branch: Any, commit: str) -> bool:
    if not isinstance(actual, str):
        return False
    path, separator, ref = actual.partition("@")
    if path != expected:
        return False
    if not separator:
        return True
    allowed = {commit}
    if (
        isinstance(branch, str)
        and re.fullmatch(r"[A-Za-z0-9_./-]{1,255}", branch)
        and ".." not in branch
        and "//" not in branch
    ):
        allowed.update((branch, f"refs/heads/{branch}"))
    return ref in allowed


def verify_run(approval: Approval, pin: RunPin, data: Any) -> tuple[datetime, datetime]:
    require(isinstance(data, dict), "run_metadata")
    require(
        data.get("id") == pin.run_id
        and data.get("run_attempt") == pin.attempt
        and data.get("workflow_id") == pin.workflow_id
        and workflow_path_matches(
            data.get("path"), pin.workflow_path, data.get("head_branch"), pin.commit
        )
        and data.get("head_sha") == pin.commit
        and data.get("status") == "completed"
        and data.get("conclusion") == "success"
        and data.get("event") in {"push", "workflow_dispatch"}
        and data.get("repository", {}).get("id") == approval.repository_id
        and data.get("head_repository", {}).get("id") == approval.repository_id,
        "wrong_or_unsuccessful_run",
    )
    started, finished = utc_time(data["run_started_at"]), utc_time(data["updated_at"])
    require(started <= finished <= approval.reviewed_at, "run_dates")
    return started, finished


def verify_artifact(
    approval: Approval,
    run: RunPin,
    pin: ArtifactPin,
    data: Any,
    now: datetime,
    run_window: tuple[datetime, datetime],
) -> None:
    require(isinstance(data, dict), "artifact_metadata")
    require(
        data.get("id") == pin.artifact_id
        and data.get("name") == pin.name
        and data.get("digest") == pin.digest
        and data.get("size_in_bytes") == pin.size
        and data.get("expired") is False
        and data.get("workflow_run", {}).get("id") == run.run_id
        and data["workflow_run"].get("repository_id") == approval.repository_id
        and data["workflow_run"].get("head_repository_id") == approval.repository_id
        and data["workflow_run"].get("head_sha") == run.commit,
        "artifact_identity",
    )
    require(utc_time(data["expires_at"]) > now, "artifact_expired")
    require(
        run_window[0] <= utc_time(data["created_at"]) <= run_window[1],
        "artifact_outside_run_attempt",
    )


def prepare(approval_path: Path, context: Context, github: GitHub, now: datetime) -> Prepared:
    approval, checksum = load_approval(approval_path, now)
    require(
        approval.repository == context.repository
        and approval.repository_id == context.repository_id
        and context.run_attempt == 1,
        "context_or_rerun",
    )
    repository = github.get("")
    default = repository["default_branch"]
    require(
        repository["id"] == approval.repository_id and context.ref == f"refs/heads/{default}",
        "default_branch_required",
    )
    branch = github.get("/branches/" + urllib.parse.quote(default, safe=""))
    require(
        branch.get("protected") is True and branch["commit"]["sha"] == context.policy_commit,
        "policy_branch_changed_or_unprotected",
    )
    current = github.get(f"/actions/runs/{context.run_id}/attempts/1")
    require(
        workflow_path_matches(current.get("path"), WORKFLOW, default, context.policy_commit)
        and current.get("head_sha") == context.policy_commit
        and current.get("head_branch") == default
        and current.get("event") == "workflow_dispatch"
        and current.get("run_attempt") == 1
        and current.get("id") == context.run_id
        and current.get("repository", {}).get("id") == approval.repository_id
        and current.get("head_repository", {}).get("id") == approval.repository_id,
        "verification_run_identity",
    )
    environment = github.get(f"/environments/{ENVIRONMENT}")
    require(
        environment.get("id") == approval.environment_id
        and environment.get("name") == ENVIRONMENT
        and environment.get("deployment_branch_policy")
        == {"protected_branches": True, "custom_branch_policies": False},
        "unprotected_environment",
    )
    users = {
        r["reviewer"]["id"]
        for rule in environment.get("protection_rules", [])
        if rule.get("type") == "required_reviewers"
        for r in rule.get("reviewers", [])
        if r.get("type") == "User"
    }
    require(bool(users & set(approval.reviewer_ids)), "required_reviewer_missing")
    reviews = github.get(f"/actions/runs/{context.run_id}/approvals")
    require(isinstance(reviews, list), "review_history")
    matching = [
        row
        for row in reviews
        if row.get("comment") == f"security-review:{checksum}"
        and row.get("user", {}).get("id") in users & set(approval.reviewer_ids)
        and row["user"].get("type") == "User"
        and any(e.get("id") == approval.environment_id for e in row.get("environments", []))
    ]
    require(
        len(matching) == 1 and matching[0].get("state") == "approved",
        "explicit_environment_approval_missing",
    )
    for run, artifact in (
        (approval.build, approval.build_artifact),
        (approval.evidence, approval.evidence_artifact),
    ):
        window = verify_run(
            approval, run, github.get(f"/actions/runs/{run.run_id}/attempts/{run.attempt}")
        )
        verify_artifact(
            approval,
            run,
            artifact,
            github.get(f"/actions/artifacts/{artifact.artifact_id}"),
            now,
            window,
        )
    return Prepared(
        schema_version=1,
        approval_sha256=checksum,
        policy_commit=context.policy_commit,
        verification_run_id=context.run_id,
        verified_at=now,
        reviewer_id=matching[0]["user"]["id"],
        security_approved=False,
    )


def verify_build_evidence(root: Path, approval: Approval, image: Any, source: Any) -> None:
    reader = BundleReader(root)
    try:
        require(approval.build_provenance.path == PROVENANCE, "build_provenance_path")
        provenance = reader.document(approval.build_provenance)
        require(
            provenance.get("commit_sha") == approval.build.commit
            and provenance.get("expected_commit_sha") == approval.build.commit
            and provenance.get("commit_matches") is True
            and str(provenance.get("run_attempt")) == str(approval.build.attempt)
            and provenance.get("workflow_url")
            == f"https://github.com/{approval.repository}/actions/runs/{approval.build.run_id}",
            "build_provenance_identity",
        )
        files: dict[str, FileRef] = {}
        for item in provenance["files"]:
            path = item["path"]
            if path.startswith(
                (".opencommerce/source-scans/", ".opencommerce/security-scans/final/")
            ):
                ref = FileRef(path=path, sha256=item["sha256"], size=item["bytes"])
                require(path not in files, "duplicate_build_artifact")
                reader.bound(ref)
                files[path] = ref
        for path, manifest in ((IMAGE_INVENTORY, image), (SOURCE_INVENTORY, source)):
            require(path in files, "missing_build_inventory")
            reviewed = FileRef.model_validate(manifest["inventory"])
            require(
                files[path].sha256 == reviewed.sha256 and files[path].size == reviewed.size,
                "wrong_build_inventory",
            )

        def bound_child(path: str, checksum: str) -> None:
            require(path in files, "raw_build_evidence_missing")
            require(files[path].sha256 == checksum, "build_inventory_child_mismatch")

        image_inventory = reader.document(files[IMAGE_INVENTORY])
        image_prefix = IMAGE_INVENTORY.rsplit("/", 1)[0] + "/"
        for item in image_inventory["images"]:
            for key in ("scan", "sbom"):
                bound_child(image_prefix + item[key], item[key + "_sha256"])
            for identity_input in item["identity_inputs"].values():
                bound_child(image_prefix + identity_input["file"], identity_input["sha256"])
        source_inventory = reader.document(files[SOURCE_INVENTORY])
        source_prefix = SOURCE_INVENTORY.rsplit("/", 1)[0] + "/"
        snapshot = source_inventory["snapshot"]
        bound_child(source_prefix + snapshot["manifest"], snapshot["sha256"])
        bound_child(source_prefix + "source-files.json", snapshot["source_files_sha256"])
        bound_child(
            source_prefix + "python-requirements.txt", source_inventory["requirements_sha256"]
        )
        for item in source_inventory["reports"]:
            bound_child(source_prefix + item["report"], item["sha256"])
            if "log" in item:
                bound_child(source_prefix + item["log"], item["log_sha256"])
        for item in source_inventory["tool_version_evidence"].values():
            for key in ("stdout", "stderr"):
                bound_child(source_prefix + item[key], item[key + "_sha256"])
        reader.recheck()
    finally:
        reader.close()


def verify(
    approval_path: Path,
    prepared_path: Path,
    archive: Path,
    build_artifact: Path,
    now: datetime,
    context: Context,
) -> dict[str, Any]:
    from scripts.check_source_assessments import verify_source_bundle
    from scripts.release_evidence_archive import unpack_bundle

    approval, checksum = load_approval(approval_path, now)
    prepared = Prepared.model_validate(strict_json(prepared_path.read_bytes()))
    require(prepared.approval_sha256 == checksum, "approval_changed")
    require(
        prepared.policy_commit == context.policy_commit
        and prepared.verification_run_id == context.run_id
        and prepared.reviewer_id in approval.reviewer_ids
        and approval.repository == context.repository
        and approval.repository_id == context.repository_id
        and context.run_attempt == 1,
        "prepared_context",
    )
    require(approval.reviewed_at <= prepared.verified_at, "prepared_predates_review")
    require(0 <= (now - prepared.verified_at).total_seconds() <= 1800, "prepared_expired")
    with tempfile.TemporaryDirectory(prefix="release-security-") as temporary:
        root = Path(temporary).resolve() / "bundle"
        unpack_bundle(archive, root, approval.bundle_sha256)
        reader = BundleReader(root)
        try:
            image = reader.document(approval.image_review)
            source = reader.document(approval.source_review)
        finally:
            reader.close()
        verify_build_evidence(build_artifact, approval, image, source)
        images = verify_bundle(
            root,
            approval.image_review.path,
            approval.image_review.sha256,
            approval.source_sha256,
            now=now,
        )
        sources = verify_source_bundle(
            root,
            approval.source_review.path,
            approval.source_review.sha256,
            approval.source_sha256,
            now=now,
        )
        require(images.get("valid") is True and sources.get("valid") is True, "assessment_failed")
    return {
        "schema_version": 1,
        "security_consistency_verified": True,
        "publication_approved": False,
        "candidate_commit": approval.build.commit,
        "source_sha256": approval.source_sha256,
        "bundle_sha256": approval.bundle_sha256,
        "approval_sha256": checksum,
        "policy_commit": prepared.policy_commit,
        "verification_run_id": prepared.verification_run_id,
        "images": images,
        "source": sources,
        "limitations": list(approval.limitations),
    }


def main() -> int:
    parser = SafeParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "verify"])
    parser.add_argument(
        "--approval", type=Path, default=Path("security/current-release-approval.json")
    )
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--build-artifact", type=Path)
    try:
        args = parser.parse_args()
        now = datetime.now(UTC)
        context = Context(
            repository=os.environ["GITHUB_REPOSITORY"],
            repository_id=int(os.environ["GITHUB_REPOSITORY_ID"]),
            run_id=int(os.environ["GITHUB_RUN_ID"]),
            run_attempt=int(os.environ["GITHUB_RUN_ATTEMPT"]),
            event=os.environ["GITHUB_EVENT_NAME"],  # type: ignore[arg-type]
            policy_commit=os.environ["GITHUB_SHA"],
            ref=os.environ["GITHUB_REF"],
        )
        if args.phase == "prepare":
            github = GitHub(context.repository, os.environ.get("GH_TOKEN", ""))
            prepared = prepare(args.approval, context, github, now)
            with args.prepared.open("x", encoding="utf-8") as stream:
                stream.write(prepared.model_dump_json(indent=2) + "\n")
            approval, _ = load_approval(args.approval, now)
            with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
                for key, value in {
                    "build_run": approval.build.run_id,
                    "build_artifact": approval.build_artifact.artifact_id,
                    "evidence_run": approval.evidence.run_id,
                    "evidence_artifact": approval.evidence_artifact.artifact_id,
                }.items():
                    stream.write(f"{key}={value}\n")
            print(json.dumps({"prepared": True, "security_approved": False}))
        else:
            require(
                args.archive is not None and args.build_artifact is not None, "missing_artifacts"
            )
            print(
                json.dumps(
                    verify(
                        args.approval,
                        args.prepared,
                        args.archive,
                        args.build_artifact,
                        now,
                        context,
                    )
                )
            )
        return 0
    except (GateError, ValidationError, OSError, ValueError, KeyError, TypeError, AttributeError):
        print(
            json.dumps({"security_consistency_verified": False, "error": "qualification_blocked"})
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
