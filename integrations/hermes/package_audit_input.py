#!/usr/bin/env python3
"""Package prepared source only. Never include a session, database, key or live evidence claim."""

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path

from owner_setup import private_file, read_private_json, settings_for


def package(home, output):
    home, _ = settings_for(home)
    manifest = read_private_json(home / "private/snapshot.json")
    payloads = {"manifest.json": (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode(),
                "status.json": (json.dumps({"audit": "NotRun", "live_acceptance": "NotRun", "findings": [],
                                             "purpose": "Prepared input, not completed audit evidence"},
                                            indent=2) + "\n").encode()}
    for row in manifest["records"]:
        path = row["snapshot_path"]
        if not path.startswith("code/") or len(Path(path).parts) != 2 or not path.endswith(".txt"):
            raise ValueError("Invalid projected source path")
        file = home / "workspace" / path
        if file.is_symlink():
            raise ValueError("Snapshot symlinks are not supported")
        content = file.read_bytes()
        if hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise ValueError("Snapshot content changed; no package created")
        payloads["snapshot/" + path] = content
    output.mkdir(mode=0o700)
    archive = output / "prepared-audit-input.tar"
    with archive.open("xb") as stream:
        with tarfile.open(fileobj=stream, mode="w") as bundle:
            for name, content in sorted(payloads.items()):
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(content), 0o400, 0
                bundle.addfile(info, io.BytesIO(content))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    private_file(output / "package.json", json.dumps({"archive": archive.name, "sha256": digest,
                                                       "commit": manifest["commit"], "status": "PreparedNotRun",
                                                       "members": len(payloads)}, indent=2) + "\n")
    return {"archive": str(archive), "sha256": digest, "members": len(payloads)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.home, args.output)))
