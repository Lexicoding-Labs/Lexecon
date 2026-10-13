"""Argument-bound, single-use grants without accounts, sockets, or disk keys."""

import asyncio
import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from lexecon.api.models import DecisionRequestModel
from lexecon.api.routers.decisions import make_decision, verify_capability
from lexecon.decision.service import DecisionRequest, DecisionService, tool_arguments_digest
from lexecon.ledger.chain import LedgerChain
from lexecon.policy.engine import PolicyEngine
from lexecon.policy.relations import PolicyRelation
from lexecon.security.auth_service import Role


@pytest.fixture
def service():
    engine = PolicyEngine()
    engine.add_relation(PolicyRelation.permits("actor:hermes", "action:read"))
    engine.add_relation(PolicyRelation.permits("actor:hermes", "tool:safe_read"))
    return DecisionService(engine)


def request(arguments=None):
    return DecisionRequest(
        actor="hermes",
        proposed_action="read",
        tool="safe_read",
        user_intent="Read an approved sample",
        tool_arguments=arguments,
    )


def grant(service, arguments=None):
    return service.evaluate_request(request(arguments), subject="user-test").capability_token


def verify(service, token, arguments=None, **kwargs):
    return service.verify_capability_token(token, "user-test", "read", "safe_read", arguments, **kwargs)


def test_exact_nested_arguments_are_bound_and_order_independent(service):
    arguments = {"path": "sample.txt", "options": {"limit": 4, "unicode": "é"}}
    token = grant(service, arguments)
    expected = hashlib.sha256(
        json.dumps(arguments, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(),
    ).hexdigest()
    assert token["arguments_digest"] == expected
    assert verify(service, token, {"options": {"unicode": "é", "limit": 4}, "path": "sample.txt"})
    assert not verify(service, token, {**arguments, "path": "private.txt"})
    assert not verify(service, token)
    assert not verify(service, token, {})


def test_empty_arguments_are_bound_and_legacy_still_verifies(service):
    bound = grant(service, {})
    assert verify(service, bound, {})
    assert not verify(service, bound)
    legacy = grant(service)
    assert "arguments_digest" not in legacy
    assert verify(service, legacy)
    assert not verify(service, legacy, {})


def test_caller_mutation_does_not_change_request(service):
    arguments = {"options": {"limit": 4}}
    req = request(arguments)
    arguments["options"]["limit"] = 99
    token = service.evaluate_request(req, subject="user-test").capability_token
    assert verify(service, token, {"options": {"limit": 4}})


def test_digest_is_mac_authenticated(service):
    token = grant(service, {"path": "safe"})
    token["arguments_digest"] = tool_arguments_digest({"path": "secret"})
    assert not verify(service, token, {"path": "secret"})


def test_consume_rejects_every_replay(service):
    token = grant(service, {})
    assert verify(service, token, {})
    assert verify(service, token, {}, consume=True)
    assert not verify(service, token, {}, consume=True)
    assert not verify(service, token, {})


def test_parallel_consumption_has_exactly_one_winner(service):
    token = grant(service, {"path": "safe"})
    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(lambda _: verify(service, token, {"path": "safe"}, consume=True), range(64)))
    assert sum(results) == 1


def test_failed_verification_does_not_consume(service):
    token = grant(service, {"path": "safe"})
    assert not verify(service, token, {"path": "secret"}, consume=True)
    assert verify(service, token, {"path": "safe"}, consume=True)


def test_expired_consumption_records_pruned(service):
    service._consumed_capabilities["expired"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    token = grant(service, {})
    assert verify(service, token, {}, consume=True)
    assert "expired" not in service._consumed_capabilities
    assert token["token_id"] in service._consumed_capabilities


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("subject", "other-user"),
        ("scope", {"action": "write", "tool": "safe_read"}),
        ("scope", {"action": "read", "tool": "terminal"}),
    ],
)
def test_even_authentic_wrong_scope_is_denied(service, field, value):
    token = grant(service, {})
    token[field] = value
    token["mac"] = service._capability_mac(token)
    assert not verify(service, token, {}, consume=True)


