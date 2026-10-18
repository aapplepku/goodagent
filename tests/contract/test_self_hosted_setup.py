"""First installation must not require a Python package install or reset old data."""

import base64
import errno
import io
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
from scripts import setup_self_hosted as setup


@pytest.fixture
def ports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup, "available_ports", lambda: dict(setup.PORTS))


def configuration() -> dict[str, Any]:
    environment = {
        "OPEN_COMMERCE_RUNTIME_PROFILE": "self_hosted",
        "OPEN_COMMERCE_ENCRYPTION_KEY": base64.urlsafe_b64encode(b"x" * 32).decode(),
    }
    services: dict[str, Any] = {
        name: {"environment": dict(environment)} for name in ("api", "worker", "web", "shopper")
    }
    services["postgres"] = {"environment": {"POSTGRES_PASSWORD": "synthetic@pass:/#%"}}
    for name, port in (("web", 3000), ("shopper", 3001)):
        services[name]["ports"] = [{"host_ip": "127.0.0.1", "published": str(port)}]
    return {"name": "test-installation", "services": services}


@pytest.mark.usefixtures("ports")
def test_generated_configuration_is_private_unique_and_never_overwritten(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    assert setup.prepare_environment(path)
    original = path.read_bytes()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    values = dict(line.split("=", 1) for line in original.decode().splitlines() if "=" in line)
    assert len(base64.urlsafe_b64decode(values["OPEN_COMMERCE_ENCRYPTION_KEY"])) == 32
    assert len(values["POSTGRES_PASSWORD"]) == 48
    assert values["OPEN_COMMERCE_OPENAI_API_KEY"] == ""
    assert values["OPEN_COMMERCE_RUNTIME_PROFILE"] == "self_hosted"
    assert not setup.prepare_environment(path)
    assert path.read_bytes() == original
    second = tmp_path / "second.env"
    setup.prepare_environment(second)
    assert second.read_bytes() != original


@pytest.mark.usefixtures("ports")
@pytest.mark.parametrize("interrupted", [False, True])
def test_initial_config_failure_leaves_no_partial_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interrupted: bool
) -> None:
    path = tmp_path / ".env"

    def fail_sync(descriptor: int) -> None:
        if interrupted:
            raise KeyboardInterrupt
        raise OSError(errno.ENOSPC, "Synthetic disk full")

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail_sync)
        with pytest.raises(KeyboardInterrupt if interrupted else OSError):
            setup.prepare_environment(path)
    assert not path.exists()
    assert list(tmp_path.iterdir()) == []
    assert setup.prepare_environment(path)


