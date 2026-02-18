"""Pytest configuration and fixtures."""

import glob
import os

import pytest

from lexecon.ledger.chain import LedgerChain
from lexecon.policy.engine import PolicyEngine, PolicyMode
from lexecon.policy.relations import PolicyRelation
from lexecon.policy.terms import PolicyTerm


@pytest.fixture(scope="session", autouse=True)
def _clean_stale_databases():
    """Delete stale SQLite databases before the test session starts.

    These accumulate across runs (usage counters, auth state, ledger entries)
    and cause false failures such as 402 Payment Required when usage limits
    are hit from prior runs.
    """
    patterns = [
        "lexecon_*.db",
        "lexecon_*.db-wal",
        "lexecon_*.db-shm",
    ]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for pattern in patterns:
        for path in glob.glob(os.path.join(root, pattern)):
            try:
                os.remove(path)
            except OSError:
                pass


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
