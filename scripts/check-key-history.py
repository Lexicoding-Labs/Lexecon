#!/usr/bin/env python3
"""Read-only release guard for PEM private keys in Git refs, index, and worktree.

Uses only the standard library. Prints locations, never matching key material.
This is a narrow private-key check, not a general secret scan or revocation check.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


PRIVATE_KEY = re.compile(
    rb"-----BEGIN ((?:[A-Z0-9]+ )*PRIVATE KEY)-----\s*"
    rb"[A-Za-z0-9+/=:\r\n\t ,_-]{32,}"
    rb"-----END \1-----",
)


def git(repo: Path, *arguments: str) -> bytes:
    """Run Git without a shell, leaving the repository unchanged."""
    return subprocess.check_output(
        ["git", "-C", str(repo), *arguments], stderr=subprocess.PIPE,
    )


def contains_key(data: bytes) -> bool:
    """Recognize PEM bodies, including newline-escaped JSON/string values."""
    normalized = data.replace(b"\\r", b"\r").replace(b"\\n", b"\n")
    return PRIVATE_KEY.search(normalized) is not None


def traverses_symlink(root: Path, relative: str) -> bool:
    """Exclude any symbolic link below root, including directory ancestors."""
    path = root
    for component in Path(relative).parts:
        path = path / component
        if path.is_symlink():
            return True
    return False


def scan(repo: Path) -> tuple[list[str], int]:
    """Scan every locally reachable object, staged blob, and eligible local file."""
    if git(repo, "rev-parse", "--is-shallow-repository").strip() == b"true":
        raise ValueError("Shallow history cannot establish a release check; use a full local clone.")
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip())
    findings = []
    objects = {}
    for line in git(root, "rev-list", "--objects", "--all").splitlines():
        oid, _, name = line.partition(b" ")
        objects[oid] = name.decode(errors="replace") or "(unnamed Git object)"
    # Staged content can differ from both HEAD and the working copy.
    index = []
    for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if entry:
            metadata, name = entry.split(b"\t", 1)
            mode, oid, _ = metadata.split()
            if mode != b"160000":  # Submodule repositories need their own check.
                index.append((oid, name.decode(errors="replace")))
    matches = set()
    # Batch mode avoids starting one Git process per historical object.
    all_oids = list(dict.fromkeys([*objects, *(oid for oid, _ in index)]))
    with subprocess.Popen(
        ["git", "-C", str(root), "cat-file", "--batch"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) as process:
        for oid in all_oids:
            process.stdin.write(oid + b"\n")
            process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3:
                raise ValueError("Git object unavailable; cannot complete the key check.")
            data = process.stdout.read(int(header[2]))
            if process.stdout.read(1) != b"\n":
                raise ValueError("Incomplete Git object read; cannot complete the key check.")
            if header[1] == b"blob" and contains_key(data):
                matches.add(oid)
        process.stdin.close()
        if process.wait() != 0:
            raise ValueError("Git object reader failed; cannot complete the key check.")
    for oid in matches:
        if oid in objects:
            findings.append(f"reachable history: {objects[oid]!r}")
    for oid, name in index:
        if oid in matches:
            findings.append(f"index: {name!r}")
    names = set(git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0"))
    for name in sorted(names - {b""}):
        relative = name.decode(errors="surrogateescape")
        path = root / relative
        # Check ancestors before even stat'ing the leaf; a tracked directory may
        # have been replaced by a link into private data outside the repository.
        if traverses_symlink(root, relative):
            continue
        if path.is_file() and contains_key(path.read_bytes()):
            findings.append(f"worktree: {relative!r}")
    return sorted(set(findings)), len(all_oids)


def main() -> int:
    """Return 0 for clear, 1 for findings, and 2 for incomplete checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        findings, checked = scan(args.repository)
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("INCOMPLETE: cannot inspect full repository history/index/worktree. No clear result.", file=sys.stderr)
        return 2
    if findings:
        print("BLOCKED: PEM private-key material found (contents suppressed):")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print(f"PASS: no PEM private keys in {checked} reachable/index objects or eligible worktree files.")
    print("Scope: local refs, index, tracked and non-ignored untracked files; excludes ignored runtime data,")
    print("symlink paths (including directory ancestors), remote-only refs, reflogs/unreachable objects,")
    print("submodule contents, and non-PEM secret formats.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
