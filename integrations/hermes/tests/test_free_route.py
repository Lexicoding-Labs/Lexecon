"""No-network wire tests: denied requests must never reach inference transport."""

import asyncio
import base64
import copy
import hashlib
import importlib
import json
import socket
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import httpx
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from free_route import (
    CHAT_URL,
    HOST,
    MODEL,
    FreeRouteDenied,
    FreeRouteTransport,
    fetch_catalog,
    restrict_model_clients,
)


def check(condition: bool, detail: object) -> None:
    """Report the exact offline contract that failed."""
    if not condition:
        pytest.fail(str(detail))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Block every real socket connection during route tests."""
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Test attempted a real network connection")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def catalog():
    """Build a synthetic catalog with zero prices for the approved SKU."""
    return {"data": [{"id": MODEL, "pricing": {"prompt": "0", "completion": "0", "input_cache_read": "0"}}]}


def body():
    """Build a minimal approved inference request body."""
    return {"model": MODEL, "messages": [{"role": "user", "content": "synthetic fixture"}], "max_tokens": 100}


def synthetic_jwt(expiry: float) -> str:
    """Make a locally parseable placeholder JWT with no signing authority."""
    payload = json.dumps({"exp": expiry, "scope": "inference:invoke"}).encode()
    segment = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return "synthetic-header." + segment + ".synthetic-signature"


def harness(**kwargs: object):
    """Collect inference sends behind a synthetic transport."""
    sends = []
    def respond(request) -> httpx.Response:
        sends.append(request)
        return httpx.Response(200, json={"ok": True})
    route = FreeRouteTransport(transport=httpx.MockTransport(respond), catalog_reader=catalog, **kwargs)
    return route, sends


@pytest.mark.parametrize("url", [
    "https://openrouter.ai/api/v1/chat/completions", "http://" + HOST + "/v1/chat/completions",
    CHAT_URL + "?model=paid", CHAT_URL + "/", CHAT_URL + "#other", "https://" + HOST + ".evil/v1/chat/completions",
    "https://" + HOST + "/v1/responses", "https://" + HOST + ":444/v1/chat/completions",
])
def test_wrong_destination_never_preflights_or_sends(url):
    """Reject alternate hosts, schemes, ports and request paths."""
    route, sends = harness()
    with pytest.raises(FreeRouteDenied):
        route.handle_request(httpx.Request("POST", url, json=body()))
    check(sends == [] and route.preflights == 0, "sends == [] and route.preflights == 0")


@pytest.mark.parametrize("patch", [
    {"model": "upstage/solar-mini4"}, {"models": [MODEL, "paid"]}, {"provider": {"allow_fallbacks": True}},
    {"service_tier": "priority"}, {"plugins": [{"id": "web"}]}, {"max_tokens": 5000},
    {"max_tokens": True}, {"max_completion_tokens": 100}, {"messages": []},
    {"tools": [{"type": "web_search"}]}, {"tools": [{"type": "function", "function": {"name": "terminal"}}]},
])
def test_alternate_model_routing_paid_features_and_invalid_body_never_send(patch):
    """Reject body fields that could change model or route."""
    route, sends = harness()
    payload = {**body(), **patch}
    with pytest.raises(FreeRouteDenied):
        route.handle_request(httpx.Request("POST", CHAT_URL, json=payload))
    check(sends == [] and route.preflights == 0, "sends == [] and route.preflights == 0")


@pytest.mark.parametrize("raw", [b'{"model":"x","model":"y"}', b'{"model":NaN}', b"not json"])
def test_malformed_or_ambiguous_json_denied(raw):
    """Reject invalid or ambiguous JSON before any send."""
    route, sends = harness()
    with pytest.raises(FreeRouteDenied):
        route.handle_request(httpx.Request("POST", CHAT_URL, content=raw))
    check(sends == [], "sends == []")


@pytest.mark.parametrize("pricing", [None, {}, {"prompt": "0"}, {"prompt": "0", "completion": "0.1"},
                                       {"prompt": "NaN", "completion": "0"},
                                       {"prompt": False, "completion": "0"},
                                       {"prompt": "0", "completion": "0", "request": "0.01"},
                                       {"prompt": "0", "completion": "0", "other": "unknown"}])
def test_missing_nonzero_or_unknown_prices_never_send(pricing):
    """Stop when any published price is missing or not zero."""
    route, sends = harness()
    route.catalog_reader = lambda: {"data": [{"id": MODEL, "pricing": pricing}]}
    with pytest.raises(FreeRouteDenied):
        route.handle_request(httpx.Request("POST", CHAT_URL, json=body()))
    check(sends == [], "sends == []")


@pytest.mark.parametrize("value", [{}, {"data": []}, {"data": catalog()["data"] * 2}])
def test_absent_or_ambiguous_sku_never_sends(value):
    """Require exactly one approved model row in the catalog."""
    route, sends = harness()
    route.catalog_reader = lambda: value
    with pytest.raises(FreeRouteDenied):
        route.handle_request(httpx.Request("POST", CHAT_URL, json=body()))
    check(sends == [], "sends == []")


def test_preflight_fresh_for_every_request_and_failure_is_latched():
    """Recheck price on every request and latch a later failure."""
    route, sends = harness()
    prices = [catalog(), {"data": []}, catalog()]
    route.catalog_reader = lambda: prices.pop(0)
    request = httpx.Request("POST", CHAT_URL, json=body())
    route.handle_request(request)
    with pytest.raises(FreeRouteDenied):
        route.handle_request(request)
    with pytest.raises(FreeRouteDenied):
        route.handle_request(request)
    check(len(sends) == 1 and route.preflights == 2 and (len(prices) == 1), "len(sends) == 1 and route.preflights == 2 and (len(prices) == 1)")


def test_catalog_exception_is_sanitized_and_never_sends():
    """Keep provider errors out of the terminal refusal."""
    route, sends = harness()
    def unavailable() -> None:
        raise TimeoutError("provider secret should not escape")
    route.catalog_reader = unavailable
    with pytest.raises(FreeRouteDenied, match=r"^Fresh zero-price preflight failed$"):
        route.handle_request(httpx.Request("POST", CHAT_URL, json=body()))
    check(sends == [], "sends == []")


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308, 401, 402, 429, 500])
def test_redirects_and_errors_never_retry_even_if_client_requests_following(status):
    """Refuse redirects and errors without following or retrying."""
    sends = []
    def respond(request) -> httpx.Response:
        sends.append(request)
        return httpx.Response(status, headers={"location": "https://paid.invalid/v1/chat/completions"})
    route = FreeRouteTransport(transport=httpx.MockTransport(respond), catalog_reader=catalog)
    aux = SimpleNamespace(**{name: lambda: None for name in
                            ("call_llm", "async_call_llm", "resolve_provider_client",
                             "get_async_text_auxiliary_client")})
    with restrict_model_clients(route, aux), httpx.Client(transport=route, trust_env=False) as client:
        with pytest.raises(FreeRouteDenied):
            client.post(CHAT_URL, json=body(), follow_redirects=True)
        with pytest.raises(FreeRouteDenied):
            client.post(CHAT_URL, json=body())
    check(len(sends) == 1 and str(sends[0].url) == CHAT_URL, "len(sends) == 1 and str(sends[0].url) == CHAT_URL")


def test_budget_and_deadline_including_slow_preflight():
    """Enforce the shared request and time limits."""
    route, sends = harness(max_requests=1)
    request = httpx.Request("POST", CHAT_URL, json=body())
    route.handle_request(request)
    with pytest.raises(FreeRouteDenied):
        route.handle_request(request)
    check(len(sends) == 1, "len(sends) == 1")
    clock = [0]
    route, sends = harness(clock=lambda: clock[0], seconds=2)
    def slow() -> dict:
        clock[0] = 3
        return catalog()
    route.catalog_reader = slow
    with pytest.raises(FreeRouteDenied):
        route.handle_request(request)
    check(sends == [], "sends == []")


@pytest.mark.parametrize("operation", ["aux", "unregistered_sync", "unregistered_async", "mounted_transport"])
def test_other_clients_auxiliary_and_mount_bypasses_never_send(operation):
    """Reject alternate HTTP clients and auxiliary model paths."""
    route, sends = harness()
    def respond(request) -> httpx.Response:
        sends.append(request)
        return httpx.Response(200)
    other = httpx.MockTransport(respond)
    aux = SimpleNamespace(**{name: lambda: None for name in
                            ("call_llm", "async_call_llm", "resolve_provider_client",
                             "get_async_text_auxiliary_client")})
    original = aux.call_llm
    def attempt() -> None:
        if operation == "aux":
            aux.call_llm(task="title_generation", model="paid")
        elif operation == "unregistered_sync":
            with httpx.Client(transport=other, trust_env=False) as client:
                client.post(CHAT_URL, json=body())
        elif operation == "mounted_transport":
            with httpx.Client(transport=route, mounts={"all://": other}, trust_env=False) as client:
                client.post(CHAT_URL, json=body())
        else:
            async def run() -> None:
                async with httpx.AsyncClient(transport=other, trust_env=False) as client:
                    await client.post(CHAT_URL, json=body())
            asyncio.run(run())
    with restrict_model_clients(route, aux), pytest.raises(FreeRouteDenied):
        attempt()
    check(sends == [] and aux.call_llm is original, "sends == [] and aux.call_llm is original")


def test_catalog_request_is_anonymous_and_does_not_follow_redirects(monkeypatch):
    """Fetch metadata without authentication or redirects."""
    import free_route
    pinned_models = ModuleType("hermes_cli.models")
    pinned_models._HERMES_USER_AGENT = "hermes-cli/synthetic-pinned"
    monkeypatch.setitem(sys.modules, "hermes_cli.models", pinned_models)
    calls = []
    class Connection:
        def __init__(self, host, timeout):
            check(host == HOST and timeout == 10, "host == HOST and timeout == 10")
        def request(self, *args: object, **kwargs: object) -> None:
            calls.append((args, copy.deepcopy(kwargs)))
        def getresponse(self) -> SimpleNamespace:
            return SimpleNamespace(status=302)
        def close(self) -> None:
            """Close the synthetic connection without a socket."""
    monkeypatch.setattr(free_route.http.client, "HTTPSConnection", Connection)
    with pytest.raises(ValueError, match="Catalog unavailable"):
        fetch_catalog()
    check(calls == [(("GET", "/v1/models"), {"headers": {
        "Accept": "application/json", "User-Agent": pinned_models._HERMES_USER_AGENT,
    }})], "catalog GET uses the pinned Hermes identity without credentials or redirects")


def test_valid_request_uses_zero_priced_model_without_mutating_payload():
    """Pass one approved body through to the synthetic transport."""
    route, sends = harness()
    payload = body()
    request = httpx.Request("POST", CHAT_URL, json=payload)
    route.handle_request(request)
    check(len(sends) == route.preflights == 1, "len(sends) == route.preflights == 1")
    check(json.loads(sends[0].content) == payload, "json.loads(sends[0].content) == payload")


@pytest.mark.parametrize("metadata", [
    {"tags": ["product=hermes-agent", "client=hermes-client-v1", "conversation=test"],
     "session_id": "test"},
    {"tags": ["product=other", "client=hermes-client-v1"]},
    {"tags": ["product=hermes-agent", "client=hermes-client-v1", "provider=paid"]},
    {"session_id": 42},
])
def test_nous_metadata_cannot_add_routing_fields(metadata):
    """Allow bounded attribution metadata only."""
    route, sends = harness()
    payload = {**body(), **metadata}
    request = httpx.Request("POST", CHAT_URL, json=payload)
    if metadata.get("session_id") == "test":
        route.handle_request(request)
        check(len(sends) == 1, "len(sends) == 1")
    else:
        with pytest.raises(FreeRouteDenied):
            route.handle_request(request)
        check(sends == [], "sends == []")


def test_metadata_lookup_is_anonymous_and_not_an_inference_send():
    """Serve SDK metadata without sending an inference request."""
    from free_route import CATALOG_URL
    route, sends = harness()
    aux = SimpleNamespace(**{name: lambda: None for name in
                            ("call_llm", "async_call_llm", "resolve_provider_client",
                             "get_async_text_auxiliary_client")})
    with restrict_model_clients(route, aux), httpx.Client(trust_env=False) as client:
        response = client.get(CATALOG_URL, headers={"Authorization": "Bearer synthetic-not-a-key"})
    check(response.json() == catalog() and sends == [], "response.json() == catalog() and sends == []")


@pytest.mark.parametrize("run", [False, True])
def test_unapproved_run_or_bad_manifest_never_initializes_runtime(tmp_path, monkeypatch, run):
    """Validate the manifest before starting any audit runtime."""
    import owner_setup
    import run_free_audit
    home = owner_setup.prepare(tmp_path.resolve() / "pilot", api_port=8765)
    raw = '{"commit":"synthetic","records":[]}'
    owner_setup.private_file(home / "private/snapshot.json", raw)
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Preparation or unreviewed manifest initialized execution")
    monkeypatch.setattr(run_free_audit, "initialize_required_runtime", forbidden)
    expected = hashlib.sha256(raw.encode()).hexdigest()
    args = ["--home", str(home), "--hermes-checkout", str(tmp_path),
            "--manifest-sha256", expected if not run else "0" * 64]
    if run:
        with pytest.raises(owner_setup.SetupError):
            run_free_audit.main([*args, "--run"])
    else:
        check(run_free_audit.main(args) == 0, "run_free_audit.main(args) == 0")


def test_nous_yaml_save_keeps_viewer_renewal_and_offline_preflight(tmp_path, monkeypatch):
    """Hermes can rewrite config as YAML without breaking isolated owner flows."""
    import owner_setup
    import run_free_audit

    home = owner_setup.prepare(tmp_path.resolve() / "pilot", "lexecon_auditor", api_port=8765)
    path = home / "config.yaml"
    config = json.loads(path.read_text())
    config["model"] = {"provider": "nous", "name": MODEL}
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    with pytest.raises(json.JSONDecodeError):
        json.loads(path.read_text())
    settings = owner_setup.settings_for(home)[1]
    check(settings["api_port"] == 8765 and settings["username"] == "lexecon_auditor",
          "rewritten YAML retains the isolated viewer route")

    monkeypatch.setattr("builtins.input", lambda _: "login")
    monkeypatch.setattr(owner_setup.getpass, "getpass", lambda _: "synthetic-password")
    monkeypatch.setattr(owner_setup, "request", lambda *_args, **_kwargs: {
        "success": True, "session_id": "synthetic-session-id-123",
        "user": {"username": "lexecon_auditor", "role": "viewer"},
    })
    owner_setup.login(settings)
    check(Path(settings["session_file"]).is_file(), "viewer renewal kept its private session path")

    raw = '{"commit":"synthetic","records":[]}'
    owner_setup.private_file(home / "private/snapshot.json", raw)
    monkeypatch.setattr(run_free_audit, "initialize_required_runtime",
                        lambda *_args: pytest.fail("offline preflight started runtime"))
    result = run_free_audit.main([
        "--home", str(home), "--hermes-checkout", str(tmp_path),
        "--manifest-sha256", hashlib.sha256(raw.encode()).hexdigest(),
    ])
    check(result == 0, "offline preflight accepted the reviewed manifest")


def test_required_runtime_validates_nous_yaml_before_gate_activation(tmp_path, monkeypatch):
    """The second config reader also accepts YAML without relaxing gate checks."""
    import owner_setup
    import required_runtime

    home = owner_setup.prepare(tmp_path.resolve() / "pilot", "lexecon_auditor", api_port=8765)
    path = home / "config.yaml"
    config = json.loads(path.read_text())
    config["model"] = {"provider": "nous", "name": MODEL}
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    checkout = tmp_path / "pinned-hermes"
    (checkout / "tools").mkdir(parents=True)
    (checkout / "tools/required_tool_gate.py").write_text("# synthetic gate\n")

    class ReachedGateError(Exception):
        pass

    def stop_before_import(_name) -> None:
        raise ReachedGateError

    monkeypatch.setenv("HERMES_HOME", "synthetic-before")
    monkeypatch.setenv("HERMES_RUNTIME_DIR", "synthetic-before")
    monkeypatch.setenv("HERMES_ENABLE_PROJECT_PLUGINS", "synthetic-before")
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(required_runtime.importlib, "import_module", stop_before_import)
    with pytest.raises(ReachedGateError):
        required_runtime.initialize_required_runtime(home, checkout)


def test_required_runtime_rejects_yaml_tool_expansion_before_import(tmp_path, monkeypatch):
    """A YAML rewrite cannot broaden the required two-tool dispatch."""
    import owner_setup
    import required_runtime

    home = owner_setup.prepare(tmp_path.resolve() / "pilot", "lexecon_auditor", api_port=8765)
    path = home / "config.yaml"
    config = json.loads(path.read_text())
    config["required_tool_gate"]["tools"] = ["lexecon_read_file", "terminal"]
    path.write_text(yaml.safe_dump(config))
    checkout = tmp_path / "pinned-hermes"
    (checkout / "tools").mkdir(parents=True)
    (checkout / "tools/required_tool_gate.py").write_text("# synthetic gate\n")
    monkeypatch.setattr(required_runtime.importlib, "import_module",
                        lambda *_args: pytest.fail("expanded gate reached import"))
    with pytest.raises(owner_setup.SetupError, match="exactly its two bounded tools"):
        required_runtime.initialize_required_runtime(home, checkout)


def test_runner_records_thread_level_route_denial_as_failure(tmp_path, monkeypatch):
    """Record a swallowed worker refusal as a stopped audit."""
    import run_free_audit

    class LoopbackClient:
        def __init__(self, *_args: object):
            """Build a socket-free viewer identity fixture."""

        def for_call(self) -> "LoopbackClient":
            return self

        def whoami(self) -> dict:
            return {"user": {"username": "tester", "role": "viewer"}}

    runtime = SimpleNamespace(LoopbackClient=LoopbackClient)
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(json.dumps({"providers": {"nous": {
        "access_token": synthetic_jwt(time.time() + 600),
        "inference_base_url": run_free_audit.BASE_URL,
    }}}))
    auth = SimpleNamespace(_auth_file_path=lambda: auth_file, _global_auth_file_path=lambda: None)
    auxiliary = SimpleNamespace(**{name: lambda: None for name in
                                ("call_llm", "async_call_llm", "resolve_provider_client",
                                 "get_async_text_auxiliary_client")})
    modules = {"offline_host.runtime": runtime, "hermes_cli.auth": auth,
               "agent.auxiliary_client": auxiliary, "run_agent": SimpleNamespace(AIAgent=object)}
    original_import = importlib.import_module
    monkeypatch.setattr(run_free_audit.importlib, "import_module",
                        lambda name: modules.get(name) or original_import(name))

    class Agent:
        def run_conversation(self, *_args: object, **_kwargs: object) -> dict:
            route.denial = "Synthetic route refusal"
            return {"final_response": "Hermes handled a thread failure as a normal result"}

        def close(self) -> None:
            """Close the synthetic agent without side effects."""

    route = None
    def make_agent(_class, _key, passed_route, _workspace) -> Agent:
        nonlocal route
        route = passed_route
        return Agent()

    monkeypatch.setattr(run_free_audit, "make_agent", make_agent)
    home = tmp_path.resolve()
    (home / "private").mkdir(mode=0o700)
    host = SimpleNamespace(plugin=SimpleNamespace(__name__="offline_host"), home=home,
                           settings={"session_file": str(home / "private/session"), "username": "tester"})
    check(run_free_audit.execute(host, {"commit": "synthetic", "records": []}) == 1, "run_free_audit.execute(host, {'commit': 'synthetic', 'records': []}) == 1")
    result = json.loads(next((home / "private").glob("model-audit-*.json")).read_text())
    check(result["state"] == "StoppedByFreeRouteRestriction", "result['state'] == 'StoppedByFreeRouteRestriction'")
    check(result["inference_sends"] == result["price_preflights"] == 0, "result['inference_sends'] == result['price_preflights'] == 0")
    check("result" not in result, "'result' not in result")
