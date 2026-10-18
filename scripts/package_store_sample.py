"""Repackage the existing attributed ABO fixture for reviewed offline onboarding."""

import csv
import hashlib
import io
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/datasets/amazon-berkeley-objects"
TARGET = ROOT / "packages/backend/src/open_commerce/stores/sample_data"


def main() -> None:
    with (SOURCE / "catalog.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    with (SOURCE / "image-sources.csv").open(newline="") as stream:
        images = {row["product_id"]: row for row in csv.DictReader(stream)}
    TARGET.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for row in rows:
        product = row["product_id"]
        image = images[product]
        filename = f"{product}.jpg"
        source = ROOT / "apps/web/public/abo-images" / filename
        assert hashlib.sha256(source.read_bytes()).hexdigest() == image["sha256"]
        shutil.copyfile(source, TARGET / filename)
        manifest[product] = {
            "filename": filename,
            "sha256": image["sha256"],
            "source_url": image["source_url"],
            "license": image["license"],
        }
        row["image_url"] = f"sample-abo:{product}"
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (TARGET / "catalog.csv").write_text(output.getvalue())
    (TARGET / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    shutil.copyfile(SOURCE / "LICENSE-CC-BY-4.0.txt", TARGET / "LICENSE-CC-BY-4.0.txt")
    print(f"Packaged {len(rows)} sample products with verified image hashes.")


if __name__ == "__main__":
    main()
