"""Reject template-only attribution in the reviewed MIT/BSD notice collections.

This is an evidence check, not a determination of ownership or license compliance.
Original file hashes and provenance must be verified by the caller as well.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath
from typing import Any

# Exact omissions found in the preserved upstream sources. Do not infer authorship
# from repository usernames, Cargo authors, or a generic SPDX license template.
REVIEWED_OMISSIONS = {
    ("stumpalo", "1.0.0"): "BSD-3-Clause",
    ("block", "0.1.6"): "MIT",
    ("objc-foundation", "0.1.1"): "MIT",
    ("objc_id", "0.1.1"): "MIT",
}
# Only these previously retained original notices have been independently matched
# to their cached upstream archive. A new notice needs explicit provenance review.
REVIEWED_NOTICES = {
    ("difflib", "0.4.0"): {
        "license": "MIT",
        "path": "difflib@0.4.0/upstream-notices/LICENSE",
        "sha256": "6725d1437fc6c77301f2ff0e7d52914cf4f9509213e1078dc77d9356dbe6eac5",
        "source_url": (
            "https://codeload.github.com/DimaKudosh/difflib/tar.gz/"
            "f035fb8e656f27119e23eca9d5b996df14f3885e"
        ),
        "source_sha256": "44b22338d07873669a21f9738a085f2edbdda63892fd1c4bd9025d26af8ff6d3",
        "crate_sha256": "6184e33543162437515c2e2b48714794e37845ec9851711914eec9d308f6ebe8",
    },
    ("malloc_buf", "0.0.6"): {
        "license": "MIT",
        "path": "malloc_buf@0.0.6/upstream-notices/LICENSE",
        "sha256": "aced7b57e474a63edb5a724954222bf7659c01ceef0e648a03af799582991db7",
        "source_url": (
            "https://codeload.github.com/SSheldon/malloc_buf/tar.gz/"
            "d9a3e539642bd90e07df458d226b19cdfa606863"
        ),
        "source_sha256": "dadba54c0fa5165ba2a93debb8f02ed64b3eb3b1fd3cf8cb5883dd6ab87ba73b",
        "crate_sha256": "62bb907fe88d54d8d9ce32a3cceab4218ed2f6b7d35617cafe9adf84e43919cb",
    },
}
NOTICE_NAME = re.compile(r"(^|[._-])(licen[sc]e|notice|copying|copyright)([._-]|$)", re.IGNORECASE)
COPYRIGHT = re.compile(r"^.*copyright[^\n]+$", re.IGNORECASE | re.MULTILINE)
PLACEHOLDER = re.compile(
    r"<[^>]+>|\[[^\]]+\]|\{[^}]+\}|\b(?:yyyy|year|owner|copyright holders?)\b",
    re.IGNORECASE,
)


def original_notice_candidate(content: bytes, license_name: str) -> bool:
    """Recognize complete-text candidates; provenance still requires independent review."""
    text = content.decode("utf-8", errors="replace")
    lines = COPYRIGHT.findall(text)
    if not any(
        re.search(r"\b(?:19|20)\d{2}\b", line) and not PLACEHOLDER.search(line) for line in lines
    ):
        return False
    clauses: tuple[str, ...]
    if license_name == "MIT":
        clauses = ("permission is hereby granted", "the software is provided")
    elif license_name == "BSD-3-Clause":
        clauses = (
            "redistribution and use in source and binary forms",
            "neither the name",
            "this software is provided",
        )
    else:
        raise ValueError("unreviewed attribution license")
    normalized = " ".join(text.lower().split())
    return all(clause in normalized for clause in clauses)


def attribution_gaps(
    packages: list[dict[str, Any]], files: dict[str, bytes]
) -> list[dict[str, Any]]:
    """Inspect all template fallbacks plus known omissions, even if their labels change."""
    gaps = []
    for package in packages:
        name, version = package["name"], package["version"]
        identity = f"{name}@{version}"
        names = package["files"]
        license_name = REVIEWED_OMISSIONS.get((name, version))
        evidence = REVIEWED_NOTICES.get((name, version))
        if evidence:
            license_name = evidence["license"]
        templates = [n for n in names if PurePosixPath(n).name.endswith("-standard-template.txt")]
        for template in templates:
            declared = PurePosixPath(template).name.removesuffix("-standard-template.txt")
            if declared not in {"MIT", "BSD-3-Clause"}:
                raise ValueError(f"unreviewed attribution template: {identity}")
            if license_name is not None and license_name != declared:
                raise ValueError(f"conflicting attribution license: {identity}")
            license_name = declared
        if license_name is None:
            continue
        candidates = [
            n
            for n in names
            if n.startswith(f"{identity}/")
            and n not in templates
            and NOTICE_NAME.search(PurePosixPath(n).name)
            and original_notice_candidate(files[n], license_name)
        ]
        sources = package.get("sources", [])
        verified = (
            evidence is not None
            and evidence["path"] in candidates
            and hashlib.sha256(files[evidence["path"]]).hexdigest() == evidence["sha256"]
            and {"url": evidence["source_url"], "sha256": evidence["source_sha256"]} in sources
            and {
                "url": f"https://static.crates.io/crates/{name}/{name}-{version}.crate",
                "sha256": evidence["crate_sha256"],
            }
            in sources
        )
        if not verified:
            gaps.append(
                {
                    "package": identity,
                    "license": license_name,
                    "decision": "blocked",
                    "reason": (
                        "No reviewed, source-bound original copyright and full license notice; "
                        "template or unreviewed text is not attribution"
                    ),
                    "retained_files": sorted(names),
                    "sources": package.get("sources", []),
                    "next_action": (
                        "Obtain an authentic version-applicable upstream notice with provenance, "
                        "or separately review a distribution that does not include "
                        "this component's source/binary."
                    ),
                }
            )
    return gaps


def require_attribution(packages: list[dict[str, Any]], files: dict[str, bytes]) -> None:
    gaps = attribution_gaps(packages, files)
    if gaps:
        raise ValueError("Missing upstream attribution: " + ", ".join(g["package"] for g in gaps))
