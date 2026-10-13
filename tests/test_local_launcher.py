"""Exercise setup ordering and dependency reconciliation without accounts or servers."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("local_launcher", ROOT / "scripts/start-local.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "shutil_which", lambda program: f"/mock/{program}")
    binaries = tmp_path / ".venv/bin"
    binaries.mkdir(parents=True)
    for name in ("python", "uvicorn"):
        (binaries / name).touch()
    return module


def test_existing_python_environment_is_reconciled_with_lock(launcher, monkeypatch):
    calls = []
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "/outside/project")
    monkeypatch.setattr(launcher.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))
    launcher.ensure_dependencies(include_frontend=False)
    args, kwargs = calls[0]
    assert args == ["uv", "sync", "--locked", "--extra", "dev"]
    assert kwargs["env"]["UV_PROJECT_ENVIRONMENT"] == str(launcher.ROOT / ".venv")
    assert "LEXECON_ADMIN_PASSWORD" not in kwargs["env"]
    assert not (launcher.ROOT / ".lexecon").exists()


def test_sync_failure_stops_before_data_initialization(launcher, monkeypatch):
    def failed_sync(args, **kwargs):
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(launcher.subprocess, "run", failed_sync)
    with pytest.raises(RuntimeError, match="Locked Python dependency setup failed"):
        launcher.ensure_dependencies(include_frontend=False)
    assert not (launcher.ROOT / ".lexecon").exists()


def test_uv_is_required_even_when_old_environment_exists(launcher, monkeypatch):
    monkeypatch.setattr(launcher, "shutil_which", lambda _: None)
    with pytest.raises(RuntimeError, match="reconcile the locked Python environment"):
        launcher.ensure_dependencies(include_frontend=False)


def test_browser_lock_change_reconciles_existing_node_modules(launcher, monkeypatch):
    frontend = launcher.ROOT / "frontend"
    binaries = frontend / "node_modules/.bin"
    binaries.mkdir(parents=True)
    (binaries / "react-scripts").touch()
    (frontend / "package.json").write_text('{"name":"fixture"}')
    lock = frontend / "package-lock.json"
    lock.write_text('{"lockfileVersion":3}')
    calls = []
    monkeypatch.setattr(launcher.subprocess, "run", lambda args, **kwargs: calls.append(args))
    launcher.ensure_dependencies()
    launcher.ensure_dependencies()
    assert sum(args[0] == "npm" for args in calls) == 1
    lock.write_text('{"lockfileVersion":3,"fixtureChanged":true}')
    launcher.ensure_dependencies()
    assert sum(args[0] == "npm" for args in calls) == 2
    assert all(args == ["npm", "ci", "--no-audit", "--no-fund"] for args in calls if args[0] == "npm")


@pytest.mark.parametrize("failure", ["build", "dependencies", None])
def test_native_build_and_dependencies_precede_any_account_setup(launcher, monkeypatch, failure):
    calls = []
    monkeypatch.setattr(sys, "argv", ["start-local.py", "--macos"])
    monkeypatch.setattr(launcher, "check_port", lambda _: None)

    def build(args, **kwargs):
        calls.append("build")
        if failure == "build":
            raise subprocess.CalledProcessError(1, args)

    def dependencies(**kwargs):
        calls.append("dependencies")
        assert kwargs == {"include_frontend": False}
        if failure == "dependencies":
            raise RuntimeError("dependency failure")
        return launcher.ROOT / ".venv/bin/python", launcher.ROOT / ".venv/bin/uvicorn"

    def data(*args):
        calls.append("data")
        # Stop at this boundary: never create an account or start a server.
        raise RuntimeError("data boundary reached")

    monkeypatch.setattr(launcher.subprocess, "run", build)
    monkeypatch.setattr(launcher, "ensure_dependencies", dependencies)
    monkeypatch.setattr(launcher, "prepare_data", data)
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        launcher.main()
    expected = ["build"] if failure == "build" else ["build", "dependencies"]
    if failure is None:
        expected.append("data")
    assert calls == expected
    assert not (launcher.ROOT / ".lexecon").exists()


def test_missing_environment_after_uv_success_is_actionable(launcher, monkeypatch):
    (launcher.ROOT / ".venv/bin/uvicorn").unlink()
    monkeypatch.setattr(launcher.subprocess, "run", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="did not produce"):
        launcher.ensure_dependencies(include_frontend=False)
