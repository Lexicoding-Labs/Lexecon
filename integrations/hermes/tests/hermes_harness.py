"""Real Hermes loader/dispatcher, isolated from installed user state and networks.

Run from the Hermes checkout with its canonical scripts/run_tests.sh. This
module deliberately does not discover a user's default Hermes home or secrets.
"""

from __future__ import annotations

import importlib
import json
import socket
from pathlib import Path
from types import SimpleNamespace

PLUGIN_SOURCE = Path(__file__).resolve().parents[1] / "lexecon_gate"


def load_hermes_gate(tmp_path, monkeypatch, *, enabled=True):
    """Discover the shipped plugin from a temporary home using Hermes itself."""
    tmp_path = tmp_path.resolve()
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HERMES_ENABLE_PROJECT_PLUGINS", "0")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    def no_connect(*args, **kwargs):
        raise AssertionError("Network connections are forbidden in dispatch tests")

    monkeypatch.setattr(socket.socket, "connect", no_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", no_connect)
    monkeypatch.setattr(socket, "create_connection", no_connect)
    spec = importlib.util.spec_from_file_location("lexecon_owner_setup", PLUGIN_SOURCE.parent / "owner_setup.py")
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    setup.prepare(home, username="hermes-test")
    config = json.loads((home / "config.yaml").read_text())
    if not enabled:
        config["plugins"]["enabled"] = []
        (home / "config.yaml").write_text(json.dumps(config))
    settings = config["plugins"]["entries"]["lexecon-gate"]["settings"]
    workspace = Path(settings["workspace_root"])
    (workspace / "hello.txt").write_text("Hello from the bounded workspace.\n")
    monkeypatch.chdir(workspace)
    required_gate = None
    if importlib.util.find_spec("tools.required_tool_gate") is not None:
        required_gate = importlib.import_module("tools.required_tool_gate")
        assert required_gate.arm_from_config() is True
    plugins = importlib.import_module("hermes_cli.plugins")
    plugins._reset_plugin_managers_for_tests()
    model_tools = importlib.import_module("model_tools")
    plugins.discover_plugins(force=True)
    if required_gate is not None and enabled:
        required_gate.seal_required_gate()
    manager = plugins.get_plugin_manager()
    loaded = manager._plugins.get("lexecon-gate")
    module = None if loaded is None else loaded.module
    return SimpleNamespace(
        home=home, workspace=workspace, settings=settings, plugins=plugins,
        manager=manager, module=module, model_tools=model_tools,
    )


def parse_result(result):
    return json.loads(result) if isinstance(result, str) else result


def call_tool(harness, name, args=None, **kwargs):
    return parse_result(harness.model_tools.handle_function_call(
        name, args or {}, task_id="isolated-test", session_id="isolated-test",
        **kwargs,
    ))
