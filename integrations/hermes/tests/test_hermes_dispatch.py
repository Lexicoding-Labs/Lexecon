"""External integration contract for the installed Hermes dispatcher.

Use Hermes' canonical runner with this file's absolute path. No model, socket,
account, live profile, or built-in effectful handler is used. Threaded dispatch
below tests concurrent dispatcher calls, not a full model/delegation turn.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

# The canonical runner changes cwd to its Hermes checkout and strips PYTHONPATH.
if (Path.cwd() / "model_tools.py").is_file():
    sys.path.insert(0, str(Path.cwd()))
if importlib.util.find_spec("hermes_cli") is None:
    pytest.skip("Run using the Hermes checkout's scripts/run_tests.sh", allow_module_level=True)

from integrations.hermes.tests.hermes_harness import call_tool, load_hermes_gate  # noqa: E402


@pytest.fixture
def gate(tmp_path, monkeypatch):
    harness = load_hermes_gate(tmp_path, monkeypatch)
    assert harness.module is not None, {
        name: item.error for name, item in harness.manager._plugins.items()
    }
    yield harness
    harness.plugins._reset_plugin_managers_for_tests()


def test_real_discovery_exposes_only_bounded_plugin_tools(gate):
    from tools.tool_search import load_config

    assert load_config().enabled == "off"
    definitions = gate.model_tools.get_tool_definitions(
        enabled_toolsets=["lexecon_workspace"], quiet_mode=True, skip_tool_search_assembly=True,
    )
    assert {item["function"]["name"] for item in definitions} == {
        "lexecon_list_files", "lexecon_read_file",
    }


@pytest.mark.parametrize("name", ["terminal", "read_file", "execute_code", "delegate_task", "unmapped_tool"])
def test_unmapped_handler_is_never_called(gate, monkeypatch, name):
    calls = []
    monkeypatch.setattr(gate.model_tools.registry, "dispatch", lambda *a, **kw: calls.append(a))
    result = call_tool(gate, name, {"path": "anything"})
    assert result.get("error"), result
    assert calls == []


def test_registered_pre_hook_failure_blocks_dispatch(gate, monkeypatch):
    def broken(**kwargs):
        raise RuntimeError("test hook failed")

    gate.manager._hooks["pre_tool_call"] = [broken]
    calls = []
    monkeypatch.setattr(gate.model_tools.registry, "dispatch", lambda *a, **kw: calls.append(a))
    assert call_tool(gate, "lexecon_read_file", {"path": "hello.txt"}).get("error")
    assert calls == []


@pytest.mark.parametrize("hook_state", ["absent", "infrastructure_error", "caller_skipped"])
def test_protected_handler_still_denies_without_authenticated_gate(gate, monkeypatch, hook_state):
    if hook_state == "absent":
        gate.manager._hooks["pre_tool_call"] = []
    elif hook_state == "infrastructure_error":
        def broken(*args, **kwargs):
            raise RuntimeError("outer Hermes hook infrastructure failed")
        monkeypatch.setattr(gate.plugins, "_dispatch_pre_tool_call_hooks", broken)
    result = call_tool(
        gate, "lexecon_read_file", {"path": "hello.txt"},
        skip_pre_tool_call_hook=hook_state == "caller_skipped",
    )
    assert result.get("error"), result
    assert "Hello from" not in str(result)


def test_missing_plugin_has_no_protected_handler(tmp_path, monkeypatch):
    harness = load_hermes_gate(tmp_path, monkeypatch, enabled=False)
    try:
        result = call_tool(harness, "lexecon_read_file", {"path": "hello.txt"})
        assert result.get("error"), result
        assert "Hello from" not in str(result)
    finally:
        harness.plugins._reset_plugin_managers_for_tests()


def test_agent_loop_pre_hook_denies_unmapped_calls(gate):
    from agent.tool_executor import _pre_tool_block, _ToolCallRef

    ref = _ToolCallRef("terminal", {"command": "never executed"}, "test", "call", [])
    block, _ = _pre_tool_block(SimpleNamespace(session_id="test"), ref)
    assert block


def test_required_gate_blocks_outer_hook_failure(gate, monkeypatch):
    """The pinned dispatch gate still refuses a sentinel after hook failure."""
    def broken(*args, **kwargs):
        raise RuntimeError("outer dispatcher failure")

    called = []
    monkeypatch.setattr(gate.plugins, "_dispatch_pre_tool_call_hooks", broken)
    monkeypatch.setattr(
        gate.model_tools.registry, "dispatch",
        lambda *a, **kw: called.append(a) or '{"sentinel":true}',
    )
    assert call_tool(gate, "unmapped_sentinel").get("error")
    assert called == []


def fake_policy(gate, monkeypatch, *, deny=False):
    """Only the HTTP boundary is fake; discovery, handlers and file IO are real."""
    runtime = sys.modules[gate.module.__name__ + ".runtime"]
    requests = []

    def post(self, path, payload):
        requests.append((path, payload))
        if path == "/decide":
            return {
                "decision": "deny" if deny else "permit", "decision_id": "test-decision",
                "capability_token": {
                    "arguments_digest": runtime.arguments_digest(payload["tool_arguments"]),
                },
            }
        assert path == "/capability/verify"
        assert payload["consume"] is True
        return {"valid": True, "consumed": True}

    monkeypatch.setattr(runtime.LoopbackClient, "post", post)
    monkeypatch.setattr(runtime.LoopbackClient, "for_call", lambda self: self)
    monkeypatch.setattr(runtime.LoopbackClient, "whoami", lambda self: {
        "user": {"username": gate.settings["username"], "role": "viewer"},
    })
    return requests


def test_sequential_permit_and_denial_through_real_dispatch(gate, monkeypatch):
    requests = fake_policy(gate, monkeypatch)
    listed = call_tool(gate, "lexecon_list_files", {"path": "."})
    read = call_tool(gate, "lexecon_read_file", {"path": "hello.txt"})
    assert {entry["name"] for entry in listed["entries"]} == {"hello.txt", "welcome.txt"}
    assert read["content"] == "Hello from the bounded workspace.\n"
    assert [path for path, _ in requests] == ["/decide", "/capability/verify"] * 2
    denied_requests = fake_policy(gate, monkeypatch, deny=True)
    denied = call_tool(gate, "lexecon_read_file", {"path": "hello.txt"})
    assert denied == {"ok": False, "error": "policy_denied"}
    assert [path for path, _ in denied_requests] == ["/decide"]
    audit = [json.loads(line) for line in Path(gate.settings["audit_file"]).read_text().splitlines()]
    assert [item["outcome"] for item in audit] == [
        "requested", "authorized", "completed", "requested", "authorized", "completed",
        "requested", "blocked",
    ]


@pytest.mark.parametrize("attempt", range(8))
def test_parallel_dispatch_each_authorizes_inside_handler(gate, monkeypatch, attempt):
    from tools.thread_context import propagate_context_to_thread

    requests = fake_policy(gate, monkeypatch)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(propagate_context_to_thread(
            lambda i=i: call_tool(gate, "lexecon_read_file", {"path": "hello.txt"}, tool_call_id=str(i)),
        )) for i in range(4)]
        results = [future.result(timeout=10) for future in futures]
    errors = [result for result in results if "error" in result]
    assert errors == []
    assert all(result.get("content") == "Hello from the bounded workspace.\n" for result in results)
    assert sum(path == "/decide" for path, _ in requests) == 4
    assert sum(path == "/capability/verify" for path, _ in requests) == 4


def test_hook_rewritten_arguments_are_checked_by_actual_handler(gate, monkeypatch):
    requests = fake_policy(gate, monkeypatch)
    gate.manager._hooks["pre_tool_call"].append(
        lambda **kw: {"action": "modify", "args": {"path": "../outside.txt"}},
    )
    result = call_tool(gate, "lexecon_read_file", {"path": "hello.txt"})
    assert result.get("error"), result
    assert requests == []


def test_nested_tool_search_bridge_cannot_bypass_required_gate(gate, monkeypatch):
    requests = fake_policy(gate, monkeypatch)
    result = call_tool(gate, "tool_call", {
        "name": "lexecon_read_file", "arguments": {"path": "hello.txt"},
    }, enabled_toolsets=["lexecon_workspace"])
    assert result.get("error"), result
    assert requests == []


def test_direct_registry_invocation_cannot_skip_protected_authorization(gate):
    from integrations.hermes.tests.hermes_harness import parse_result

    result = parse_result(gate.model_tools.registry.dispatch("lexecon_read_file", {"path": "hello.txt"}))
    assert result.get("error"), result
    assert "Hello from" not in str(result)


def test_two_generated_homes_do_not_share_workspace_config(gate, tmp_path, monkeypatch):
    fake_policy(gate, monkeypatch)
    (gate.workspace / "hello.txt").write_text("Workspace A")
    assert call_tool(gate, "lexecon_read_file", {"path": "hello.txt"})["content"] == "Workspace A"
    other_root = tmp_path / "other"
    other_root.mkdir()
    other = load_hermes_gate(other_root, monkeypatch)
    fake_policy(other, monkeypatch)
    (other.workspace / "hello.txt").write_text("Workspace B")
    assert call_tool(other, "lexecon_read_file", {"path": "hello.txt"})["content"] == "Workspace B"
    monkeypatch.setenv("HERMES_HOME", str(gate.home))
    monkeypatch.chdir(gate.workspace)
    gate.plugins.discover_plugins(force=True)
    gate.manager = gate.plugins.get_plugin_manager()
    gate.module = gate.manager._plugins["lexecon-gate"].module
    fake_policy(gate, monkeypatch)
    # Reloading replaces the pinned manager; the process must refuse further
    # reads until an approved profile starts in a fresh process.
    assert call_tool(gate, "lexecon_read_file", {"path": "hello.txt"}).get("error")
