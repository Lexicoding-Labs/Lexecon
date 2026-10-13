"""Source artifacts must exclude local state and preserve committed bytes."""

import hashlib
import importlib.util
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("package_source", Path(__file__).parents[1] / "scripts/package-source.py")
PACKAGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGER)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.name", "Source fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    (root / "README.md").write_text("committed source\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture")
    return root


def test_archive_contains_committed_bytes_only_and_is_reproducible(repo, tmp_path):
    (repo / "README.md").write_text("staged change\n")
    git(repo, "add", "README.md")
    (repo / "README.md").write_text("working change\n")
    (repo / ".env").write_text("fixture-only local data")
    (repo / "local.db").write_bytes(b"fixture-only runtime data")
    before = git(repo, "status", "--porcelain")
    archive, manifest, result = PACKAGER.package(repo, "HEAD", tmp_path / "one")
    second, _, duplicate = PACKAGER.package(repo, "HEAD", tmp_path / "two")
    assert archive.read_bytes() == second.read_bytes()
    assert result == duplicate
    assert json.loads(manifest.read_text())["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    with tarfile.open(archive) as bundle:
        assert len(bundle.getmembers()) == 1
        member = bundle.getmembers()[0]
        assert member.name.endswith("/README.md")
        assert bundle.extractfile(member).read() == b"committed source\n"
    assert git(repo, "status", "--porcelain") == before
    with pytest.raises(ValueError, match="already exists"):
        PACKAGER.package(repo, "HEAD", tmp_path / "one")


@pytest.mark.parametrize("name", [
    ".env", "local.db", "lexecon_keys/config.txt", "secrets/config.txt",
    "local.db-wal", "local.db-shm", "local.db-journal", "local.sqlite", "local.sqlite3",
    "local.sqlite-wal", "local.sqlite3-wal", "local.SQLITE3-SHM",
])
def test_committed_runtime_files_are_rejected(repo, tmp_path, name):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fixture only")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "runtime fixture")
    with pytest.raises(ValueError, match="sensitive filename"):
        PACKAGER.package(repo, "HEAD", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_binary_bytes_executable_modes_and_manifest_match_commit(repo, tmp_path):
    executable = repo / "run.sh"
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    binary = b"\x00\xff\x80\r\n\x00"
    (repo / "asset.bin").write_bytes(binary)
    git(repo, "add", ".")
    git(repo, "update-index", "--chmod=+x", "run.sh")
    git(repo, "commit", "-qm", "binary and executable fixtures")
    committed_modes = {"README.md": 0o644, "run.sh": 0o755, "asset.bin": 0o644}
    archive, manifest, result = PACKAGER.package(repo, "HEAD", tmp_path / "out")
    listed = {item["path"]: item for item in json.loads(manifest.read_text())["files"]}
    assert set(listed) == set(committed_modes)
    assert result["commit"] == git(repo, "rev-parse", "HEAD").decode().strip()
    assert result["tree"] == git(repo, "rev-parse", "HEAD^{tree}").decode().strip()
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            relative = member.name.split("/", 1)[1]
            content = bundle.extractfile(member).read()
            assert member.isfile()
            assert member.mode == committed_modes[relative]
            assert content == git(repo, "show", f"HEAD:{relative}")
            assert listed[relative]["bytes"] == len(content)
            assert listed[relative]["sha256"] == hashlib.sha256(content).hexdigest()


def test_symbolic_links_are_rejected(repo, tmp_path):
    (repo / "link").symlink_to("README.md")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "link fixture")
    with pytest.raises(ValueError, match="link/submodule"):
        PACKAGER.package(repo, "HEAD", tmp_path / "out")


def test_embedded_pem_is_rejected_without_echoing_material(repo, tmp_path):
    fixture = "-----BEGIN PRIVATE KEY-----\n" + "A" * 64 + "\n-----END PRIVATE KEY-----"
    (repo / "example.txt").write_text(fixture)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "synthetic PEM fixture")
    with pytest.raises(ValueError, match="PEM private key") as caught:
        PACKAGER.package(repo, "HEAD", tmp_path / "out")
    assert fixture not in str(caught.value)
