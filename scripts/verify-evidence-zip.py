#!/usr/bin/env python3
"""Rehash a saved evidence ZIP without claiming source-chain authenticity."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def verify(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP contains a corrupt member")
        manifest = json.loads(archive.read("manifest.json"))
        events = json.loads(archive.read("ledger_events.json"))["events"]
        for item in manifest["bundle_files"]:
            if hashlib.sha256(archive.read(item["path"])).hexdigest() != item["sha256"]:
                raise ValueError(f"Manifest file hash mismatch: {item['path']}")
        file_hashes = "".join(
            item["sha256"] for item in sorted(manifest["bundle_files"], key=lambda x: x["path"])
        )
        if hashlib.sha256(file_hashes.encode()).hexdigest() != manifest["bundle_hash"]:
            raise ValueError("Bundle hash mismatch")
        for event in events:
            content = {
                key: event[key]
                for key in ("entry_id", "event_type", "data", "timestamp", "previous_hash")
            }
            actual = hashlib.sha256(
                json.dumps(content, sort_keys=True, separators=(",", ":")).encode(),
            ).hexdigest()
            if actual != event["entry_hash"]:
                raise ValueError(f"Event hash mismatch: {event['entry_id']}")
    return {
        "manifest_files_rehashed": len(manifest["bundle_files"]),
        "events_rehashed": len(events),
        "source_chain_continuity": "not checked; exported subset can omit entries",
        "signature_authenticity": "not checked; compare against a trusted public key separately",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.zip_path), indent=2))


if __name__ == "__main__":
    main()
