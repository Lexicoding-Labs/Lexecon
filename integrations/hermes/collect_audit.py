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
from pathlib import Path
from uuid import uuid4

from owner_setup import private_file, read_private_json, settings_for
from required_runtime import initialize_required_runtime


def append_journal(path, row):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def collect_reads(dispatch, records, destination):
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
                or hashlib.sha256(content.encode()).hexdigest() != record["sha256"]):
            raise RuntimeError("Returned source does not match pinned content; attempt remains Unknown")
        private_file(destination / "reads" / f"{read_id}.txt", content)
        observed = {**common, "state": "ObservedRead", "decision_id": identifier,
                    "evidence_file": f"reads/{read_id}.txt"}
        append_journal(journal, observed)
        successes.append(observed)
    return successes


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
    identity = runtime.LoopbackClient(settings["session_file"], 8765).for_call().whoami().get("user", {})
    if identity.get("username") != settings["username"] or identity.get("role") != "viewer":
        raise SystemExit("Dedicated isolated viewer login required")
    destination = home / "private" / ("audit-run-" + uuid4().hex)
    print("Evidence directory: " + str(destination), flush=True)
    reads = collect_reads(host.model_tools.handle_function_call, selected, destination)
    # Every successful read must have a corresponding handler completion record.
    audit_path = Path(settings["audit_file"])
    filesystem = importlib.import_module(host.plugin.__name__ + ".filesystem")
    with filesystem.open_private_file(audit_path) as fd:
        if os.fstat(fd).st_size > 4 * 1024 * 1024:
            raise RuntimeError("Audit log exceeds collection bound; preserve evidence for independent review")
        rows = [json.loads(row) for row in os.read(fd, 4 * 1024 * 1024 + 1).splitlines()]
    correlated = []
    for observed in reads:
        matches = [row for row in rows if row.get("decision_id") == observed["decision_id"]]
        if [row.get("outcome") for row in matches] != ["authorized", "completed"]:
            raise RuntimeError("Incomplete gate correlation; preserve attempts as evidence, not a completed audit")
        correlated.extend(matches)
    evidence = {"version": 1, "commit": manifest["commit"], "tree": manifest["tree"],
                "snapshot_sha256": args.manifest_sha256,
                "reads": reads, "gate_records": correlated,
                "transport": "authenticated_live_loopback_127.0.0.1:8765",
                "scope": "Source collection only; findings require human review; not held-out evaluation",
                "limits": "Local journals are not externally attested; service identity is not pinned"}
    private_file(destination / "evidence.json", json.dumps(evidence, indent=2) + "\n")
    private_file(destination / "findings.json", json.dumps({"status": "AwaitingReview", "findings": []}) + "\n")
    print(json.dumps({"state": "CollectedAwaitingReview", "reads": len(reads), "commit": manifest["commit"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