def test_policy_change_and_restart_invalidate_grants(service):
    token = grant(service, {})
    assert not verify(DecisionService(service.policy_engine), token, {})
    service.policy_engine.add_relation(PolicyRelation.forbids("actor:hermes", "action:read"))
    assert not verify(service, token, {}, consume=True)
    assert service.evaluate_request(request({}), subject="user-test").decision == "deny"


@pytest.mark.parametrize("expiry", ["not a timestamp", "2020-01-01T00:00:00+00:00", "2099-01-01T00:00:00"])
def test_bad_or_expired_timestamp_rejected(service, expiry):
    token = grant(service, {})
    token["expiry"] = expiry
    token["mac"] = service._capability_mac(token)
    assert not verify(service, token, {}, consume=True)


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        {1: "invalid key"},
        {"n": float("nan")},
        {"n": float("inf")},
        {"bytes": b"x"},
        {"tuple": (1, 2)},
        {"text": "x" * 65536},
    ],
)
def test_invalid_arguments_rejected_at_model_and_service(arguments):
    with pytest.raises(ValueError, match="tool_arguments"):
        request(arguments)
    with pytest.raises(ValidationError):
        DecisionRequestModel(
            actor="hermes",
            proposed_action="read",
            tool="safe_read",
            user_intent="Read sample",
            tool_arguments=arguments,
        )


def test_deep_and_cyclic_arguments_rejected():
    value = {}
    for _ in range(34):
        value = {"nested": value}
    with pytest.raises(ValueError, match="depth"):
        request(value)
    cyclic = {}
    cyclic["self"] = cyclic
    with pytest.raises(ValueError, match="depth"):
        request(cyclic)


@pytest.mark.parametrize("consume", ["true", "false", 1, 0, None])
def test_consume_requires_actual_boolean(service, consume):
    token = grant(service, {})
    assert not verify(service, token, {}, consume=consume)
    response = asyncio.run(
        verify_capability(
            {
                "capability_token": token,
                "action": "read",
                "tool": "safe_read",
                "tool_arguments": {},
                "consume": consume,
            },
            services=SimpleNamespace(decision_service=service),
            session=SimpleNamespace(user_id="user-test"),
        ),
    )
    assert response == {"valid": False, "consumed": False}
    assert verify(service, token, {}, consume=True)


def test_api_decision_and_verify_preserve_binding_and_digest_only_audit(service):
    ledger = LedgerChain()
    services = SimpleNamespace(
        decision_service=service,
        policy_engine=service.policy_engine,
        ledger=ledger,
        usage_service=None,
        responsibility_tracker=Mock(),
    )
    session = SimpleNamespace(username="hermes", user_id="user-test", role=Role.VIEWER)
    model = DecisionRequestModel(
        actor="hermes",
        proposed_action="read",
        tool="safe_read",
        user_intent="Read sample",
        tool_arguments={"path": "sample.txt"},
    )
    response = asyncio.run(make_decision(None, model, services=services, tenant_id="test", session=session))
    assert response["decision"] == "permit"
    token = response["capability_token"]
    assert ledger.entries[-1].data["arguments_digest"] == token["arguments_digest"]
    assert "sample.txt" not in json.dumps(ledger.entries[-1].data)
    payload = {
        "capability_token": token,
        "action": "read",
        "tool": "safe_read",
        "tool_arguments": {"path": "sample.txt"},
        "consume": True,
    }
    assert asyncio.run(verify_capability(payload, services, session)) == {"valid": True, "consumed": True}
    assert asyncio.run(verify_capability(payload, services, session)) == {"valid": False, "consumed": False}


def test_malformed_verification_never_consumes(service):
    token = grant(service, {})
    payload = {
        "capability_token": copy.deepcopy(token),
        "action": "read",
        "tool": "safe_read",
        "tool_arguments": [],
        "consume": True,
    }
    assert asyncio.run(
        verify_capability(payload, SimpleNamespace(decision_service=service), SimpleNamespace(user_id="user-test")),
    ) == {"valid": False, "consumed": False}
    assert verify(service, token, {}, consume=True)
