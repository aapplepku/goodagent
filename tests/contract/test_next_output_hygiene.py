"""Local Next output stays out of Git and lint without hiding app source."""

import shutil
import subprocess
from pathlib import Path

import pytest
from scripts.export_public_source import omission

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = (".next", ".next-local", ".next-self-service-qa", ".next-entry-preview")


@pytest.mark.parametrize("app", ["web", "shopper"])
def test_next_outputs_are_not_source(tmp_path: Path, app: str) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    shutil.copyfile(ROOT / ".gitignore", tmp_path / ".gitignore")
    paths = [f"apps/{app}/{output}/server/runtime.js" for output in OUTPUTS]
    source = f"apps/{app}/src/app/page.tsx"
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=tmp_path,
        input="\n".join([*paths, source]) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.splitlines() == paths
    assert all(omission(path) for path in paths)
    assert omission(source) is None


@pytest.mark.parametrize("app", ["web", "shopper"])
def test_next_outputs_are_not_linted(app: str) -> None:
    node = shutil.which("node")
    assert node, "Node.js is required to verify Next output exclusions"
    assert (ROOT / "node_modules/eslint").exists(), "Install locked workspace dependencies first"
    subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            """
import assert from 'node:assert/strict';
import { ESLint } from 'eslint';
const lint = new ESLint();
for (const output of process.argv.slice(1)) {
  assert.equal(await lint.isPathIgnored(`${output}/server/runtime.js`), true, output);
}
assert.equal(await lint.isPathIgnored('src/app/page.tsx'), false);
""",
            *OUTPUTS,
        ],
        cwd=ROOT / "apps" / app,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
