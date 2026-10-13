#!/usr/bin/env python3
"""Owner-run live acceptance after setup; creates no accounts or credentials.

Uses actual Hermes discovery and dispatch, without a model/provider request.
This script reads only the prepared welcome fixture through protected tools.
"""

import argparse
import contextlib
import importlib
import io
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from owner_setup import settings_for
from required_runtime import initialize_required_runtime

WELCOME = "Welcome to the isolated Lexecon workspace.\n"
TOOLS = {"lexecon_list_files", "lexecon_read_file"}


class ProofError(Exception):
    """Fixed, secret-free acceptance failure."""


def require(condition, reason):
    if not condition:
        raise ProofError(reason)


def parsed(value):
    if isinstance(value, str):
        value = json.loads(value)
    require(isinstance(value, dict), "malformed_dispatch_result")
    return value


def decision_id(result):
    value = result.get("decision_id")
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value),
            "missing_decision_id")
    return value


def run_proof(dispatch, client, read_audit, username):
    """Pure orchestration seam, tested with fake dispatcher/API (no live sessions)."""
    identity = client.whoami()
    user = identity.get("user") if isinstance(identity, dict) else None
    require(isinstance(user, dict) and user.get("username") == username
            and user.get("role") in {"viewer", "auditor", "compliance_officer"},
            "dedicated_nonadmin_identity_required")
    listing = parsed(dispatch("lexecon_list_files", {"path": "."}))
    require(listing.get("ok") is True, "list_not_permitted")
    require(isinstance(listing.get("entries"), list)
            and {"name": "welcome.txt", "type": "file"} in listing["entries"],
            "welcome_fixture_missing")
    list_id = decision_id(listing)
    reading = parsed(dispatch("lexecon_read_file", {"path": "welcome.txt"}))
    require(reading.get("ok") is True and reading.get("content") == WELCOME,
            "welcome_read_failed_or_fixture_changed")
    read_id = decision_id(reading)
    require(list_id != read_id, "duplicate_decision_id")
    traversal = parsed(dispatch("lexecon_read_file", {"path": "../outside.txt"}))
    require(traversal.get("ok") is False and traversal.get("error") == "path_not_allowed",
            "traversal_not_blocked")
    # This is a policy request only. No delete handler or filesystem mutation exists here.
    denied = client.post("/decide", {
        "request_id": str(uuid4()), "actor": username, "proposed_action": "delete",
        "tool": "lexecon_read_file", "tool_arguments": {"path": "welcome.txt"},
        "user_intent": "Owner acceptance: prove an unmapped action is denied without executing it",
    })
    require(isinstance(denied, dict) and denied.get("decision") == "deny"
            and denied.get("capability_token") is None, "delete_policy_not_denied")
    denied_id = decision_id(denied)
    records = read_audit()
    for identifier, name in ((list_id, "lexecon_list_files"), (read_id, "lexecon_read_file")):
        correlated = [record for record in records if record.get("decision_id") == identifier
                      and record.get("tool") == name]
        require([record.get("outcome") for record in correlated] == ["authorized", "completed"],
                "missing_or_unexpected_audit_sequence")
        require(correlated[0].get("reason") == "grant_consumed"
                and correlated[1].get("reason") == "success"
                and correlated[0].get("request_id") == correlated[1].get("request_id")
                and isinstance(correlated[0].get("request_id"), str)
                and correlated[0].get("arguments_digest") == correlated[1].get("arguments_digest")
                and isinstance(correlated[0].get("arguments_digest"), str),
                "audit_correlation_failed")
    require(any(record.get("tool") == "lexecon_read_file"
                and record.get("outcome") == "blocked"
                and record.get("reason") == "path_not_allowed" for record in records),
            "traversal_audit_missing")
    return {
        "ok": True, "scope": "two bounded tools via actual Hermes dispatch; no model turn",
        "permitted": {"list_decision_id": list_id, "read_decision_id": read_id},
        "denied": {"traversal": "path_not_allowed", "delete_policy_decision_id": denied_id},
        "audit": "grant consumption and completion correlated for both permitted calls",
        "limits": "does not prove OS sandboxing or universal Hermes tool enforcement",
    }


def load_runtime(home, settings, checkout):
    required = initialize_required_runtime(home, checkout)
    model_tools = required.model_tools
    runtime = importlib.import_module(required.plugin.__name__ + ".runtime")
    filesystem = importlib.import_module(required.plugin.__name__ + ".filesystem")
    client = runtime.LoopbackClient(settings["session_file"], settings.get("api_port", 8000)).for_call()
    audit_path = Path(settings["audit_file"])
    initial_size = 0
    if audit_path.exists():
        with filesystem.open_private_file(audit_path) as fd:
            initial_size = os.fstat(fd).st_size

    def read_audit():
        with filesystem.open_private_file(audit_path) as fd:
            require(os.fstat(fd).st_size >= initial_size, "audit_was_truncated")
            os.lseek(fd, initial_size, os.SEEK_SET)
            data = bytearray()
            while len(data) <= 1024 * 1024:
                chunk = os.read(fd, min(65536, 1024 * 1024 + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            require(len(data) <= 1024 * 1024, "audit_too_large")
        records = [json.loads(line) for line in data.splitlines()]
        require(all(isinstance(record, dict) for record in records), "malformed_audit")
        return records

    def dispatch(name, args):
        return model_tools.handle_function_call(
            name, args, task_id="lexecon-owner-acceptance", session_id="lexecon-owner-acceptance",
        )

    return dispatch, client, read_audit, required


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--hermes-checkout", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        # Silence import/dispatcher chatter; the proof prints no file contents or server bodies.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            require(args.home.is_absolute() and args.hermes_checkout.is_absolute(),
                    "absolute_paths_required")
            home, settings = settings_for(args.home)
            dispatch, client, read_audit, host = load_runtime(home, settings, args.hermes_checkout)
            result = run_proof(dispatch, client, read_audit, settings["username"])
            from audit_acceptance import interruption_probe, replay_probe, zero_effect_probe
            result["host_denial"] = zero_effect_probe(host)
            result["replay"] = replay_probe(client, settings)
            result["interruption"] = interruption_probe(host, client, read_audit)
        print(json.dumps(result, sort_keys=True))
        return 0
    except ProofError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
    except (Exception, KeyboardInterrupt):
        # No arbitrary exception text: it can contain a session, server body, or file contents.
        print(json.dumps({"ok": False, "error": "proof_failed_check_owner_setup_and_local_api"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
