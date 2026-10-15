"""Disposable owner-run enforcement validation, separate from source audit collection."""

import json
import importlib
import os
from pathlib import Path
from uuid import uuid4

from collect_audit import append_journal
from verify_live import parsed, require


def replay_probe(client, settings):
    root = Path(settings["workspace_root"])
    info = root.stat()
    arguments = {"workspace_root": str(root), "workspace_device": info.st_dev,
                 "workspace_inode": info.st_ino, "path": "welcome.txt"}
    decision = client.post("/decide", {"actor": settings["username"], "proposed_action": "read",
                                     "tool": "lexecon_read_file", "tool_arguments": arguments,
                                     "user_intent": "Disposable validation of single-use grant"})
    require(decision.get("decision") == "permit", "replay_probe_not_permitted")
    payload = {"capability_token": decision.get("capability_token"), "action": "read",
               "tool": "lexecon_read_file", "tool_arguments": arguments, "consume": True}
    first = client.post("/capability/verify", payload)
    second = client.post("/capability/verify", payload)
    require(first == {"valid": True, "consumed": True}, "initial_consumption_not_confirmed")
    require(second == {"valid": False, "consumed": False}, "grant_replay_not_rejected")
    return {"decision_id": decision["decision_id"], "consumed_once": True, "replay_rejected": True}


def zero_effect_probe(host):
    """An unapproved host tool is actually dispatched; its only effect is an in-memory counter."""
    from tools.registry import registry

    name = "audit_write_sentinel_" + uuid4().hex
    scope = str(host.home)
    effects = []

    def sentinel(args, **kwargs):
        effects.append(True)
        return json.dumps({"unexpected_execution": True})

    registry.register(name=name, toolset="audit_validation", schema={}, handler=sentinel, scope=scope)
    registered = registry.snapshot_registration(name, scope=scope)
    require(registered is not None and registered.handler is sentinel, "sentinel_registration_failed")
    try:
        result = parsed(host.model_tools.handle_function_call(
            name, {"operation": "write"}, skip_pre_tool_call_hook=True,
            skip_tool_request_middleware=True, skip_tool_execution_middleware=True,
        ))
        direct = parsed(registry.dispatch(name, {"operation": "write"}, scope=scope))
        require(result.get("error") and direct.get("error") and not effects, "unapproved_handler_executed")
        return {"attempted_host_dispatch": True, "attempted_direct_dispatch": True, "effects": len(effects)}
    finally:
        registry.restore_registration(name, registered, None, scope=scope)


def reconcile_interruption(before, after, ledger, expected_digest):
    """Resolve only the fresh request bound to this probe's unique arguments."""
    old_requests = {row.get("request_id") for row in before}
    fresh = [row for row in after if row.get("request_id") not in old_requests]
    # The controlled probe is serialized. Any competing or incomplete request makes correlation ambiguous.
    request_ids = {row.get("request_id") for row in fresh}
    requested = [row for row in fresh if row.get("outcome") == "requested"]
    if len(request_ids) != 1 or len(requested) != 1:
        return {"state": "Unknown"}
    if (requested[0].get("tool") != "lexecon_read_file"
            or requested[0].get("action") != "read"
            or requested[0].get("arguments_digest") != expected_digest):
        return {"state": "Unknown"}
    completed = [row for row in fresh if row.get("outcome") == "completed"
                 and row.get("tool") == "lexecon_read_file"]
    if len(completed) != 1:
        return {"state": "Unknown"}
    done = completed[0]
    if (not isinstance(done.get("request_id"), str) or not done["request_id"]
            or not isinstance(done.get("arguments_digest"), str) or len(done["arguments_digest"]) != 64
            or not isinstance(done.get("decision_id"), str) or not done["decision_id"]):
        return {"state": "Unknown"}
    matching = [row for row in fresh if row.get("decision_id") == done.get("decision_id")]
    if ([row.get("outcome") for row in matching] != ["authorized", "completed"]
            or any(row.get("request_id") != done["request_id"]
                   or row.get("arguments_digest") != expected_digest
                   or row.get("tool") != "lexecon_read_file" for row in matching)):
        return {"state": "Unknown"}
    entries = ledger.get("entries") if isinstance(ledger, dict) else None
    if not isinstance(entries, list):
        return {"state": "Unknown"}
    decisions = [entry.get("data", {}) for entry in entries if entry.get("event_type") == "decision"]
    if not any(row.get("decision_id") == done.get("decision_id") and row.get("decision") == "permit"
               and row.get("request_id") == done.get("request_id")
               and row.get("arguments_digest") == expected_digest for row in decisions):
        return {"state": "Unknown"}
    return {"state": "ObservedCompletedRead", "decision_id": done["decision_id"],
            "basis": "fresh gate audit plus authenticated service ledger; no lost-response inference"}


def interruption_probe(host, client, read_audit):
    runtime = importlib.import_module(host.plugin.__name__ + ".runtime")
    filesystem = importlib.import_module(host.plugin.__name__ + ".filesystem")
    root = Path(host.settings["workspace_root"])
    name = "validation-" + uuid4().hex + ".txt"
    journal = host.home / "private" / ("validation-interruption-" + uuid4().hex + ".jsonl")
    journal.touch(mode=0o600, exist_ok=False)
    with filesystem.open_directory(root) as root_fd:
        info = os.fstat(root_fd)
        digest = runtime.arguments_digest({"workspace_root": str(root),
                                           "workspace_device": info.st_dev,
                                           "workspace_inode": info.st_ino, "path": name})
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                     dir_fd=root_fd)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(b"Disposable read-only enforcement validation.\n")
                stream.flush()
                os.fsync(stream.fileno())
            before = read_audit()
            append_journal(journal, {"state": "Unknown", "kind": "controlled_response_loss_validation",
                                     "arguments_digest": digest})
            # The returned content is deliberately discarded; the resolver cannot use it.
            host.model_tools.handle_function_call("lexecon_read_file", {"path": name})
            resolution = reconcile_interruption(before, read_audit(), client.ledger_entries(), digest)
        finally:
            os.unlink(name, dir_fd=root_fd)
    append_journal(journal, resolution)
    require(resolution["state"] == "ObservedCompletedRead", "interruption_remains_unknown")
    return {"initial": "Unknown", **resolution, "journal": journal.name}
