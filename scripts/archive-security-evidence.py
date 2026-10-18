"""Create a compact, hash-addressed archive of complete local scanner evidence."""

import argparse
import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    image_inventory = json.loads((args.images / "inventory.json").read_bytes())
    source_inventory = json.loads((args.source / "inventory.json").read_bytes())
    dispositions = json.loads((args.images / "dispositions.json").read_bytes())
    if not all(
        (
            image_inventory.get("complete"),
            source_inventory.get("complete"),
            source_inventory.get("passed"),
            dispositions.get("passed"),
        )
    ):
        raise SystemExit("do not archive incomplete or failed evidence as a qualified scan set")
    if args.output.exists():
        raise SystemExit("evidence output already exists; use a new version instead of overwriting")
    if hashlib.sha256(args.proof.read_bytes()).hexdigest() != dispositions.get(
        "runtime_proof_sha256"
    ):
        raise SystemExit("runtime evidence no longer matches the checked disposition")
    assessment = Path("security/image-assessments.json")
    if hashlib.sha256(assessment.read_bytes()).hexdigest() != dispositions["assessment_sha256"]:
        raise SystemExit("applicability assessment changed after checking images")
    args.output.mkdir(parents=True)
    files = {
        "images/inventory.json": args.images / "inventory.json",
        "images/dispositions.json": args.images / "dispositions.json",
        "images/runtime-proof.json": args.proof,
        "images/assessments.json": Path("security/image-assessments.json"),
        "source/inventory.json": args.source / "inventory.json",
        "source/source-files.json": args.source / "source-files.json",
        "source/python-requirements.txt": args.source / "python-requirements.txt",
    }
    if "reviewed_records_sha256" in dispositions:
        reviewed = Path("security/reviewed-image-findings.json")
        if (
            hashlib.sha256(reviewed.read_bytes()).hexdigest()
            != dispositions["reviewed_records_sha256"]
        ):
            raise SystemExit("per-record assessments changed after checking images")
        files["images/reviewed-findings.json"] = reviewed
    for item in image_inventory["images"]:
        for key in ("scan", "sbom"):
            path = args.images / item[key]
            if hashlib.sha256(path.read_bytes()).hexdigest() != item[f"{key}_sha256"]:
                raise SystemExit(f"{item['service']}: evidence hash changed")
            files[f"images/{path.name}"] = path
    for item in source_inventory["reports"]:
        path = args.source / item["report"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise SystemExit(f"{path.name}: evidence hash changed")
        files[f"source/{path.name}"] = path
    records = []
    for name, source in sorted(files.items()):
        data = source.read_bytes()
        target = args.output / f"{name}.gz"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(gzip.compress(data, mtime=0))
        records.append(
            {
                "path": str(target.relative_to(args.output)),
                "uncompressed_sha256": hashlib.sha256(data).hexdigest(),
                "compressed_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    (args.output / "manifest.json").write_text(
        json.dumps(
            {
                "format": "gzip with mtime=0; original reports unmodified",
                "recorded_at": datetime.now(UTC).isoformat(),
                "files": records,
                "scope": (
                    "local qualification evidence; not publication or an independent certification"
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(f"Archived {len(records)} evidence files to {args.output}")


if __name__ == "__main__":
    main()
