"""Pytest configuration and fixtures."""

import os
import tempfile
import uuid

import pytest

from lexecon.ledger.chain import LedgerChain
from lexecon.policy.engine import PolicyEngine, PolicyMode
from lexecon.policy.relations import PolicyRelation
from lexecon.policy.terms import PolicyTerm


@pytest.fixture
def authenticated_client():
    """Client with a real, disposable administrator session for legacy API flows."""
    from fastapi.testclient import TestClient

    from lexecon.api.dependencies import ServiceRegistry
    from lexecon.api.server import app
    from lexecon.decision.service import DecisionService
    from lexecon.policy.engine import PolicyEngine, PolicyMode
    from lexecon.security.auth_service import Role

    services = ServiceRegistry.get()
    services.initialize()
    services.policy_engine = PolicyEngine(mode=PolicyMode.STRICT)
    services.decision_service = DecisionService(policy_engine=services.policy_engine)
    suffix = uuid.uuid4().hex[:12]
    user = services.auth_service.create_user(
        f"api_admin_{suffix}", f"{suffix}@example.test", "Th!sV7ryStr0ng", Role.ADMIN, "API Test Admin",
    )
    session = services.auth_service.create_session(user)
    client = TestClient(app, client=(f"test-{suffix}", 40000))
    client.headers.update({"Authorization": f"Bearer {session.session_id}"})
    return client


@pytest.fixture(scope="session", autouse=True)
def _isolated_api_storage():
    """Run API tests in disposable storage without deleting checkout data."""
    from lexecon.api.dependencies import ServiceRegistry

    previous = os.environ.get("LEXECON_DATA_DIR")
    with tempfile.TemporaryDirectory(prefix="lexecon-tests-") as data_dir:
        os.environ["LEXECON_DATA_DIR"] = data_dir
        ServiceRegistry.reset()
        yield
        ServiceRegistry.reset()
    if previous is None:
        os.environ.pop("LEXECON_DATA_DIR", None)
    else:
        os.environ["LEXECON_DATA_DIR"] = previous


@pytest.fixture
def policy_engine():
    """Create a basic policy engine."""
    return PolicyEngine(mode=PolicyMode.STRICT)


@pytest.fixture
def populated_policy_engine():
    """Create a policy engine with some terms and relations."""
    engine = PolicyEngine(mode=PolicyMode.STRICT)

    # Add terms
    engine.add_term(PolicyTerm.create_actor("user", "User"))
    engine.add_term(PolicyTerm.create_actor("model", "AI Model"))
    engine.add_term(PolicyTerm.create_action("read", "Read Data"))
    engine.add_term(PolicyTerm.create_action("write", "Write Data"))
    engine.add_term(PolicyTerm.create_data_class("pii", "PII"))

    # Add relations
    engine.add_relation(PolicyRelation.permits("actor:user", "action:read"))
    engine.add_relation(PolicyRelation.forbids("actor:model", "action:write"))

    return engine


@pytest.fixture
def ledger():
    """Create a fresh ledger."""
    return LedgerChain()


@pytest.fixture
def populated_ledger():
    """Create a ledger with some entries."""
    ledger = LedgerChain()
    ledger.append("decision", {"actor": "user", "action": "read", "decision": "permit"})
    ledger.append("decision", {"actor": "model", "action": "write", "decision": "deny"})
    return ledger


@pytest.fixture
def redis_unavailable(monkeypatch):
    """Opt-in API fixture: simulate unavailable Redis, never a real connection.

    This exercises the production ConnectionError fallback. It does not replace
    authentication, route handlers, policy checks, or the offline network guard.
    """
    import importlib
    from unittest.mock import Mock

    import redis

    cache_module = importlib.import_module("lexecon.cache.redis_cache")
    client = Mock(spec=redis.Redis)
    client.ping.side_effect = redis.ConnectionError("synthetic Redis unavailable")
    monkeypatch.setattr(cache_module.redis, "from_url", Mock(return_value=client))
    monkeypatch.setattr(cache_module, "_cache_instance", None)
    return client
