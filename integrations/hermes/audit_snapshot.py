#!/usr/bin/env python3
"""Prepare a pinned, code-only read projection; never reads the working tree.

Preparation is not an audit and never authorizes or activates a tool. Test,
evaluation, runtime, hidden and non-Python material is outside this milestone.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

from owner_setup import checked_path, private_file, settings_for

PREFIXES = ("src/lexecon/", "integrations/hermes/lexecon_gate/")
EXCLUDED = {"test", "tests", "fixtures", "eval", "evals", "evaluation", "evaluations",
            "benchmark", "benchmarks", "heldout", "held-out", "holdout", "hold-out",
            "secrets", "credentials", "runtime", "data", "private", "__pycache__"}
SECRET = re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|\bAKIA[A-Z0-9]{16}\b|"
                    rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bsk-[A-Za-z0-9_-]{32,}\b")
CHUNK_BYTES = 24 * 1024


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_allowed(name):
    path = PurePosixPath(name)
    return (name.startswith(PREFIXES) and path.suffix == ".py"
            and not any(part.startswith(".") or part.lower() in EXCLUDED for part in path.parts)
            and not path.name.startswith("test_") and "heldout" not in name.lower()
            and "held_out" not in name.lower())


def chunks(data):
    """Preserve original bytes and line numbers, splitting only at line boundaries."""
    data.decode("utf-8")
    if any(byte < 32 and byte not in (9, 10, 13) for byte in data):
        raise ValueError("non_plain_text")
    block, first, count = bytearray(), 1, 0
    for number, line in enumerate(data.splitlines(keepends=True), 1):
        if len(line) > CHUNK_BYTES:
            raise ValueError("oversized_line")
        if block and len(block) + len(line) > CHUNK_BYTES:
            yield first, count, bytes(block)
            block, first, count = bytearray(), number, 0
        block.extend(line)
        count += 1
    if block:
        yield first, count, bytes(block)


def prepare_snapshot(repo, revision, home):
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    home, _ = settings_for(home)
    commit = git(root, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}").decode().strip()
    tree = git(root, "rev-parse", f"{commit}^{{tree}}").decode().strip()
    target = home / "workspace" / "code"
    if target.exists() or (home / "private/snapshot.json").exists():
        raise ValueError("Snapshot exists; prepare a new profile instead of replacing it")
    records, excluded, blobs = [], [], []
    for raw in git(root, "ls-tree", "-rz", commit).split(b"\0"):
        if not raw:
            continue
        metadata, raw_name = raw.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        name = raw_name.decode("utf-8")
        if not source_allowed(name):
            excluded.append({"reason": "outside_explicit_code_scope"})
            continue
        if kind != "blob" or mode not in {"100644", "100755"}:
            excluded.append({"path": name, "reason": "not_regular_blob"})
            continue
        data = git(root, "cat-file", "blob", oid)
        if not data:
            excluded.append({"path": name, "reason": "empty_source", "bytes": 0,
                             "sha256": sha(data), "git_blob": oid})
            continue
        if SECRET.search(data):
            excluded.append({"path": name, "reason": "credential_pattern"})
            continue
        try:
            pieces = list(chunks(data))
        except (ValueError, UnicodeError):
            excluded.append({"path": name, "reason": "unsupported_text"})
            continue
        for first, count, content in pieces:
            # Opaque IDs preserve the existing tool's safe text-only interface.
            # This is a declared projection, not bypassing the original filesystem filter.
            relative = f"code/{len(records):05d}.txt"
            records.append({"snapshot_path": relative, "source_path": name, "line_start": first,
                            "line_end": first + count - 1, "bytes": len(content), "sha256": sha(content),
                            "source_sha256": sha(data), "git_blob": oid})
            blobs.append((relative, content))
    if not records:
        raise ValueError("No eligible source; no snapshot created")
    target.mkdir(mode=0o700)
    for relative, content in blobs:
        with (home / "workspace" / relative).open("xb") as stream:
            stream.write(content)
        os.chmod(home / "workspace" / relative, 0o400)
    os.chmod(target, 0o500)
    manifest = {"version": 1, "kind": "development_audit_input", "repository": str(root),
                "commit": commit, "tree": tree, "records": records, "excluded": excluded,
                "scope": list(PREFIXES), "heldout_evaluation": "excluded; none used or evaluated",
                "limits": "Code-only committed text; pattern checks are not comprehensive secret certification."
                          " No runtime, working-tree, test, evaluation or historical blobs are copied."}
    private_file(home / "private/snapshot.json", json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--home", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare_snapshot(checked_path(args.repo), args.revision, args.home)
    print(json.dumps({"commit": manifest["commit"], "chunks": len(manifest["records"]),
                      "excluded_files": len(manifest["excluded"]), "audit_status": "NotRun"}))


if __name__ == "__main__":
    main()
