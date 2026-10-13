"""Real Hermes dispatch -> real Lexecon API -> bounded filesystem proof.

Only authentication/storage wiring is replaced: an in-memory test principal,
ledger and service are used. No accounts, live HTTP listeners or model calls.
Run with the Hermes canonical test runner, as test_hermes_dispatch.py documents.
"""
# ruff: noqa: E402 -- Hermes runner requires path setup before optional imports.
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
if (Path.cwd() / "model_tools.py").is_file():
    sys.path.insert(0, str(Path.cwd()))
if importlib.util.find_spec("hermes_cli") is None:
    pytest.skip("Use the Hermes checkout's scripts/run_tests.sh", allow_module_level=True)

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from integrations.hermes.tests.hermes_harness import call_tool, load_hermes_gate
from lexecon.api.dependencies import get_services, get_tenant_id, require_session
from lexecon.api.routers.decisions import router
from lexecon.decision.service import DecisionService
from lexecon.ledger.chain import LedgerChain
from lexecon.policy.engine import PolicyEngine
from lexecon.policy.relations import PolicyRelation
from lexecon.security.auth_service import Role


@pytest.fixture
def integration(tmp_path, monkeypatch):
    h = load_hermes_gate(tmp_path, monkeypatch)
    assert h.module is not None
    engine = PolicyEngine()
    policy = json.loads((ROOT / "integrations/hermes/starter-policy.json").read_text())
    # The isolated loader uses hermes-test; production starter policy stays unchanged.
    for relation in policy["relations"]:
        relation["subject"] = "actor:hermes-test"
    engine.load_policy(policy)
    ledger = LedgerChain()
    service = DecisionService(engine)
    services = SimpleNamespace(policy_engine=engine, decision_service=service,
                               ledger=ledger, usage_service=None, responsibility_tracker=Mock())
    state = SimpleNamespace(authenticated=True, after_decide=None, calls=[])

    def principal():
        if not state.authenticated:
            raise HTTPException(401, "Test session expired")
        return SimpleNamespace(user_id="test-only-subject", username="hermes-test", role=Role.VIEWER)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_services] = lambda: services
    app.dependency_overrides[get_tenant_id] = lambda: "test-only-tenant"
    app.dependency_overrides[require_session] = principal
    runtime = sys.modules[h.module.__name__ + ".runtime"]
    with TestClient(app) as client:
        def post(_self, path, payload):
            state.calls.append((path, payload))
            response = client.post(path, json=payload)
            if response.status_code != 200:
                raise runtime.GateError("authentication_required" if response.status_code == 401 else "request_denied")
            result = response.json()
            if path == "/decide" and state.after_decide:
                state.after_decide(result)
            return result
        monkeypatch.setattr(runtime.LoopbackClient, "for_call", lambda self: self)
        monkeypatch.setattr(runtime.LoopbackClient, "whoami", lambda self: {
            "user": {"username": "hermes-test", "role": "viewer"},
        })
        monkeypatch.setattr(runtime.LoopbackClient, "post", post)
        monkeypatch.setattr(runtime.LoopbackClient, "ledger_entries",
                            lambda self: client.get("/ledger/entries").json())
        yield SimpleNamespace(h=h, engine=engine, ledger=ledger, service=service, state=state,
                              runtime=runtime)
    h.plugins._reset_plugin_managers_for_tests()


