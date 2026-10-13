"""Required startup against the isolated Hermes candidate, without live credentials."""

# ruff: noqa: E402 -- Optional candidate imports need the runner checkout first.
import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if not (Path.cwd() / "tools/required_tool_gate.py").is_file():
    pytest.skip("Use the patched Hermes candidate's canonical runner", allow_module_level=True)
CANDIDATE = Path.cwd()
sys.path.insert(0, str(CANDIDATE))
sys.path.insert(0, str(ROOT / "integrations/hermes"))

from owner_setup import SetupError, prepare
from required_runtime import initialize_required_runtime


def test_required_startup_loads_real_profile_and_blocks_without_session(tmp_path, monkeypatch):
    home = tmp_path.resolve() / "pilot"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("HERMES_ENABLE_PROJECT_PLUGINS", "0")
    monkeypatch.chdir(tmp_path)

    def no_network(*args, **kwargs):
        raise AssertionError("Startup test must not connect to a network or live API")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    prepare(home)
    runtime = initialize_required_runtime(home, CANDIDATE)
    assert runtime.gate.mandatory_block("lexecon_read_file") is None
    assert runtime.gate.mandatory_block("terminal")
    result = json.loads(runtime.model_tools.handle_function_call(
        "lexecon_read_file", {"path": "welcome.txt"}, skip_pre_tool_call_hook=True,
    ))
    assert result["ok"] is False
    assert "content" not in result
    # A process must not silently fall back to the normal installed host.
    with pytest.raises(SetupError, match="patched"):
        initialize_required_runtime(home, tmp_path)
