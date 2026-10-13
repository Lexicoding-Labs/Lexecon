"""End-to-end checks for the supported single-organization local mode."""

import hashlib
import io
import json
import shutil
import sqlite3
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from lexecon.api.dependencies import ServiceRegistry
from lexecon.api.server import app
from lexecon.evidence_export.service import EvidenceExportService
from lexecon.ledger.chain import LedgerChain
from lexecon.policy.relations import PolicyRelation
from lexecon.security.auth_service import AuthService, Role
from lexecon.security.signature_service import SignatureService


def test_online_capability_verifier_rejects_tampering_scope_and_other_users(authenticated_client):
    client = authenticated_client
    services = ServiceRegistry.get()
    user = client.get("/auth/me").json()["user"]
    services.policy_engine.add_relation(PolicyRelation.permits(f"actor:{user['username']}", "action:read"))
    services.policy_engine.add_relation(PolicyRelation.permits(f"actor:{user['username']}", "action:tool:safe_demo"))
    decided = client.post("/decide", json={
        "actor": user["username"], "proposed_action": "read", "tool": "safe_demo",
        "user_intent": "Local verifier test",
    })
    assert decided.status_code == 200, decided.text
    grant = decided.json()["capability_token"]
    payload = {"capability_token": grant, "action": "read", "tool": "safe_demo"}
    # The documented verifier contract returns both validity and consumption.
    valid_response = {"valid": True, "consumed": False}
    invalid_response = {"valid": False, "consumed": False}
    for verification_payload in (payload, {**payload, "consume": False}):
        response = client.post("/capability/verify", json=verification_payload)
        assert response.status_code == 200, response.text
        assert response.json() == valid_response
    assert client.post("/capability/verify", json={**payload, "tool": "dangerous"}).json() == invalid_response
    forged = {**grant, "scope": {"action": "read", "tool": "dangerous"}}
    assert client.post("/capability/verify", json={**payload, "capability_token": forged}).json() == invalid_response
    other = services.auth_service.create_user(
        "other_verifier", "other-verifier@example.test", "Th!sV7ryStr0ng", Role.ADMIN, "Other",
    )
    other_session = services.auth_service.create_session(other)
    assert client.post("/capability/verify", json=payload, headers={
        "Authorization": f"Bearer {other_session.session_id}",
    }).json() == invalid_response
    # Rejected checks must not make the unchanged grant unusable by its owner.
    assert client.post("/capability/verify", json=payload).json() == valid_response
    services.policy_engine.add_relation(PolicyRelation.permits("actor:other_verifier", "action:other"))
    assert client.post("/capability/verify", json=payload).json() == invalid_response


def test_guided_policy_example_records_real_permit_and_deny_with_provenance(authenticated_client):
    client = authenticated_client
    username = client.get("/auth/me").json()["user"]["username"]
    loaded = client.post("/policies/load", json={"policy": {"relations": [
        {"type": "permits", "subject": f"actor:{username}", "action": "action:read"},
        {"type": "permits", "subject": f"actor:{username}", "action": "tool:safe_demo"},
    ]}})
    assert loaded.status_code == 200, loaded.text
    request = {"actor": username, "tool": "safe_demo", "user_intent": "Local guided policy example",
               "context": {"demo": True}}
    allowed = client.post("/decide", json={**request, "proposed_action": "read"})
    denied = client.post("/decide", json={**request, "proposed_action": "delete"})
    assert allowed.status_code == denied.status_code == 200
    assert allowed.json()["decision"] == "permit"
    assert denied.json()["decision"] == "deny"
    for response in (allowed, denied):
        assert client.post("/decide/verify", json=response.json()).json()["verified"] is True
    entries = client.get("/ledger/entries?event_type=decision").json()["entries"]
    assert [entry["data"]["evaluation_source"] for entry in entries[-2:]] == ["policy_engine"] * 2
    assert all(entry["data"]["demo_requested"] is True for entry in entries[-2:])
    assert all(entry["data"]["policy_version_hash"] and entry["data"]["risk_level"] == 1
               for entry in entries[-2:])
    assert client.get("/ledger/verify").json()["valid"] is True
    exported = client.post("/evidence/export", json={"include_verification": True})
    assert exported.status_code == 200, exported.text
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        assert "| LOW |" in archive.read("summary.md").decode()
        exported_entries = json.loads(archive.read("ledger_events.json"))["events"]
    assert any(entry["data"].get("evaluation_source") == "policy_engine" for entry in exported_entries)


