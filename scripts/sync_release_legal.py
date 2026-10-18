"""Copy canonical first-party legal documents into package distribution roots."""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("packages/backend", "packages/sdk-typescript", "apps/web", "apps/shopper")
FILES = ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for package in PACKAGES:
        for name in FILES:
            source = (ROOT / name).read_bytes()
            destination = ROOT / package / name
            if args.check:
                if not destination.exists() or destination.read_bytes() != source:
                    raise SystemExit(f"stale package legal file: {package}/{name}")
            else:
                destination.write_bytes(source)


if __name__ == "__main__":
    main()
