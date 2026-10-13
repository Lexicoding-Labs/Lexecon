#!/usr/bin/env python3
"""Package one committed tree, never the index, runtime data, or Git ancestry.

This is a bounded source-release guard, not a comprehensive secret scanner.
"""

import argparse
import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
from pathlib import Path, PurePosixPath


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)


def package(repo, revision, output):
    root = Path(repo).resolve()
    commit = git(root, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}").decode().strip()
    tree = git(root, "rev-parse", f"{commit}^{{tree}}").decode().strip()
    timestamp = int(git(root, "show", "-s", "--format=%ct", commit))
    spec = importlib.util.spec_from_file_location("key_guard", Path(__file__).with_name("check-key-history.py"))
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    excluded_parts = {".git", ".lexecon", ".venv", "node_modules", "__pycache__", "lexecon_keys", "secrets"}
    product_roots = {
        ".gitattributes", ".github", ".gitignore", "CONTRIBUTING.md", "LICENSE", "README.md",
        "SECURITY.md", "docs", "examples", "frontend", "integrations", "macos",
        "model_governance_pack", "pyproject.toml", "scripts", "setup_security.py", "src",
        "tests", "uv.lock",
    }
    product_docs = {"docs/architecture.md", "docs/architecture.svg", "docs/walkthrough.md"}
    non_product_paths = {
        "integrations/hermes/audit_snapshot.py", "integrations/hermes/collect_audit.py",
        "integrations/hermes/free_route.py", "integrations/hermes/package_audit_input.py",
        "integrations/hermes/run_free_audit.py", "integrations/hermes/start_audit_service.py",
        "integrations/hermes/tests/test_audit_workflow.py",
        "integrations/hermes/tests/test_free_audit_hermes.py",
        "integrations/hermes/tests/test_free_route.py",
    }
    # SQLite write-ahead logs can contain the same private records as the database.
    sqlite_suffixes = tuple(
        extension + sidecar
        for extension in (".db", ".sqlite", ".sqlite3")
        for sidecar in ("", "-wal", "-shm", "-journal")
    )
    entries = []
    for entry in git(root, "ls-tree", "-r", "-z", commit).split(b"\0"):
        if not entry:
            continue
        metadata, name_bytes = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        name = name_bytes.decode("utf-8")
        path = PurePosixPath(name)
        if mode not in {b"100644", b"100755"} or kind != b"blob":
            raise ValueError(f"Unsupported source entry (link/submodule): {name}")
        if (path.is_absolute() or ".." in path.parts or set(path.parts) & excluded_parts
                or path.name.startswith(".env") or path.name.lower().endswith(sqlite_suffixes)
                or path.suffix in {".key", ".ledger"}
                or path.name in {"id_rsa", "id_ed25519", "private_key.pem"}):
            raise ValueError(f"Runtime or sensitive filename in committed tree: {name}")
        if (path.parts[0] == "docs" and name not in product_docs) or path.suffix.lower() in {
            ".mp4", ".mov", ".webm"
        }:
            raise ValueError(f"Non-product documentation or media in committed tree: {name}")
        if path.parts[0] not in product_roots:
            raise ValueError(f"Non-product top-level path in committed tree: {name}")
        if name in non_product_paths:
            raise ValueError(f"Non-product integration tooling in committed tree: {name}")
        data = git(root, "cat-file", "blob", oid.decode())
        if guard.contains_key(data):
            raise ValueError(f"PEM private key detected in committed tree: {name}")
        entries.append((name, mode, data))
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    prefix = f"lexecon-{commit[:12]}"
    archive = output / f"{prefix}.tar"
    manifest = output / f"{prefix}.json"
    # Exclusive creation avoids replacing an existing deliverable or user file.
    if archive.exists() or manifest.exists():
        raise ValueError("Output already exists; select another output directory.")
    files = []
    with archive.open("xb") as stream:
        with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as bundle:
            for name, mode, data in entries:
                info = tarfile.TarInfo(f"{prefix}/{name}")
                info.size = len(data)
                info.mode = 0o755 if mode == b"100755" else 0o644
                info.mtime = timestamp
                bundle.addfile(info, io.BytesIO(data))
                files.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    result = {
        "commit": commit, "tree": tree, "archive": archive.name,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "files": files,
        "scope": "Exact committed regular files only; no index/worktree changes or Git history. PEM and filename checks are not comprehensive secret certification.",
    }
    with manifest.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return archive, manifest, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        archive, manifest, result = package(args.repo, args.commit, args.output)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Source packaging failed: {error}\n")
    print(f"Commit: {result['commit']}\nFiles: {len(result['files'])}\nArchive: {archive}\nSHA-256: {result['sha256']}\nManifest: {manifest}")


if __name__ == "__main__":
    main()