@pytest.mark.usefixtures("ports")
def test_partial_write_is_not_published(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / ".env"

    class PartialWriter(io.TextIOWrapper):
        def write(self, text: str) -> int:
            super().write(text[:32])
            self.flush()
            raise OSError(errno.ENOSPC, "Synthetic partial write")

    def partial_writer(descriptor: int, mode: str, *, encoding: str) -> PartialWriter:
        return PartialWriter(io.FileIO(descriptor, mode=mode), encoding=encoding)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fdopen", partial_writer)
        with pytest.raises(OSError, match="Synthetic partial write"):
            setup.prepare_environment(path)
    assert list(tmp_path.iterdir()) == []
    assert setup.prepare_environment(path)


@pytest.mark.usefixtures("ports")
def test_config_is_private_and_complete_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / ".env"
    real_link = os.link
    observed: list[bytes] = []

    def inspect_link(source: Path, destination: Path) -> None:
        assert not destination.exists()
        assert source.parent.parent == path.parent
        assert source.parent.name.startswith(".env.setup-")
        assert stat.S_IMODE(source.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(source.stat().st_mode) == 0o600
        observed.append(source.read_bytes())
        for ignore in (".gitignore", ".dockerignore"):
            assert ".env.*" in (setup.ROOT / ignore).read_text().splitlines()
        real_link(source, destination)

    monkeypatch.setattr(os, "link", inspect_link)
    assert setup.prepare_environment(path)
    assert observed == [path.read_bytes()]
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.usefixtures("ports")
@pytest.mark.parametrize("symlink", [False, True])
def test_concurrent_environment_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, symlink: bool
) -> None:
    path = tmp_path / ".env"
    target = tmp_path / "winner.env" if symlink else path
    original = "# Synthetic concurrent setup\nPOSTGRES_PASSWORD=do-not-replace\n"
    real_sync = os.fsync

    def create_winner(descriptor: int) -> None:
        real_sync(descriptor)
        target.write_text(original)
        target.chmod(0o600)
        if symlink:
            path.symlink_to(target)

    monkeypatch.setattr(os, "fsync", create_winner)
    with pytest.raises(setup.SetupError, match="appeared during setup"):
        setup.prepare_environment(path)
    assert path.read_text() == original
    assert path.is_symlink() is symlink
    assert sorted(tmp_path.iterdir()) == sorted({path, target})


@pytest.mark.usefixtures("ports")
def test_unsupported_publication_fails_without_unsafe_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / ".env"

    def fail_link(source: Path, destination: Path) -> None:
        raise OSError(errno.EOPNOTSUPP, "Synthetic unsupported filesystem")

    monkeypatch.setattr(os, "link", fail_link)
    with pytest.raises(setup.SetupError, match="hard-link support"):
        setup.prepare_environment(path)
    assert list(tmp_path.iterdir()) == []


def test_existing_settings_are_preserved_even_when_not_supported(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    original = "OPEN_COMMERCE_RUNTIME_PROFILE=legacy_demo\n# do not reset\n"
    path.write_text(original)
    path.chmod(0o600)
    assert not setup.prepare_environment(path)
    assert path.read_text() == original
    symlink = tmp_path / "linked.env"
    symlink.symlink_to(path)
    with pytest.raises(setup.SetupError, match="symlink"):
        setup.prepare_environment(symlink)
    assert path.read_text() == original


def test_unsafe_permissions_are_not_silently_rewritten(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("private setting")
    path.chmod(0o644)
    with pytest.raises(setup.SetupError, match="600"):
        setup.prepare_environment(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o644


def test_environment_cannot_enter_source_or_container_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    unsafe = tmp_path / "scripts" / "alpha.env"
    unsafe.parent.mkdir()
    with pytest.raises(setup.SetupError, match="container images"):
        setup.prepare_environment(unsafe)
    assert not unsafe.exists()
    linked = tmp_path / "alias"
    linked.symlink_to(unsafe.parent)
    with pytest.raises(setup.SetupError, match="container images"):
        setup.prepare_environment(linked / "alpha.env")


def test_ambient_demo_settings_cannot_override_file(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("OPEN_COMMERCE_RUNTIME_PROFILE", "POSTGRES_PASSWORD", "COMPOSE_FILE", "WEB_PORT"):
        monkeypatch.setenv(key, "do-not-use")
    monkeypatch.setenv("DOCKER_CONTEXT", "existing-local-engine")
    environment = setup.compose_environment()
    assert "OPEN_COMMERCE_RUNTIME_PROFILE" not in environment
    assert "POSTGRES_PASSWORD" not in environment
    assert "COMPOSE_FILE" not in environment
    assert "WEB_PORT" not in environment
    assert environment["DOCKER_CONTEXT"] == "existing-local-engine"


@pytest.mark.parametrize("profile", ["legacy_demo", "hosted"])
def test_setup_rejects_other_profiles(profile: str) -> None:
    config = configuration()
    config["services"]["api"]["environment"]["OPEN_COMMERCE_RUNTIME_PROFILE"] = profile
    with pytest.raises(setup.SetupError, match="only for self_hosted"):
        setup.validate_configuration(config)


def test_invalid_key_and_public_bindings_fail_before_launch() -> None:
    config = configuration()
    config["services"]["api"]["environment"]["OPEN_COMMERCE_ENCRYPTION_KEY"] = "invalid!"
    with pytest.raises(setup.SetupError, match="encryption key"):
        setup.validate_configuration(config)
    config = configuration()
    config["services"]["web"]["ports"][0]["host_ip"] = "0.0.0.0"
    with pytest.raises(setup.SetupError, match="loopback"):
        setup.validate_configuration(config)
    assert setup.validate_configuration(configuration()) == {"web": 3000, "shopper": 3001}


@pytest.mark.parametrize(
    "serialized,encoded",
    [
        ("synthetic$$literal", "synthetic%24literal"),
        ("synthetic$$$$literal", "synthetic%24%24literal"),
        ("$${literal}", "%24%7Bliteral%7D"),
        ("synthetic@pass:/#%", "synthetic%40pass%3A%2F%23%25"),
    ],
)
def test_database_url_decodes_exactly_one_compose_serialization_layer(
    serialized: str, encoded: str
) -> None:
    config = configuration()
    config["services"]["postgres"]["environment"]["POSTGRES_PASSWORD"] = serialized
    assert setup.encoded_database_password(config) == encoded


def test_preflight_errors_do_not_print_environment_or_docker_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["docker"], 1, "secret", "another-secret")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(setup.SetupError) as error:
        setup.captured(["docker", "info"], {})
    assert "secret" not in str(error.value)


@pytest.mark.usefixtures("ports")
def test_main_launches_with_saved_configuration_and_no_bootstrap_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / ".env"
    monkeypatch.setattr("sys.argv", ["setup", "--env-file", str(path)])
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "other-private-store")
    monkeypatch.setenv("COMPOSE_FILE", "other-private-compose.yml")
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if "up" in command:
            environment = kwargs["env"]
            assert isinstance(environment, dict)
            assert environment["POSTGRES_PASSWORD_URLENCODED"] == "synthetic%40pass%3A%2F%23%25"
        output = json.dumps(configuration()) if "config" in command else ""
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(subprocess, "run", run)
    assert setup.main() == 0
    original = path.read_bytes()
    assert setup.main() == 0
    assert path.read_bytes() == original
    assert any("--wait" in command and "--build" in command for command in commands)
    assert not any("bootstrap" in command or "down" in command for command in commands)
    assert all(str(path) in command for command in commands if "up" in command)
    assert all("--project-name" in command for command in commands if "up" in command)
    output = capsys.readouterr().out
    assert "http://localhost:3000/manager" in output
    assert "OPEN_COMMERCE_ENCRYPTION_KEY" not in output
    assert "--project-name test-installation" in output
    assert "-u COMPOSE_PROJECT_NAME" in output
    assert "-u COMPOSE_FILE" in output
    assert "other-private-store" not in output


@pytest.mark.usefixtures("ports")
def test_failed_startup_retains_configuration_and_never_removes_volumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / ".env"
    setup.prepare_environment(path)
    original = path.read_bytes()
    monkeypatch.setattr("sys.argv", ["setup", "--env-file", str(path)])
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        output = json.dumps(configuration()) if "config" in command else ""
        return subprocess.CompletedProcess(command, 1 if "up" in command else 0, output, "")

    monkeypatch.setattr(subprocess, "run", run)
    assert setup.main() == 1
    assert path.read_bytes() == original
    assert not any("down" in command or "rm" in command for command in commands)
    assert "volumes are retained" in capsys.readouterr().out


@pytest.mark.usefixtures("ports")
def test_configure_only_needs_no_docker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / ".env"
    monkeypatch.setattr("sys.argv", ["setup", "--env-file", str(path), "--configure-only"])
    monkeypatch.setenv("PATH", "")
    assert setup.main() == 0
    assert path.exists()
    assert os.stat(path).st_size > 0