def test_evidence_zip_accepts_real_numeric_risks_only():
    ledger = LedgerChain()
    ledger.append("decision", {"tenant_id": "default", "decision": "permit", "action": "read",
                               "risk_level": 1, "evaluation_source": "policy_engine"})
    ledger.append("decision", {"tenant_id": "default", "decision": "deny", "action": "delete",
                               "risk_level": 5, "evaluation_source": "policy_engine"})
    with zipfile.ZipFile(io.BytesIO(EvidenceExportService(ledger).export("default"))) as archive:
        summary = archive.read("summary.md").decode()
        events = json.loads(archive.read("ledger_events.json"))["events"]
    assert "| LOW | 1 |" in summary
    assert "| CRITICAL | 1 |" in summary
    assert {event["data"]["risk_level"] for event in events} == {1, 5}


def test_evidence_zip_accepts_mixed_real_and_synthetic_risks():
    ledger = LedgerChain()
    ledger.append("decision", {"tenant_id": "default", "decision": "permit", "action": "read",
                               "risk_level": 2, "evaluation_source": "policy_engine"})
    ledger.append("decision", {"tenant_id": "default", "decision": "deny", "action": "delete",
                               "risk_level": "high", "evaluation_source": "synthetic_seed"})
    with zipfile.ZipFile(io.BytesIO(EvidenceExportService(ledger).export("default"))) as archive:
        summary = archive.read("summary.md").decode()
        events = json.loads(archive.read("ledger_events.json"))["events"]
    assert "| MEDIUM | 1 |" in summary
    assert "| HIGH | 1 |" in summary
    assert {event["data"]["evaluation_source"] for event in events} == {"policy_engine", "synthetic_seed"}


def test_oidc_login_callback_uses_configured_auth_database(tmp_path, monkeypatch):
    monkeypatch.setenv("LEXECON_DATA_DIR", str(tmp_path))
    old_registry = ServiceRegistry._instance
    ServiceRegistry.reset()
    try:
        services = ServiceRegistry.get()
        services.initialize()
        provider = services.oidc_service.register_provider(
            "synthetic", "https://provider.invalid/discovery", "local-client", "unused",
        )
        monkeypatch.setattr(provider, "get_authorization_url", lambda state, nonce: "https://provider.invalid/authorize")
        monkeypatch.setattr(provider, "exchange_code_for_tokens", lambda code: {"id_token": "mock-token"})
        monkeypatch.setattr(provider, "verify_id_token", lambda token, nonce: {
            "sub": "subject-1", "email": "operator@example.test",
            "email_verified": True, "name": "Operator",
        })
        with TestClient(app, client=("192.0.2.51", 41000)) as client:
            initiated = client.get("/auth/oidc/login/synthetic")
            assert initiated.status_code == 200, initiated.text
            state = initiated.json()["state"]
            callback = client.get(f"/auth/oidc/callback/synthetic?code=mock&state={state}")
            assert callback.status_code == 200, callback.text
            token = callback.json()["session_id"]
            assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
            assert client.get(f"/auth/oidc/callback/synthetic?code=mock&state={state}").status_code == 400
        with sqlite3.connect(tmp_path / "lexecon_auth.db") as conn:
            assert conn.execute("SELECT COUNT(*) FROM oidc_users").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM oidc_states").fetchone()[0] == 0
    finally:
        ServiceRegistry._instance = old_registry


def test_password_change_only_session_and_credential_revocation(tmp_path, monkeypatch):
    monkeypatch.setenv("LEXECON_DATA_DIR", str(tmp_path))
    old_registry = ServiceRegistry._instance
    ServiceRegistry.reset()
    try:
        services = ServiceRegistry.get()
        services.initialize()
        user = services.auth_service.create_user(
            "operator", "operator@example.test", "Th!sV7ryStr0ng", Role.ADMIN, "Operator",
        )
        old_session = services.auth_service.create_session(user)
        with sqlite3.connect(services.auth_service.db_path) as conn:
            conn.execute("UPDATE users SET force_password_change = 1 WHERE user_id = ?", (user.user_id,))
        assert services.auth_service.validate_session(old_session.session_id)[0] is None
        with TestClient(app, client=("192.0.2.52", 41000)) as client:
            login = client.post("/auth/login", json={"username": "operator", "password": "Th!sV7ryStr0ng"}).json()
            assert login["success"] is False and login["session_id"]
            restricted = {"Authorization": f"Bearer {login['session_id']}"}
            assert client.get("/auth/me", headers=restricted).status_code == 401
            assert client.post("/policies/load", json={"policy": {}}, headers=restricted).status_code == 401
            changed = client.post("/auth/change-password", headers=restricted, json={
                "old_password": "Th!sV7ryStr0ng", "new_password": "N3w!Str0ngPassphrase",
            })
            assert changed.status_code == 200, changed.text
            assert client.get("/auth/me", headers=restricted).status_code == 401
            assert services.auth_service.validate_session(old_session.session_id)[0] is None
            fresh = client.post("/auth/login", json={
                "username": "operator", "password": "N3w!Str0ngPassphrase",
            }).json()
            assert fresh["success"] is True
    finally:
        ServiceRegistry._instance = old_registry


