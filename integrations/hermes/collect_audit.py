#!/usr/bin/env python3
"""Owner-approved gated source collection; preparation alone never runs this.

The journal records Unknown before dispatch. Exceptions or interruption leave it
Unknown; only independently reviewed evidence may resolve an uncertain attempt.
"""

import argparse
import hashlib
import importlib
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from owner_setup import private_file, read_private_json, settings_for
from required_runtime import initialize_required_runtime


def append_journal(path, row):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def collect_reads(dispatch, records, destination, corroborate=None):
    """Collect only actual returned content; this seam makes no authentication claim."""
    destination.mkdir(mode=0o700)
    (destination / "reads").mkdir(mode=0o700)
    journal = destination / "attempts.jsonl"
    journal.touch(mode=0o600, exist_ok=False)
    successes = []
    for record in records:
        read_id = uuid4().hex
        common = {"read_id": read_id, **record}
        append_journal(journal, {**common, "state": "Unknown"})
        result = dispatch("lexecon_read_file", {"path": record["snapshot_path"]})
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError("Read not confirmed; attempt remains Unknown")
        content = result.get("content")
        identifier = result.get("decision_id")
        if (not isinstance(content, str) or not isinstance(identifier, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier)
                or hashlib.sha256(content.encode()).hexdigest() != record["sha256"]):
            raise RuntimeError("Returned source does not match pinned content; attempt remains Unknown")
        proof = corroborate(record, identifier) if corroborate is not None else {}
        private_file(destination / "reads" / f"{read_id}.txt", content)
        observed = {**common, "state": "ObservedRead", "decision_id": identifier,
                    "evidence_file": f"reads/{read_id}.txt", **proof}
        append_journal(journal, observed)
        successes.append(observed)
    return successes


