"""Use synthetic PEM-shaped fixtures; never copy actual signing keys into tests."""

import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-key-history.py"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def fixture_key():
    # Deliberately not a valid cryptographic key, but a complete PEM-shaped body.
    kind = "PRIVATE" + " KEY"
    payload = base64.b64encode(b"synthetic-key-fixture-not-secret" * 3).decode()
    return f"-----BEGIN {kind}-----\n{payload}\n-----END {kind}-----\n"


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.com")
    (tmp_path / "README.md").write_text("No private material.\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "initial")
    return tmp_path


def check(repo):
    result = subprocess.run([sys.executable, str(SCRIPT), str(repo)], capture_output=True, text=True)
    assert base64.b64encode(b"synthetic-key-fixture-not-secret" * 3).decode() not in result.stdout + result.stderr
    return result


def test_clear_and_public_material(repo):
    (repo / "public.pem").write_text(fixture_key().replace("PRIVATE", "PUBLIC"))
    assert check(repo).returncode == 0


def test_deleted_key_remains_blocked_in_history(repo):
    (repo / "renamed.txt").write_text(fixture_key())
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture")
    git(repo, "rm", "renamed.txt")
    git(repo, "commit", "-m", "remove fixture")
    result = check(repo)
    assert result.returncode == 1
    assert "reachable history: 'renamed.txt'" in result.stdout


def test_other_branch_history_is_checked(repo):
    git(repo, "checkout", "-b", "fixture-branch")
    (repo / "fixture.txt").write_text(fixture_key())
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture")
    git(repo, "checkout", "main")
    assert check(repo).returncode == 1


def test_staged_key_cannot_be_hidden_by_clean_worktree(repo):
    (repo / "staged.txt").write_text(fixture_key())
    git(repo, "add", "staged.txt")
    (repo / "staged.txt").write_text("clean again")
    result = check(repo)
    assert result.returncode == 1
    assert "index: 'staged.txt'" in result.stdout


@pytest.mark.parametrize("filename", ["README.md", "untracked.txt"])
def test_unstaged_and_untracked_keys_are_checked(repo, filename):
    (repo / filename).write_text(fixture_key().replace("\n", "\\n"))
    result = check(repo)
    assert result.returncode == 1
    assert f"worktree: '{filename}'" in result.stdout


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("location", ["worktree", "history"])
def test_json_encoded_pem_line_endings_are_checked(repo, newline, location):
    path = repo / "encoded.json"
    path.write_text(json.dumps({"key": fixture_key().replace("\n", newline)}))
    if location == "history":
        git(repo, "add", "encoded.json")
        git(repo, "commit", "-m", "encoded fixture")
        git(repo, "rm", "encoded.json")
        git(repo, "commit", "-m", "remove encoded fixture")
    result = check(repo)
    assert result.returncode == 1
    assert f"{location}: 'encoded.json'" in result.stdout


def test_ignored_runtime_key_and_external_symlink_are_not_read(repo):
    (repo / ".gitignore").write_text("runtime/\n")
    (repo / "runtime").mkdir()
    (repo / "runtime" / "key.pem").write_text(fixture_key())
    (repo / "link.pem").symlink_to(repo / "runtime" / "key.pem")
    assert check(repo).returncode == 0


@pytest.mark.parametrize("relative_directory", ["tracked", "nested/tracked"])
def test_tracked_directory_replaced_by_external_symlink_is_not_read(
    repo, tmp_path_factory, relative_directory,
):
    directory = repo / relative_directory
    directory.mkdir(parents=True)
    leaf = directory / "file.txt"
    leaf.write_text("Clean tracked file.\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "clean tracked directory")
    outside = tmp_path_factory.mktemp("external-private-data")
    (outside / "file.txt").write_text(fixture_key())
    leaf.unlink()
    directory.rmdir()
    directory.symlink_to(outside, target_is_directory=True)
    result = check(repo)
    assert result.returncode == 0
    assert "directory ancestors" in result.stdout


def test_encrypted_traditional_pem_is_blocked(repo):
    pem = fixture_key().replace("PRIVATE KEY", "RSA PRIVATE KEY")
    header, body = pem.split("\n", 1)
    (repo / "encrypted.txt").write_text(
        header + "\nProc-Type: 4,ENCRYPTED\nDEK-Info: AES-256-CBC,0123456789ABCDEF\n\n" + body,
    )
    assert check(repo).returncode == 1


def test_shallow_repository_never_reports_clear(repo, tmp_path_factory):
    clone = tmp_path_factory.mktemp("shallow") / "clone"
    subprocess.run(["git", "clone", "--depth", "1", repo.as_uri(), str(clone)], check=True, capture_output=True)
    result = check(clone)
    assert result.returncode == 2
    assert "INCOMPLETE" in result.stderr
