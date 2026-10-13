#!/usr/bin/env python3
"""Run an isolated API proof with disposable local data and no external service."""

import json
import os
import tempfile

from fastapi.testclient import TestClient
from reference_tool_adapter import execute_safe_demo


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="lexecon-proof-") as data_dir:
        os.environ["LEXECON_DATA_DIR"] = data_dir

        from lexecon.api.dependencies import ServiceRegistry
        from lexecon.api.server import app
        from lexecon.security.auth_service import Role

        ServiceRegistry.reset()
        services = ServiceRegistry.get()
        services.initialize()
        services.auth_service.create_user(
            "demo_admin", "demo@example.test", "D3moP@ssW9thTest", Role.ADMIN, "Demo Admin",
        )

        with TestClient(app, client=("demo-local", 40000)) as client:
            login = client.post("/auth/login", json={
                "username": "demo_admin", "password": "D3moP@ssW9thTest",
            })
            login.raise_for_status()
            token = login.json()["session_id"]
            headers = {"Authorization": f"Bearer {token}"}
            policy = {"policy": {"relations": [
                {"type": "permits", "subject": "actor:demo_admin", "action": "action:read"},
                {"type": "permits", "subject": "actor:demo_admin", "action": "tool:safe_demo"},
            ]}}
            loaded = client.post("/policies/load", json=policy, headers=headers)
            loaded.raise_for_status()

            request = {
                "actor": "demo_admin", "proposed_action": "read", "tool": "safe_demo",
                "user_intent": "show an authorized local read",
            }
            allowed = client.post("/decide", json=request, headers=headers)
            allowed.raise_for_status()
            decision = allowed.json()
            verified = client.post("/decide/verify", json=decision, headers=headers)
            verified.raise_for_status()
            altered = client.post("/decide/verify", json={**decision, "decision": "deny"}, headers=headers)
            altered.raise_for_status()
            denied = client.post("/decide", json={**request, "tool": "unapproved_tool"}, headers=headers)
            grant = decision["capability_token"]
            tool_result = execute_safe_demo(client, headers, grant, "local demo")
            forged = {**grant, "scope": {"action": "read", "tool": "unapproved_tool"}}
            try:
                execute_safe_demo(client, headers, forged, "must not run")
                forged_grant_blocked = False
            except PermissionError:
                forged_grant_blocked = True
            ledger = client.get("/ledger/entries", headers=headers)
            ledger.raise_for_status()

            proof = {
                "policy_loaded": loaded.status_code == 200,
                "authorized_decision": decision["decision"],
                "authorized_tool": decision["capability_token"]["scope"]["tool"],
                "response_verified": verified.json()["verified"],
                "tampered_response_verified": altered.json()["verified"],
                "unapproved_tool_status": denied.status_code,
                "verified_tool_result": tool_result,
                "forged_grant_blocked": forged_grant_blocked,
                "ledger_entries": ledger.json()["total"],
            }
            assert proof["policy_loaded"]
            assert proof["authorized_decision"] == "permit"
            assert proof["response_verified"] is True
            assert proof["tampered_response_verified"] is False
            assert proof["unapproved_tool_status"] == 403
            assert proof["verified_tool_result"] == "LOCAL DEMO"
            assert proof["forged_grant_blocked"] is True
            print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