def test_real_permit_and_policy_deny_correlate_execution_and_ledger(integration, monkeypatch):
    i = integration
    result = call_tool(i.h, "lexecon_read_file", {"path": "hello.txt"})
    assert result["ok"] is True, result
    assert "Hello from the bounded workspace." in json.dumps(result)
    decisions = [entry for entry in i.ledger.entries if entry.event_type == "decision"]
    assert len(decisions) == 1
    assert decisions[0].data["decision_id"] == result["decision_id"]
    assert decisions[0].data["arguments_digest"]
    rows = [json.loads(line) for line in Path(i.h.settings["audit_file"]).read_text().splitlines()]
    assert [row["outcome"] for row in rows] == ["requested", "authorized", "completed"]
    assert rows[-1]["decision_id"] == result["decision_id"]
    assert rows[-1]["request_id"] == decisions[0].data["request_id"]
    assert rows[-1]["timestamp"]
    i.engine.add_relation(PolicyRelation.forbids("actor:hermes-test", "action:read"))
    reads = []
    monkeypatch.setattr(i.runtime, "read_file", lambda *args: reads.append(args))
    denied = call_tool(i.h, "lexecon_read_file", {"path": "hello.txt"})
    assert denied == {"ok": False, "error": "policy_denied"}
    assert reads == []
    assert [e.data["decision"] for e in i.ledger.entries if e.event_type == "decision"] == ["permit", "deny"]
    assert i.ledger.verify_integrity()["valid"]


@pytest.mark.parametrize("failure", ["expired_session", "policy_changed", "arguments_changed", "replayed_grant"])
def test_real_api_failures_stop_filesystem_execution(integration, monkeypatch, failure):
    i = integration
    if failure == "expired_session":
        i.state.authenticated = False
    elif failure == "policy_changed":
        i.state.after_decide = lambda result: i.engine.add_relation(
            PolicyRelation.forbids("actor:hermes-test", "action:read"))
    elif failure == "arguments_changed":
        def alter(result):
            result["capability_token"]["arguments_digest"] = "0" * 64
        i.state.after_decide = alter
    else:
        def consume_first(result):
            payload = i.state.calls[-1][1]
            assert i.service.verify_capability_token(
                result["capability_token"], "test-only-subject", "read", "lexecon_read_file",
                payload["tool_arguments"], consume=True)
        i.state.after_decide = consume_first
    reads = []
    monkeypatch.setattr(i.runtime, "read_file", lambda *args: reads.append(args))
    result = call_tool(i.h, "lexecon_read_file", {"path": "hello.txt"})
    assert result["ok"] is False, result
    assert reads == []
    assert "Hello from" not in json.dumps(result)


def test_owner_proof_flow_through_actual_dispatch_and_api(integration, monkeypatch):
    """Validate the owner proof orchestration with the real in-process API seam."""
    i = integration
    monkeypatch.syspath_prepend(str(ROOT / "integrations/hermes"))
    from verify_live import run_proof

    client = i.runtime.LoopbackClient(Path(i.h.settings["session_file"]))
    result = run_proof(
        lambda name, args: call_tool(i.h, name, args), client,
        lambda: [json.loads(row) for row in Path(i.h.settings["audit_file"]).read_text().splitlines()],
        "hermes-test",
    )
    assert result["ok"] is True
    decisions = [e for e in i.ledger.entries if e.event_type == "decision"]
    assert [e.data["decision"] for e in decisions] == ["permit", "permit", "deny"]
    assert result["denied"]["delete_policy_decision_id"] == decisions[-1].data["decision_id"]


def test_owner_acceptance_replay_dispatch_and_interruption(integration, monkeypatch):
    if importlib.util.find_spec("tools.required_tool_gate") is None:
        pytest.skip("Mandatory-host acceptance requires the patched candidate")
    monkeypatch.syspath_prepend(str(ROOT / "integrations/hermes"))
    from audit_acceptance import interruption_probe, replay_probe, zero_effect_probe

    i = integration
    host = SimpleNamespace(home=i.h.home, model_tools=i.h.model_tools)
    client = i.runtime.LoopbackClient(Path(i.h.settings["session_file"]))
    assert zero_effect_probe(host)["effects"] == 0
    assert replay_probe(client, i.h.settings)["replay_rejected"] is True
    audit_file = Path(i.h.settings["audit_file"])

    def audit():
        return [json.loads(line) for line in audit_file.read_text().splitlines()] if audit_file.exists() else []

    result = interruption_probe(host, client, audit)
    assert result["initial"] == "Unknown"
    assert result["state"] == "ObservedCompletedRead"
    journal = [json.loads(row) for row in (i.h.home / "private" / result["journal"]).read_text().splitlines()]
    assert [row["state"] for row in journal] == ["Unknown", "ObservedCompletedRead"]
