"""Guard the locked Alembic template dependency against GHSA-5639-2j2p-m4mx."""

import ntpath
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import Script
from mako import exceptions, template  # type: ignore[import-untyped]


@pytest.mark.parametrize(
    "uri",
    [
        "C:/../../../outside.txt",
        "C:\\..\\..\\..\\outside.txt",
        "d:/../../../outside.txt",
        "//../../outside.txt",
        "\\..\\..\\outside.txt",
        "../../outside.txt",
    ],
)
def test_windows_template_uri_cannot_escape_its_root(
    monkeypatch: pytest.MonkeyPatch, uri: str
) -> None:
    # Only Mako's os reference changes; pytest and other modules keep host paths.
    monkeypatch.setattr(template, "os", SimpleNamespace(path=ntpath))
    with pytest.raises(exceptions.TemplateLookupException):
        template.Template(text="synthetic content only", uri=uri)


def test_safe_template_still_renders_under_windows_path_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(template, "os", SimpleNamespace(path=ntpath))
    result = template.Template(text="synthetic content only", uri="templates/revision.txt")
    assert result.render() == "synthetic content only"


def test_alembic_still_generates_a_revision_from_its_template(tmp_path: Path) -> None:
    config = Config(str(tmp_path / "alembic.ini"))
    migrations = tmp_path / "migrations"
    config.set_main_option("script_location", str(migrations))
    command.init(config, str(migrations))

    revision = command.revision(config, message="synthetic patch smoke", rev_id="patch_smoke")

    assert isinstance(revision, Script)
    assert revision.revision == "patch_smoke"
    assert revision.down_revision is None
    assert Path(revision.path).is_relative_to(migrations)
    assert "def upgrade()" in Path(revision.path).read_text()
    assert "def downgrade()" in Path(revision.path).read_text()