def correlate_read(decision_id, audit_rows, ledger, expected_digest, actor):
    """Require one completed gate attempt and its matching authenticated decision."""
    completed = [row for row in audit_rows if row.get("decision_id") == decision_id]
    if ([row.get("outcome") for row in completed] != ["authorized", "completed"]
            or not isinstance(completed[0].get("request_id"), str)
            or not completed[0]["request_id"]):
        raise RuntimeError("Incomplete gate correlation; attempt remains Unknown")
    request_id = completed[0]["request_id"]
    gate = [row for row in audit_rows if row.get("request_id") == request_id]
    if ([row.get("outcome") for row in gate] != ["requested", "authorized", "completed"]
            or [row.get("reason") for row in gate] != ["policy_check", "grant_consumed", "success"]
            or any(row.get("tool") != "lexecon_read_file" or row.get("action") != "read"
                   or row.get("arguments_digest") != expected_digest for row in gate)
            or gate[0].get("decision_id") is not None
            or any(row.get("decision_id") != decision_id for row in gate[1:])):
        raise RuntimeError("Incomplete gate correlation; attempt remains Unknown")
    entries = ledger.get("entries") if isinstance(ledger, dict) else None
    if not isinstance(entries, list):
        raise RuntimeError("Decision ledger unavailable; attempt remains Unknown")
    matching = [entry for entry in entries if isinstance(entry, dict)
                and isinstance(entry.get("data"), dict)
                and entry["data"].get("decision_id") == decision_id]
    if len(matching) != 1:
        raise RuntimeError("Decision ledger mismatch; attempt remains Unknown")
    entry = matching[0]
    data = entry["data"]
    if (entry.get("event_type") != "decision"
            or data.get("decision") != "permit" or data.get("actor") != actor
            or data.get("action") != "read" or data.get("tool") != "lexecon_read_file"
            or data.get("request_id") != request_id
            or data.get("arguments_digest") != expected_digest
            or data.get("evaluation_source") != "policy_engine"
            or not isinstance(entry.get("entry_hash"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", entry["entry_hash"])):
        raise RuntimeError("Decision ledger mismatch; attempt remains Unknown")
    hashed = {key: entry.get(key) for key in
              ("entry_id", "event_type", "data", "timestamp", "previous_hash")}
    canonical = json.dumps(hashed, sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(canonical.encode()).hexdigest() != entry["entry_hash"]:
        raise RuntimeError("Decision ledger hash mismatch; attempt remains Unknown")
    return {"gate_records": gate, "ledger_entry": entry}


def validate_findings(report, evidence):
    """Check traceability only; a reviewer must still assess the finding's claim."""
    by_id = {row["read_id"]: row for row in evidence["reads"] if row["state"] == "ObservedRead"}
    for finding in report["findings"]:
        if not finding.get("claim") or not finding.get("references"):
            raise ValueError("Every finding needs a claim and gated source references")
        for ref in finding["references"]:
            observed = by_id.get(ref.get("read_id"))
            if (observed is None or ref.get("revision") != evidence["commit"]
                    or ref.get("path") != observed["source_path"]
                    or type(ref.get("line_start")) is not int or type(ref.get("line_end")) is not int
                    or not observed["line_start"] <= ref["line_start"] <= ref["line_end"] <= observed["line_end"]):
                raise ValueError("Finding is not supported by a collected revision/path/line range")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--hermes-checkout", required=True, type=Path)
    parser.add_argument("--manifest-sha256", required=True, help="Independently reviewed snapshot SHA-256")
    parser.add_argument("--source", action="append", required=True, help="Exact original source path in snapshot")
    args = parser.parse_args(argv)
    home, settings = settings_for(args.home)
    if settings.get("api_port") != 8765:
        raise SystemExit("Audit collection requires the isolated port-8765 profile")
    manifest = read_private_json(home / "private/snapshot.json", expected_sha256=args.manifest_sha256)
    selected = [row for row in manifest["records"] if row["source_path"] in args.source]
    if {row["source_path"] for row in selected} != set(args.source):
        raise SystemExit("One or more requested source paths are outside the pinned snapshot")
    host = initialize_required_runtime(home, args.hermes_checkout)
    runtime = importlib.import_module(host.plugin.__name__ + ".runtime")
    # Confirms an authenticated live identity before any source collection starts.
    client = runtime.LoopbackClient(settings["session_file"], 8765).for_call()
    identity = client.whoami().get("user", {})
    if identity.get("username") != settings["username"] or identity.get("role") != "viewer":
        raise SystemExit("Dedicated isolated viewer login required")
    destination = home / "private" / ("audit-run-" + uuid4().hex)
    print("Evidence directory: " + str(destination), flush=True)
    audit_path = Path(settings["audit_file"])
    filesystem = importlib.import_module(host.plugin.__name__ + ".filesystem")
    initial_size = 0
    if audit_path.exists():
        with filesystem.open_private_file(audit_path) as fd:
            initial_size = os.fstat(fd).st_size
        if initial_size > 4 * 1024 * 1024:
            raise RuntimeError("Audit log exceeds collection bound; preserve evidence for independent review")

    def corroborate(record, decision_id):
        with filesystem.open_private_file(audit_path) as fd:
            size = os.fstat(fd).st_size
            if size < initial_size or size > 4 * 1024 * 1024:
                raise RuntimeError("Audit log changed outside collection bound; attempt remains Unknown")
            os.lseek(fd, initial_size, os.SEEK_SET)
            rows = [json.loads(row) for row in os.read(fd, size - initial_size).splitlines()]
        root = Path(settings["workspace_root"])
        root_info = root.stat()
        expected = runtime.arguments_digest({"workspace_root": str(root),
                                             "workspace_device": root_info.st_dev,
                                             "workspace_inode": root_info.st_ino,
                                             "path": record["snapshot_path"]})
        return correlate_read(decision_id, rows, client.ledger_entries(), expected, settings["username"])

    reads = collect_reads(host.model_tools.handle_function_call, selected, destination, corroborate)
    evidence = {"version": 2, "commit": manifest["commit"], "tree": manifest["tree"],
                "snapshot_sha256": args.manifest_sha256,
                "reads": reads,
                "transport": "authenticated_live_loopback_127.0.0.1:8765",
                "scope": "Source collection only; findings require human review; not held-out evaluation",
                "limits": "Local journals are not externally attested; service identity is not pinned"}
    private_file(destination / "evidence.json", json.dumps(evidence, indent=2) + "\n")
    private_file(destination / "findings.json", json.dumps({"status": "AwaitingReview", "findings": []}) + "\n")
    print(json.dumps({"state": "CollectedAwaitingReview", "reads": len(reads), "commit": manifest["commit"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