def test_absolute_session_age_and_password_expiry_fail_closed(tmp_path):
    auth = AuthService(str(tmp_path / "auth.db"))
    user = auth.create_user("operator", "operator@example.test", "Th!sV7ryStr0ng", Role.ADMIN, "Operator")
    session = auth.create_session(user)
    with sqlite3.connect(auth.db_path) as conn:
        old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        conn.execute("UPDATE sessions SET created_at = ?, expires_at = ? WHERE session_id = ?", (old, future, session.session_id))
    assert auth.validate_session(session.session_id)[0] is None
    fresh = auth.create_session(user)
    with sqlite3.connect(auth.db_path) as conn:
        conn.execute("UPDATE users SET password_expires_at = ? WHERE user_id = ?", (
            (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), user.user_id,
        ))
    assert auth.validate_session(fresh.session_id)[0] is None
    assert auth.authenticate("operator", "Th!sV7ryStr0ng")[1] == "password_change_required"
    assert auth._is_password_expired((datetime.now(timezone.utc) - timedelta(days=1)).replace(tzinfo=None).isoformat())
    assert auth._is_password_expired("invalid-expiry")


def test_bad_passwords_cannot_lock_named_account_or_enumerate_it(tmp_path):
    auth = AuthService(str(tmp_path / "auth.db"))
    user = auth.create_user("operator", "operator@example.test", "Th!sV7ryStr0ng", Role.ADMIN, "Operator")
    errors = [auth.authenticate("operator", "incorrect")[1] for _ in range(6)]
    errors.append(auth.authenticate("missing", "incorrect")[1])
    assert set(errors) == {"Invalid username or password"}
    with sqlite3.connect(auth.db_path) as conn:
        locked_until = conn.execute("SELECT locked_until FROM users WHERE user_id = ?", (user.user_id,)).fetchone()[0]
    assert locked_until is None
    assert auth.authenticate("operator", "Th!sV7ryStr0ng")[0] is not None


def test_tenant_subset_zip_is_rehashable_and_verification_is_honest():
    ledger = LedgerChain()
    ledger.append("decision", {"tenant_id": "default", "action": "first", "response_digest": "a"})
    ledger.append("decision", {"tenant_id": "other", "action": "secret", "response_digest": "b"})
    ledger.append("decision", {"tenant_id": "default", "action": "latest", "response_digest": "c"})
    service = EvidenceExportService(ledger)
    with zipfile.ZipFile(io.BytesIO(service.export("default", limit=1))) as archive:
        event = json.loads(archive.read("ledger_events.json"))["events"][0]
        report = json.loads(archive.read("verification_report.json"))
        summary = archive.read("summary.md").decode()
    hash_input = {key: event[key] for key in ("entry_id", "event_type", "data", "timestamp", "previous_hash")}
    expected = hashlib.sha256(json.dumps(hash_input, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert expected == event["entry_hash"]
    assert event["data"]["response_digest"] == "c"
    assert report["checked_count"] == 1
    assert report["source_chain_valid"] is True
    assert report["scope"] == "source_chain_and_exported_entry_hashes"
    assert "PASSED (source chain and exported entry hashes)" in summary
    with zipfile.ZipFile(io.BytesIO(service.export("default", limit=1, include_verification=False))) as archive:
        unchecked = json.loads(archive.read("verification_report.json"))
        unchecked_summary = archive.read("summary.md").decode()
    assert unchecked["verified"] is None
    assert unchecked["checked_count"] == 0
    assert "UNCHECKED" in unchecked_summary


def test_global_export_metadata_requires_admin(tmp_path, monkeypatch):
    monkeypatch.setenv("LEXECON_DATA_DIR", str(tmp_path))
    old_registry = ServiceRegistry._instance
    ServiceRegistry.reset()
    try:
        services = ServiceRegistry.get()
        services.initialize()
        auditor = services.auth_service.create_user(
            "auditor", "auditor@example.test", "Th!sV7ryStr0ng", Role.AUDITOR, "Auditor",
        )
        token = services.auth_service.create_session(auditor).session_id
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(app, client=("192.0.2.53", 41000)) as client:
            for path in ("/compliance/export-requests", "/compliance/audit-chain-verification",
                         "/api/governance/audit-export/requests", "/ledger/verify"):
                assert client.get(path, headers=headers).status_code == 403, path
            assert client.get("/ledger/entries", headers={**headers, "X-Tenant-ID": "other"}).status_code == 403
    finally:
        ServiceRegistry._instance = old_registry


def test_mismatched_signing_pair_is_rejected(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    SignatureService(str(first))
    SignatureService(str(second))
    shutil.copyfile(second / "public_key.pem", first / "public_key.pem")
    with pytest.raises(ValueError, match="does not match"):
        SignatureService(str(first))
