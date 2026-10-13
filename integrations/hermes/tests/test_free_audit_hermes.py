"""Real Hermes agent + SDK + required dispatch; fake inference and no live sockets."""


import base64
import importlib
import json
import socket
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

if not (Path.cwd() / "tools/required_tool_gate.py").is_file():
    pytest.skip("Use the patched Hermes candidate's canonical runner", allow_module_level=True)
sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_free_audit
from free_route import MODEL, FreeRouteDenied, FreeRouteTransport, fetch_catalog, restrict_model_clients
from owner_setup import SetupError
from run_free_audit import make_agent

from integrations.hermes.tests.hermes_harness import load_hermes_gate


def check(condition: bool, detail: str) -> None:
    """Fail with the specific synthetic integration contract."""
    if not condition:
        pytest.fail(detail)


def test_public_catalog_uses_pinned_hermes_identity_without_auth(monkeypatch):
    """The bounded audit GET uses the real pinned Hermes public-model identity."""
    import free_route
    from hermes_cli.models import _HERMES_USER_AGENT

    calls = []
    payload = json.dumps({"data": [{"id": MODEL, "pricing": {
        "prompt": "0", "completion": "0", "input_cache_read": "0",
    }}]}).encode()

    class Response:
        status = 200

        def read(self, limit: int) -> bytes:
            check(limit == free_route.MAX_CATALOG + 1, "catalog read stays bounded")
            return payload

    class Connection:
        def __init__(self, host, timeout):
            check(host == free_route.HOST and timeout == 10, "approved catalog host and timeout")

        def request(self, method: str, path: str, *, headers: dict[str, str]) -> None:
            calls.append((method, path, headers))

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    monkeypatch.setattr(free_route.http.client, "HTTPSConnection", Connection)
    check(fetch_catalog()["data"][0]["id"] == MODEL, "synthetic catalog accepted")
    check(calls == [("GET", "/v1/models", {
        "Accept": "application/json", "User-Agent": _HERMES_USER_AGENT,
    })], "only the pinned Hermes identity was sent, with no auth header")


def test_real_agent_sdk_and_dispatch_use_only_checked_free_route(tmp_path, monkeypatch):
    """Send two synthetic SDK turns through the checked route and real dispatch."""
    gate = load_hermes_gate(tmp_path, monkeypatch)
    requests = []
    def inference(request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "fixture-call", "type": "function",
                "function": {"name": "lexecon_read_file", "arguments": '{"path":"hello.txt"}'},
            }]}
            finish = "tool_calls"
        else:
            message = {"role": "assistant", "content": "The unauthenticated fixture read was denied."}
            finish = "stop"
        return httpx.Response(200, json={
            "id": "fixture-completion", "object": "chat.completion", "created": 1, "model": MODEL,
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        })
    route = FreeRouteTransport(transport=httpx.MockTransport(inference), catalog_reader=lambda: {
        "data": [{"id": MODEL, "context_length": 524288,
                  "pricing": {"prompt": "0", "completion": "0"}}]}, max_requests=3)
    auxiliary = importlib.import_module("agent.auxiliary_client")
    agent = None
    try:
        with restrict_model_clients(route, auxiliary):
            from run_agent import AIAgent
            agent = make_agent(AIAgent, "offline-test-not-a-credential", route, gate.workspace)
            answer = agent.run_conversation("Read hello.txt through Lexecon.", system_message="Synthetic offline test.")
            check("denied" in answer["final_response"], "Protected read must be denied")
            check(agent._fallback_chain == [], "Fallback chain must be empty")
            check(agent.compression_enabled is False, "Compression must be disabled")
            check(agent.skip_background_review is True, "Background review must be disabled")
            check(len(requests) == route.preflights == 2, "Both sends need fresh price checks")
            check(all(row["model"] == MODEL for row in requests), "Only the free SKU may be requested")
            names = {tool["function"]["name"] for tool in requests[0]["tools"]}
            check(names == {"lexecon_list_files", "lexecon_read_file"}, "Only Lexecon tools may be offered")
            tools = [row for row in requests[1]["messages"] if row.get("role") == "tool"]
            check(len(tools) == 1, "One protected tool result should reach the model")
            check("Hello from the bounded workspace" not in tools[0]["content"], "File contents must stay private")
            # Agent/client rebuilds cannot switch to the paid sibling.
            agent.model = "upstage/solar-mini4"
            with pytest.raises(FreeRouteDenied):
                agent._create_openai_client(agent._client_kwargs)
            check(len(requests) == 2, "Client rebuild must not send an alternate model")
    finally:
        if agent is not None:
            agent.close()
        route.finish()
        gate.plugins._reset_plugin_managers_for_tests()


