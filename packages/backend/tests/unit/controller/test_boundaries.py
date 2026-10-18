import ast
from pathlib import Path

WRITE_ATTRS = (
    "create_discount",
    "disable_discount",
    "set_variant_prices",
    "set_campaign_budget",
    "set_search_boost",
    "no_op",
    "rollback",
)


def test_controller_provider_writes_only_live_in_executor() -> None:
    root = Path("packages/backend/src/open_commerce/controller")
    offenders: list[str] = []
    for path in root.glob("*.py"):
        if path.name in {"executor.py", "durable_executor.py"}:
            continue
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in WRITE_ATTRS:
                continue
            source = ast.get_source_segment(text, node.func) or ""
            if source.startswith("self.executor."):
                continue
            offenders.append(f"{path}:{node.func.attr}")

    assert offenders == []
