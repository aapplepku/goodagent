import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = ROOT / "packages" / "backend" / "src" / "open_commerce" / "core"

FORBIDDEN_PREFIXES = (
    "fastapi",
    "httpx",
    "langgraph",
    "qdrant_client",
    "requests",
    "shopify",
    "starlette",
)


def imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


def test_core_domain_does_not_import_forbidden_dependencies() -> None:
    violations: list[str] = []
    for path in CORE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        forbidden = sorted(imported_roots(tree).intersection(FORBIDDEN_PREFIXES))
        if forbidden:
            violations.append(f"{path.relative_to(ROOT)} imports {', '.join(forbidden)}")

    assert violations == []