@pytest.mark.parametrize("state_kind", ["expired_named", "retired_guest", "wrong_route"])
def test_unusable_auth_never_refreshes_replaces_or_writes(tmp_path, monkeypatch, state_kind):
    """Refuse unusable stored identity before any auth mutator or model call."""
    auth = importlib.import_module("hermes_cli.auth")
    anon = importlib.import_module("hermes_cli.anon_auth")
    auth_nous = importlib.import_module("hermes_cli.auth_nous")
    expiry = time.time() - 1 if state_kind == "expired_named" else time.time() + 600
    payload = json.dumps({"exp": expiry, "scope": "inference:invoke"}).encode()
    token = "synthetic-header." + base64.urlsafe_b64encode(payload).decode().rstrip("=") + ".synthetic-signature"
    state = {"access_token": token, "inference_base_url": run_free_audit.BASE_URL}
    if state_kind == "expired_named":
        state["refresh_token"] = token
    elif state_kind == "retired_guest":
        state.update(auth_method="anonymous", anon_token=token)
    else:
        state["inference_base_url"] = "https://paid.invalid/v1"
    auth_file = tmp_path / "auth.json"
    initial = json.dumps({"providers": {"nous": state}}).encode()
    auth_file.write_bytes(initial)
    monkeypatch.setattr(auth, "_auth_file_path", lambda: auth_file)
    monkeypatch.setattr(auth, "_global_auth_file_path", lambda: None)
    attempts = []

    def forbidden(*_args: object, **_kwargs: object) -> None:
        attempts.append("forbidden action")
        raise AssertionError("Auth mutation, network POST or identity creation was attempted")

    for module, name in ((auth, "resolve_nous_runtime_credentials"), (auth, "_save_auth_store"),
                         (auth_nous, "_refresh_nous_or_quarantine"), (anon, "ensure_portal_identity")):
        monkeypatch.setattr(module, name, forbidden)
    monkeypatch.setattr(httpx.Client, "post", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    class Viewer:
        def __init__(self, *_args: object):
            """Represent a synthetic, already-validated viewer."""

        def for_call(self) -> "Viewer":
            return self

        def whoami(self) -> dict:
            return {"user": {"username": "tester", "role": "viewer"}}

    runtime = SimpleNamespace(LoopbackClient=Viewer)
    original_import = importlib.import_module
    monkeypatch.setattr(run_free_audit.importlib, "import_module",
                        lambda name: runtime if name == "offline_host.runtime" else original_import(name))
    host = SimpleNamespace(plugin=SimpleNamespace(__name__="offline_host"), home=tmp_path,
                           settings={"session_file": str(tmp_path / "session"), "username": "tester"})
    with pytest.raises(SetupError, match="no account changes were made"):
        run_free_audit.execute(host, {"commit": "synthetic", "records": []})
    check(attempts == [], "No refresh POST, identity creation or store write may occur")
    check(auth_file.read_bytes() == initial, "The stored auth bytes must remain unchanged")
    check(list(tmp_path.glob("private/model-audit-*.json")) == [], "No audit should start")
