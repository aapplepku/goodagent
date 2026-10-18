"""Combined synthetic verification; only GitHub metadata is mocked, never the gates."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from scripts import verify_current_release as gate
from scripts.check_release_assessments import GateError, digest
from scripts.release_evidence_archive import pack_bundle

from .test_current_release_workflow import Fixture as GitHubFixture
from .test_current_release_workflow import encoded, file_ref
from .test_release_assessment_gate import NOW as IMAGE_NOW
from .test_release_assessment_gate import Bundle as ImageBundle
from .test_source_assessments import NOW as SOURCE_NOW
from .test_source_assessments import Bundle as SourceBundle


@dataclass
class Combined:
    root: Path
    build: Path
    github: GitHubFixture
    images: ImageBundle
    source: SourceBundle
    now: datetime

    def seal(self, label: str) -> tuple[Path, Path]:
        self.images.sign()
        self.source.sign()
        for name, bundle in (("image", self.images), ("source", self.source)):
            self.github.data[name + "_review"] = bundle.put(f"reviews/{name}.json", bundle.manifest)

        rows = []
        for directory, inventory in (
            ("scans", gate.IMAGE_INVENTORY),
            ("audit", gate.SOURCE_INVENTORY),
        ):
            prefix = Path(inventory).parent
            for path in sorted((self.root / directory).rglob("*")):
                if not path.is_file():
                    continue
                relative = prefix / path.relative_to(self.root / directory)
                raw = path.read_bytes()
                destination = self.build / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
                rows.append({"path": relative.as_posix(), "sha256": digest(raw), "bytes": len(raw)})
        build_pin = self.github.data["build"]
        provenance = encoded(
            {
                "commit_sha": build_pin["commit"],
                "expected_commit_sha": build_pin["commit"],
                "commit_matches": True,
                "run_attempt": str(build_pin["attempt"]),
                "workflow_url": (
                    f"https://github.com/{self.github.data['repository']}"
                    f"/actions/runs/{build_pin['run_id']}"
                ),
                "files": rows,
            }
        )
        path = self.build / gate.PROVENANCE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(provenance)
        self.github.data["build_provenance"] = file_ref(gate.PROVENANCE, provenance)
        archive = self.root.parent / f"{label}.tar"
        self.github.data["bundle_sha256"] = pack_bundle(self.root, archive)
        self.github.save()
        prepared = gate.prepare(self.github.path, self.github.context, self.github, self.now)
        receipt = self.root.parent / f"{label}-prepared.json"
        receipt.write_text(prepared.model_dump_json(), encoding="utf-8")
        return archive, receipt

    def verify(self, transport: tuple[Path, Path]) -> dict[str, Any]:
        archive, prepared = transport
        return gate.verify(
            self.github.path, prepared, archive, self.build, self.now, self.github.context
        )


@pytest.fixture
def combined(tmp_path: Path) -> Combined:
    root = tmp_path.resolve() / "bundle"
    images = ImageBundle(root)
    source = SourceBundle(root)
    # Share the actual frozen dependency tree, including every image proof identity.
    images.source_sha = source.source_sha
    images.manifest["source"] = copy.deepcopy(source.manifest["source"])
    for record in images.manifest["assessments"]:
        record["identity"]["source_tree_sha256"] = source.source_sha
    for proof in images.proofs["proofs"]:
        proof["identity"]["source_tree_sha256"] = source.source_sha
    # Both builders use proofs.json; keep the image document separately bound.
    image_proofs = images.put("image-proofs.json", images.proofs)
    for record in images.manifest["assessments"]:
        for evidence in record["evidence"]:
            evidence["file"] = copy.deepcopy(image_proofs)

    github = GitHubFixture(root.parent)
    now = max(IMAGE_NOW, SOURCE_NOW)
    github.data.update(
        source_sha256=source.source_sha,
        reviewed_at=now.isoformat(),
        expires_at=(now + timedelta(days=1)).isoformat(),
    )
    for name in ("build", "evidence"):
        pin = github.data[name]
        github.responses[f"/actions/runs/{pin['run_id']}/attempts/1"].update(
            run_started_at=(now - timedelta(hours=2)).isoformat(),
            updated_at=(now - timedelta(minutes=30)).isoformat(),
        )
        artifact = github.data[name + "_artifact"]
        github.responses[f"/actions/artifacts/{artifact['artifact_id']}"].update(
            created_at=(now - timedelta(hours=1)).isoformat(),
            expires_at=(now + timedelta(days=2)).isoformat(),
        )
    return Combined(root, root.parent / "build", github, images, source, now)


def test_combined_real_verifiers_retain_findings_without_publication(combined: Combined) -> None:
    transport = combined.seal("valid")
    repeated = combined.root.parent / "repeat.tar"
    assert pack_bundle(combined.root, repeated) == combined.github.data["bundle_sha256"]
    assert repeated.read_bytes() == transport[0].read_bytes()
    assert len(combined.github.calls) == 9

    result = combined.verify(transport)

    assert result["security_consistency_verified"] is True
    assert result["publication_approved"] is False
    assert result["source_sha256"] == combined.images.source_sha == combined.source.source_sha
    assert result["images"]["valid"] is True and result["source"]["valid"] is True
    assert result["images"]["services"] == 8
    assert result["images"]["raw_severity_counts"] == {"HIGH": 1}
    assert result["images"]["high_critical_assessments"] == 1
    assert result["source"]["assessments"] == 2
    assert result["source"]["rawcounts"]["records_by_raw_severity"] == {"UNKNOWN": 1, "high": 1}
    assert result["source"]["rawcounts"]["python_advisories"] == 1
    assert result["source"]["rawcounts"]["node_advisories_by_severity"]["high"] == 1
    assert json.loads((combined.root / "audit/inventory.json").read_bytes())["passed"] is False
    for key in ("images", "source"):
        assert result[key]["release_approved"] is False
        assert result[key]["rationale_truth_verified"] is False


@pytest.mark.parametrize(
    "kind,change,error",
    [
        ("images", "missing", "missing_assessment"),
        ("images", "changed", "finding_identity"),
        ("source", "missing", "assessment_coverage"),
        ("source", "changed", "record_identity"),
    ],
)
def test_consistent_transport_cannot_replace_semantic_assessment(
    combined: Combined, kind: str, change: str, error: str
) -> None:
    original = combined.seal("original")
    original_approval = combined.github.path.read_bytes()
    manifest = combined.images.manifest if kind == "images" else combined.source.manifest
    if change == "missing":
        manifest["assessments"].pop(0)
    else:
        manifest["assessments"][0]["identity"]["finding_sha256"] = "f" * 64

    # Refresh review, TAR, approval and matching mock human-comment hashes, not raw findings.
    changed = combined.seal("changed")
    assert changed[0].read_bytes() != original[0].read_bytes()
    assert combined.github.path.read_bytes() != original_approval
    assert len(combined.github.calls) == 18
    approval, _ = gate.load_approval(combined.github.path, combined.now)
    gate.verify_build_evidence(
        combined.build, approval, combined.images.manifest, combined.source.manifest
    )
    with pytest.raises(GateError, match=f"^{error}$"):
        combined.verify(changed)
