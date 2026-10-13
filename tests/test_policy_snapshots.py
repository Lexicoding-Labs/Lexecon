"""Policy export and conditional rollback without credentials or live services."""

import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from lexecon.api.dependencies import get_services, require_session
from lexecon.api.routers.policy import router
from lexecon.policy.engine import PolicyEngine, PolicyMode, PolicyVersionConflict
from lexecon.policy.relations import PolicyRelation
from lexecon.policy.terms import PolicyTerm
from lexecon.security.auth_service import Role


def policy(action="read", mode="strict"):
    return {
        "mode": mode,
        "terms": [PolicyTerm.create_actor("hermes", "Hermes").to_dict()],
        "relations": [PolicyRelation.permits("actor:hermes", f"action:{action}").to_dict()],
    }


@pytest.fixture
def api():
    engine = PolicyEngine(policy())
    services = SimpleNamespace(policy_engine=engine, ledger=Mock())
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_services] = lambda: services
    app.dependency_overrides[require_session] = lambda: SimpleNamespace(role=Role.ADMIN)
    with TestClient(app) as client:
        yield client, engine, services, app


def digest(policy_data):
    return hashlib.sha256(json.dumps(policy_data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_export_and_conditional_restore_roundtrip(api):
    client, engine, services, _ = api
    previous = client.get("/policies/export").json()
    assert previous == engine.export_policy()
    assert previous["policy_hash"] == digest(previous["policy"])
    changed = client.post("/policies/load", json={
        "policy": policy("write"), "expected_policy_hash": previous["policy_hash"],
    })
    assert changed.status_code == 200
    assert changed.json()["previous_policy_hash"] == previous["policy_hash"]
    assert engine.evaluate("hermes", "write").allowed
    assert not engine.evaluate("hermes", "read").allowed
    restored = client.post("/policies/load", json={
        "policy": previous["policy"], "expected_policy_hash": changed.json()["policy_hash"],
    })
    assert restored.status_code == 200
    assert restored.json()["policy_hash"] == previous["policy_hash"]
    assert client.get("/policies/export").json() == previous
    assert engine.evaluate("hermes", "read").allowed
    assert not engine.evaluate("hermes", "write").allowed
    assert services.ledger.append.call_count == 2


def test_stale_restore_does_not_overwrite_intervening_policy(api):
    client, engine, services, _ = api
    previous = engine.export_policy()
    first = client.post("/policies/load", json={"policy": policy("write"), "expected_policy_hash": previous["policy_hash"]}).json()
    engine.add_relation(PolicyRelation.forbids("actor:hermes", "action:write"))
    intervening = engine.export_policy()
    response = client.post("/policies/load", json={"policy": previous["policy"], "expected_policy_hash": first["policy_hash"]})
    assert response.status_code == 409
    assert engine.export_policy() == intervening
    assert services.ledger.append.call_count == 1


@pytest.mark.parametrize(("path", "method"), [("/policies/export", "get"), ("/policies/load", "post")])
@pytest.mark.parametrize(("role", "expected"), [(None, 401), (Role.VIEWER, 403), (Role.ADMIN, 200)])
def test_snapshot_routes_are_admin_only_even_when_mounted_alone(api, path, method, role, expected):
    client, _, _, app = api

    def session():
        if role is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return SimpleNamespace(role=role)

    app.dependency_overrides[require_session] = session
    response = client.get(path) if method == "get" else client.post(path, json={"policy": policy()})
    assert response.status_code == expected


@pytest.mark.parametrize("payload", [{"policy": policy("write")}, policy("write")])
def test_unconditional_wrapped_and_direct_loads_remain_supported(api, payload):
    client, engine, _, _ = api
    response = client.post("/policies/load", json=payload)
    assert response.status_code == 200
    assert engine.evaluate("hermes", "write").allowed


def test_direct_format_applies_expected_hash(api):
    client, engine, _, _ = api
    before = engine.export_policy()
    response = client.post("/policies/load", json={**policy("write"), "expected_policy_hash": before["policy_hash"]})
    assert response.status_code == 200
    assert "expected_policy_hash" not in engine.export_policy()["policy"]
    assert client.post("/policies/load", json={**policy(), "expected_policy_hash": before["policy_hash"]}).status_code == 409


@pytest.mark.parametrize("bad_hash", ["", "not-a-hash", "A" * 64, "f" * 63, 42])
def test_invalid_expected_hash_rejected_before_mutation(api, bad_hash):
    client, engine, services, _ = api
    before = engine.export_policy()
    assert client.post("/policies/load", json={"policy": policy("write"), "expected_policy_hash": bad_hash}).status_code == 422
    assert engine.export_policy() == before
    services.ledger.append.assert_not_called()


@pytest.mark.parametrize("bad_policy", [{"terms": [{"invalid": True}]}, {"relations": [{}]}, {"relations": [], "mode": "unknown"}, {"relations": None}])
def test_malformed_policy_leaves_all_state_intact(api, bad_policy):
    client, engine, services, _ = api
    before = engine.export_policy()
    response = client.post("/policies/load", json={"policy": bad_policy, "expected_policy_hash": before["policy_hash"]})
    assert response.status_code == 400
    assert engine.export_policy() == before
    services.ledger.append.assert_not_called()


def test_mode_restored_and_omitted_mode_preserved():
    engine = PolicyEngine(policy(mode="paranoid"))
    saved = engine.export_policy()
    engine.load_policy(policy(mode="strict"), expected_policy_hash=saved["policy_hash"])
    assert engine.mode == PolicyMode.STRICT
    engine.load_policy(saved["policy"], expected_policy_hash=engine.get_policy_hash())
    assert engine.export_policy() == saved
    assert engine.mode == PolicyMode.PARANOID
    engine.load_policy({"relations": []})
    assert engine.mode == PolicyMode.PARANOID


def test_policy_inputs_and_exports_do_not_alias_live_state():
    source = policy()
    source["terms"][0]["metadata"] = {"labels": ["original"]}
    source["relations"][0]["conditions"] = ["risk_level <= 2"]
    engine = PolicyEngine(source)
    saved = engine.export_policy()
    source["terms"][0]["metadata"]["labels"].append("mutated")
    source["relations"][0]["conditions"].clear()
    exported = engine.export_policy()
    exported["policy"]["terms"][0]["metadata"]["labels"].append("mutated")
    exported["policy"]["relations"][0]["conditions"].clear()
    assert engine.export_policy() == saved


def test_supported_mutators_copy_inputs_and_invalidate_expected_hash():
    engine = PolicyEngine()
    old = engine.get_policy_hash()
    term = PolicyTerm.create_actor("hermes", "Hermes")
    engine.add_term(term)
    term.label = "Changed outside engine"
    assert engine.to_dict()["terms"][0]["label"] == "Hermes"
    with pytest.raises(PolicyVersionConflict, match="Active policy changed"):
        engine.load_policy(policy(), expected_policy_hash=old)
    old = engine.get_policy_hash()
    relation = PolicyRelation.permits("actor:hermes", "action:read")
    engine.add_relation(relation)
    relation.target = "action:write"
    assert engine.evaluate("hermes", "read").allowed
    with pytest.raises(PolicyVersionConflict, match="Active policy changed"):
        engine.load_policy(policy(), expected_policy_hash=old)


def test_concurrent_conditional_replacements_have_one_winner():
    engine = PolicyEngine()
    expected = engine.get_policy_hash()
    barrier = Barrier(16)

    def replace(index):
        barrier.wait()
        try:
            return engine.load_policy(policy(f"read{index}"), expected_policy_hash=expected)
        except PolicyVersionConflict:
            return None

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(replace, range(16)))
    winners = [item for item in results if item is not None]
    assert len(winners) == 1
    assert engine.export_policy() == {key: value for key, value in winners[0].items() if key != "previous_policy_hash"}


def test_parallel_exports_are_internally_consistent():
    engine = PolicyEngine()

    def replace(index):
        snapshot = engine.load_policy(policy(f"read{index}"))
        assert snapshot["policy_hash"] == digest(snapshot["policy"])
        exported = engine.export_policy()
        assert exported["policy_hash"] == digest(exported["policy"])

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(replace, range(128)))


def test_nonserializable_policy_never_partially_replaces():
    engine = PolicyEngine(policy())
    saved = engine.export_policy()
    invalid = copy.deepcopy(saved["policy"])
    invalid["terms"][0]["metadata"] = {"bad": object()}
    with pytest.raises(TypeError, match="not JSON serializable"):
        engine.load_policy(invalid)
    assert engine.export_policy() == saved
