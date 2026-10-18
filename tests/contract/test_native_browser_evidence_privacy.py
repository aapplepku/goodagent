"""Native authentication traces must not default into hosted upload directories."""

import ast
from pathlib import Path


def browser_call() -> ast.Call:
    tree = ast.parse(Path("tests/integration/test_self_service_browser.py").read_text())
    # The synthetic image-cache test also launches a subprocess, without auth data.
    # Keep these privacy assertions bound to the actual authenticated browser test.
    [browser_test] = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "test_self_service_browser"
    ]
    calls = [
        node
        for node in ast.walk(browser_test)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == "run"
    ]
    [call] = calls
    return call


def test_native_browser_raw_output_is_not_written_to_workflow_console() -> None:
    keywords = {item.arg: item.value for item in browser_call().keywords}
    for name in ("stdout", "stderr"):
        assert ast.unparse(keywords[name]) == "browser_log"


def test_native_browser_trace_default_is_private_temporary_directory() -> None:
    calls = [
        node
        for node in ast.walk(browser_call())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "getenv"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "OPEN_COMMERCE_E2E_OUTPUT"
    ]
    [call] = calls
    assert ast.unparse(call.args[1]) == "str(tmp_path / 'browser')"
