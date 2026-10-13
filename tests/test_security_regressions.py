"""Focused checks for security boundaries reported in the October 2026 scan."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
import io
import json
import os
import sqlite3
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from lexecon.api.dependencies import ServiceRegistry
from lexecon.api.server import app
from lexecon.api.server import resolve_static_path
from lexecon.policy.engine import PolicyEngine, PolicyMode
from lexecon.policy.relations import PolicyRelation
from lexecon.evidence_export.service import EvidenceExportService
from lexecon.ledger.chain import LedgerChain
from lexecon.identity.signing import KeyManager
from lexecon.security.rate_limiter import RateLimiter
from lexecon.security.auth_service import Role
from lexecon.security.auth_service import AuthService
from lexecon.security.oidc_service import OIDCService
from lexecon.security.rate_limit_middleware import RateLimitMiddleware
from lexecon.security.signature_service import SignatureService


def test_named_rate_limit_denial_returns_without_deadlock():
    limiter = RateLimiter()
    limiter.limits["global_per_ip"] = (1, 3600)
    assert limiter.consume("test", "global_per_ip") is True
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(limiter.check_rate_limit, "test", "global_per_ip")
        try:
            allowed, retry_after = future.result(timeout=2)
        except TimeoutError:
            pytest.fail("Named rate-limit denial deadlocked")
    assert allowed is False
    assert retry_after > 0


def test_static_path_stays_inside_root(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    asset = static / "asset.js"
    asset.write_text("safe")
    secret = tmp_path / "secret.db"
    secret.write_text("secret")
    (static / "linked.db").symlink_to(secret)

    assert resolve_static_path(static, "asset.js") == asset
    for value in ("../secret.db", "nested/../../secret.db", "linked.db"):
        with pytest.raises(HTTPException) as exc:
            resolve_static_path(static, value)
        assert exc.value.status_code == 404


def test_rejected_policy_load_preserves_live_authorization():
    engine = PolicyEngine()
    engine.add_relation(PolicyRelation.permits("actor:operator", "action:read"))
    original_hash = engine.get_policy_hash()
    with pytest.raises(ValueError):
        engine.load_policy({"terms": [{"id": "actor:new", "type": "actor"}],
                            "relations": [{"type": "not_a_relation", "subject": "x", "action": "y"}]})
    assert engine.get_policy_hash() == original_hash
    assert engine.evaluate("operator", "read").allowed


def test_policy_partial_names_and_unmet_conditions_do_not_grant():
    engine = PolicyEngine()
    engine.add_relation(PolicyRelation.permits("actor:operator", "action:read", ["approved"]))
    assert not engine.evaluate("o", "read", context={"approved": True}).allowed
    assert not engine.evaluate("operator", "r", context={"approved": True}).allowed
    assert not engine.evaluate("operator", "read").allowed
    assert engine.evaluate("operator", "read", context={"approved": True}).allowed


def test_paranoid_high_risk_does_not_trust_caller_approval():
    engine = PolicyEngine(mode=PolicyMode.PARANOID)
    engine.add_relation(PolicyRelation.permits("actor:operator", "action:read"))
    assert engine.evaluate("operator", "read", risk_level=2).allowed
    assert not engine.evaluate("operator", "read", risk_level=4,
                               context={"human_approved": True}).allowed


def test_evidence_bundle_contains_only_requested_tenant_and_honest_verification():
    ledger = LedgerChain()
    ledger.append("decision", {"tenant_id": "team-a", "action": "a-secret"})
    ledger.append("decision", {"tenant_id": "team-b", "action": "b-secret"})
    service = EvidenceExportService(ledger)
    bundle = service.export("team-a", include_verification=False)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        events = json.loads(archive.read("ledger_events.json"))["events"]
        verification = json.loads(archive.read("verification_report.json"))
    assert len(events) == 1
    assert events[0]["data"]["action"] == "a-secret"
    assert verification["verified"] is None
    assert verification["checked_count"] == 0


def test_evidence_bundle_manifest_is_signed(tmp_path):
    signer = SignatureService(str(tmp_path / "keys"))
    assert stat.S_IMODE(Path(signer.private_key_path).stat().st_mode) == 0o600
    bundle = EvidenceExportService(LedgerChain(), signer).export("default")
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    signature = manifest["signature"]
    assert signature["signature"]
    valid, _ = signer.verify_signature(
        {"bundle_hash": manifest["bundle_hash"]}, signature["signature"],
    )
    assert valid


def test_cli_private_key_is_owner_only_and_never_overwritten(tmp_path):
    key_path = tmp_path / "node.key"
    public_path = tmp_path / "node.pub"
    manager = KeyManager.generate()
    manager.save_keys(key_path, public_path)
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    original = key_path.read_bytes()
    with pytest.raises(FileExistsError):
        KeyManager.generate().save_keys(key_path, public_path)
    assert key_path.read_bytes() == original


def test_forwarded_header_cannot_choose_rate_limit_identity():
    from starlette.requests import Request

    request = Request({
        "type": "http", "method": "GET", "path": "/decide",
        "headers": [(b"x-forwarded-for", b"198.51.100.23"),
                    (b"x-real-ip", b"198.51.100.24")],
        "client": ("192.0.2.45", 41000), "scheme": "http",
        "server": ("testserver", 80), "query_string": b"",
    })
    assert RateLimitMiddleware()._get_client_ip(request) == "192.0.2.45"


def test_disabled_user_loses_existing_session(tmp_path):
    auth = AuthService(str(tmp_path / "auth.db"))
    user = auth.create_user("operator", "operator@example.test", "Th!sV7ryStr0ng", Role.ADMIN, "Operator")
    session = auth.create_session(user)
    assert auth.validate_session(session.session_id)[0] is not None
    with sqlite3.connect(auth.db_path) as conn:
        conn.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user.user_id,))
    assert auth.validate_session(session.session_id)[0] is None


def test_oidc_requires_verified_email_before_account_link(tmp_path):
    auth = AuthService(str(tmp_path / "auth.db"))
    user = auth.create_user("operator", "operator@example.test", "Th!sV7ryStr0ng", Role.ADMIN, "Operator")
    oidc = OIDCService(auth.db_path)
    with pytest.raises(ValueError, match="Verified email"):
        oidc._provision_user("test-provider", "subject-1", user.email, "Operator", False)
    assert oidc._provision_user("test-provider", "subject-1", user.email, "Operator", True) == user.user_id


def test_mfa_and_disabled_oidc_accounts_cannot_get_session(tmp_path, monkeypatch):
    monkeypatch.setenv("LEXECON_DATA_DIR", str(tmp_path))
    old_registry = ServiceRegistry._instance
    ServiceRegistry.reset()
    try:
        services = ServiceRegistry.get()
        services.initialize()
        user = services.auth_service.create_user("operator", "operator@example.test", "Th!sV7ryStr0ng", Role.ADMIN, "Operator")
        monkeypatch.setattr(services.oidc_service, "handle_callback", lambda *_: (user.user_id, None))
        with TestClient(app, client=("192.0.2.46", 41000)) as client:
            callback = "/auth/oidc/callback/test-provider?code=synthetic&state=synthetic"
            with sqlite3.connect(services.auth_service.db_path) as conn:
                conn.execute("UPDATE users SET mfa_enabled = 1 WHERE user_id = ?", (user.user_id,))
            assert client.get(callback).status_code == 403
            assert not client.post("/auth/login", json={"username": "operator", "password": "Th!sV7ryStr0ng"}).json()["success"]
            with sqlite3.connect(services.auth_service.db_path) as conn:
                conn.execute("UPDATE users SET mfa_enabled = 0, is_active = 0 WHERE user_id = ?", (user.user_id,))
            assert client.get(callback).status_code == 403
    finally:
        ServiceRegistry._instance = old_registry


def test_setup_requires_unique_password_and_writes_selected_directory(tmp_path):
    script = Path(__file__).resolve().parents[1] / "setup_security.py"
    env = {**os.environ, "LEXECON_DATA_DIR": str(tmp_path)}
    env.pop("LEXECON_ADMIN_PASSWORD", None)
    missing = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, check=False)
    assert missing.returncode != 0
    assert not (tmp_path / "lexecon_auth.db").exists()
    env["LEXECON_ADMIN_PASSWORD"] = "Th!sV7ryStr0ng"
    created = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, check=False)
    assert created.returncode == 0, created.stderr
    assert (tmp_path / "lexecon_auth.db").exists()
    repeated = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, check=False)
    assert repeated.returncode != 0


def test_policy_mutation_requires_admin_and_failed_load_is_atomic(tmp_path, monkeypatch):
    monkeypatch.setenv("LEXECON_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LEXECON_ENV", raising=False)
    old_registry = ServiceRegistry._instance
    ServiceRegistry.reset()
    try:
        services = ServiceRegistry.get()
        services.initialize()
        services.auth_service.create_user("admin", "admin@example.test", "Th!sV7ryStr0ng", Role.ADMIN, "Admin")
        services.auth_service.create_user("viewer", "viewer@example.test", "Th!sV7ryStr0ng", Role.VIEWER, "Viewer")
        with TestClient(app, client=("192.0.2.45", 41000)) as client:
            policy = {"policy": {"relations": [
                {"type": "permits", "subject": "actor:admin", "action": "action:read"},
                {"type": "permits", "subject": "actor:admin", "action": "tool:safe_tool"},
            ]}}
            before = services.policy_engine.get_policy_hash()
            assert client.post("/policies/load", json=policy).status_code == 401
            assert client.post("/policies/load", json=policy,
                               headers={"Authorization": "Bearer invalid"}).status_code == 401
            viewer_token = client.post("/auth/login", json={"username": "viewer", "password": "Th!sV7ryStr0ng"}).json()["session_id"]
            assert client.post("/policies/load", json=policy,
                               headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403
            assert client.post("/demo/seed", headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403
            assert services.policy_engine.get_policy_hash() == before
            admin_token = client.post("/auth/login", json={"username": "admin", "password": "Th!sV7ryStr0ng"}).json()["session_id"]
            headers = {"Authorization": f"Bearer {admin_token}"}
            assert client.post("/policies/load", json=policy, headers=headers).status_code == 200
            seeded = client.post("/demo/seed", headers=headers)
            assert seeded.status_code == 200
            assert seeded.json()["created"]["decisions"] == 20
            assert len(client.get("/ledger/entries?event_type=decision", headers=headers).json()["entries"]) == 20
            assert all(entry["data"]["evaluation_source"] == "synthetic_seed"
                       for entry in client.get("/ledger/entries?event_type=decision", headers=headers).json()["entries"])
            monkeypatch.setenv("LEXECON_ENV", "production")
            assert client.post("/demo/seed", headers=headers).status_code == 404
            monkeypatch.delenv("LEXECON_ENV")
            loaded_hash = services.policy_engine.get_policy_hash()
            assert client.post("/policies/load", json={"policy": {"relations": [{"type": "invalid", "subject": "a", "action": "b"}]}},
                               headers=headers).status_code == 400
            assert services.policy_engine.get_policy_hash() == loaded_hash

            decision_request = {"actor": "admin", "proposed_action": "read", "tool": "safe_tool",
                                "user_intent": "regression test"}
            assert client.post("/decide", json=decision_request,
                               headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403
            assert client.post("/decide", json={**decision_request, "tool": "unsafe_tool"},
                               headers=headers).status_code == 403
            response = client.post("/decide", json=decision_request, headers=headers)
            assert response.status_code == 200, response.text
            decision = response.json()
            assert decision["decision"] == "permit"
            assert client.post("/decide/verify", json=decision, headers=headers).json()["verified"]
            altered = {**decision, "decision": "deny"}
            assert not client.post("/decide/verify", json=altered, headers=headers).json()["verified"]

            other_entry = services.ledger.append("decision", {
                "tenant_id": "team-b", "actor": "other", "action": "private-action",
            })
            audit_list = client.get("/api/v1/audit/decisions", headers=headers)
            assert audit_list.status_code == 200
            assert all(item["action"] != "private-action" for item in audit_list.json()["decisions"])
            assert client.get(f"/api/v1/audit/decisions/{other_entry.entry_id}", headers=headers).status_code == 404

            services.tenancy_service.create_tenant("team-b", "Team B")
            forged = {**headers, "X-Tenant-ID": "team-b"}
            for method, path, body in (("get", "/ledger/entries", None),
                                       ("get", "/usage", None),
                                       ("post", "/evidence/export", {}),
                                       ("post", "/decide", decision_request)):
                result = getattr(client, method)(path, headers=forged, **({"json": body} if body is not None else {}))
                assert result.status_code == 403, (path, result.text)
    finally:
        ServiceRegistry._instance = old_registry
