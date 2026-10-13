"""Filesystem and fail-closed contracts, without accounts or network access."""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from lexecon_gate import GateConfig, GateRuntime, pre_tool_call, register
from lexecon_gate import runtime as module
from lexecon_gate.filesystem import MAX_BYTES, GateError
from lexecon_gate.runtime import LoopbackClient, arguments_digest


class Client:
    def __init__(self, decision="permit", verified=None):
        self.calls = []
        self.decision = decision
        self.verified = {"valid": True, "consumed": True} if verified is None else verified

    def whoami(self):
        return {"user": {"username": "hermes-test", "role": "viewer"}}

    def post(self, path, payload):
        self.calls.append((path, payload))
        if path == "/decide":
            return {"decision": self.decision, "decision_id": "decision-test",
                    "capability_token": {"arguments_digest": arguments_digest(payload["tool_arguments"])}}
        return self.verified


@pytest.fixture
def gate(tmp_path):
    base = tmp_path.resolve()
    workspace = base / "workspace"
    workspace.mkdir()
    private = base / "private"
    private.mkdir(mode=0o700)
    session = private / "session"
    session.write_text("test-session-placeholder-123456")
    session.chmod(0o600)
    (workspace / "hello.txt").write_text("hello world")
    return GateRuntime(GateConfig(workspace, "hermes-test", session, private / "audit.jsonl"), Client())


def test_permit_bound_consumed_and_audited_without_content(gate):
    result = gate.execute("lexecon_read_file", {"path": "hello.txt"})
    assert result == {"ok": True, "decision_id": "decision-test", "content": "hello world"}
    decision, verify = gate.client.calls
    assert decision[1]["actor"] == "hermes-test"
    assert verify[1]["tool_arguments"] == decision[1]["tool_arguments"]
    assert verify[1]["consume"] is True
    records = [json.loads(line) for line in gate.config.audit_file.read_text().splitlines()]
    assert [item["outcome"] for item in records] == ["requested", "authorized", "completed"]
    assert len({item["request_id"] for item in records}) == 1
    assert all(item["timestamp"].endswith("+00:00") for item in records)
    assert "hello" not in gate.config.audit_file.read_text()


@pytest.mark.parametrize("reply", [{"valid": True}, {"valid": False}, {"valid": True, "consumed": False},
                                   {"valid": 1, "consumed": True}, [], None])
def test_bad_verification_never_reads(gate, monkeypatch, reply):
    original = gate.client.post
    gate.client.post = lambda path, payload: reply if path.endswith("verify") else original(path, payload)
    monkeypatch.setattr(module, "read_file", lambda *args: pytest.fail("read before authorization"))
    assert gate.execute("lexecon_read_file", {"path": "hello.txt"})["ok"] is False


@pytest.mark.parametrize("decision", ["deny", "escalate", None, "PERMIT"])
def test_policy_denial_stops_before_verify(gate, decision):
    gate.client.decision = decision
    assert gate.execute("lexecon_read_file", {"path": "hello.txt"})["error"] == "policy_denied"
    assert len(gate.client.calls) == 1


@pytest.mark.parametrize("error", [TimeoutError("secret"), ConnectionError("secret"),
                                  GateError("authentication_required"), ValueError("secret")])
def test_transport_and_expired_session_fail_closed(gate, error):
    def failure(*args):
        raise error
    gate.client.post = failure
    result = gate.execute("lexecon_read_file", {"path": "hello.txt"})
    assert result["ok"] is False and "secret" not in json.dumps(result)


@pytest.mark.parametrize("grant", [{}, {"arguments_digest": "0" * 64}, "opaque"])
def test_unbound_grants_rejected(gate, grant):
    gate.client.post = lambda *args: {"decision": "permit", "decision_id": "test", "capability_token": grant}
    assert gate.execute("lexecon_read_file", {"path": "hello.txt"})["error"] == "unbound_or_mismatched_grant"


@pytest.mark.parametrize("path", ["../outside.txt", "/outside.txt", ".env", "secret.txt", "auth.md",
                                "nested/../hello.txt", "nested//hello.txt", "hello.json", "hello\\txt",
                                "session.txt", "node_modules/a.txt", "a\n.txt", ""])
def test_unsafe_paths_do_not_request_permission(gate, path):
    assert gate.execute("lexecon_read_file", {"path": path})["ok"] is False
    assert gate.client.calls == []


def test_symlinks_and_hardlinks_never_return_content(gate, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    (gate.config.workspace_root / "linked.txt").symlink_to(outside)
    os.link(outside, gate.config.workspace_root / "hard.txt")
    for name in ("linked.txt", "hard.txt"):
        assert gate.execute("lexecon_read_file", {"path": name})["ok"] is False
    assert gate.execute("lexecon_list_files", {"path": "."})["entries"] == [{"name": "hello.txt", "type": "file"}]


def test_symlink_directory_ancestor_rejected(gate, tmp_path):
    (tmp_path / "alias").symlink_to(gate.config.workspace_root, target_is_directory=True)
    config = GateConfig(tmp_path.resolve() / "alias", "hermes-test", gate.config.session_file, gate.config.audit_file)
    assert GateRuntime(config, Client()).execute("lexecon_read_file", {"path": "hello.txt"})["ok"] is False


def test_swap_path_to_symlink_between_decision_and_read(gate, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    original = gate.client.post
    def swap(path, payload):
        response = original(path, payload)
        if path.endswith("verify"):
            (gate.config.workspace_root / "hello.txt").unlink()
            (gate.config.workspace_root / "hello.txt").symlink_to(outside)
        return response
    gate.client.post = swap
    assert gate.execute("lexecon_read_file", {"path": "hello.txt"})["ok"] is False


@pytest.mark.parametrize("content", [b"\x00binary", b"\xff", b"x" * (MAX_BYTES + 1)])
def test_nontext_and_oversized_files_rejected(gate, content):
    (gate.config.workspace_root / "hello.txt").write_bytes(content)
    assert gate.execute("lexecon_read_file", {"path": "hello.txt"})["ok"] is False


@pytest.mark.parametrize("fail_at", [1, 2, 3])
def test_audit_failure_never_reports_success(gate, monkeypatch, fail_at):
    class BrokenAudit:
        calls = 0
        def append(self, record):
            self.calls += 1
            if self.calls >= fail_at:
                raise OSError("unavailable")
    gate.audit = BrokenAudit()
    if fail_at < 3:
        monkeypatch.setattr(module, "read_file", lambda *args: pytest.fail("read before audit"))
    assert gate.execute("lexecon_read_file", {"path": "hello.txt"}) == {"ok": False, "error": "audit_unavailable"}


def test_concurrent_audit_lines_remain_valid(gate):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: gate.execute("lexecon_read_file", {"path": "hello.txt"}), range(12)))
    assert all(result["ok"] for result in results), results
    assert len([json.loads(line) for line in gate.config.audit_file.read_text().splitlines()]) == 36


def test_private_credentials_require_owner_mode_and_no_symlink(gate, monkeypatch):
    monkeypatch.setattr(module.http.client, "HTTPConnection", lambda *a, **kw: pytest.fail("network attempted"))
    client = LoopbackClient(gate.config.session_file)
    gate.config.session_file.chmod(0o644)
    with pytest.raises(GateError):
        client.post("/decide", {})
    gate.config.session_file.chmod(0o600)
    renamed = gate.config.session_file.with_name("other")
    gate.config.session_file.rename(renamed)
    gate.config.session_file.symlink_to(renamed)
    with pytest.raises(OSError):
        client.post("/decide", {})


def test_http_transport_is_fixed_loopback_and_never_follows_redirect(gate, monkeypatch):
    calls = []
    class Response:
        status = 302
    class Connection:
        def __init__(self, host, port, timeout):
            calls.append((host, port, timeout))
        def request(self, *args):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            calls.append("closed")
    monkeypatch.setattr(module.http.client, "HTTPConnection", Connection)
    monkeypatch.setenv("HTTP_PROXY", "http://untrusted.invalid")
    with pytest.raises(GateError, match="request_denied"):
        LoopbackClient(gate.config.session_file).post("/decide", {})
    assert calls == [("127.0.0.1", 8000, 3), "closed"]


def test_hook_and_direct_handler_both_respect_boundary(gate, monkeypatch):
    assert pre_tool_call("terminal", {"command": "anything"})["action"] == "block"
    assert pre_tool_call("lexecon_read_file", {}) is None
    import lexecon_gate
    monkeypatch.setattr(lexecon_gate, "runtime_for_context", lambda ctx: gate)
    class Context:
        tools = {}
        def register_hook(self, name, callback):
            pass
        def register_tool(self, **kwargs):
            self.tools[kwargs["name"]] = kwargs["handler"]
    ctx = Context()
    register(ctx)
    gate.client.decision = "deny"
    result = json.loads(ctx.tools["lexecon_read_file"]({"path": "hello.txt"}))
    assert result["error"] == "policy_denied"


def test_private_state_inside_workspace_is_rejected(gate):
    cfg = GateConfig(gate.config.workspace_root, "hermes-test",
                     gate.config.workspace_root / "session", gate.config.audit_file)
    assert GateRuntime(cfg, Client()).execute("lexecon_read_file", {"path": "hello.txt"})["ok"] is False


def test_fifo_is_rejected_without_blocking(gate):
    os.mkfifo(gate.config.workspace_root / "pipe.txt")
    assert gate.execute("lexecon_read_file", {"path": "pipe.txt"})["ok"] is False


def test_session_ancestor_symlink_rejected(gate, tmp_path):
    alias = tmp_path.resolve() / "alias"
    alias.symlink_to(gate.config.session_file.parent, target_is_directory=True)
    with pytest.raises(OSError):
        LoopbackClient(alias / "session").post("/decide", {})


def test_session_hardlink_and_oversize_rejected(gate):
    os.link(gate.config.session_file, gate.config.session_file.with_name("linked"))
    with pytest.raises(GateError, match="private_file"):
        LoopbackClient(gate.config.session_file).post("/decide", {})
    gate.config.session_file.with_name("linked").unlink()
    gate.config.session_file.write_text("x" * 4097)
    with pytest.raises(GateError, match="invalid_session_file"):
        LoopbackClient(gate.config.session_file).post("/decide", {})


def test_audit_symlink_blocks_before_client(gate, tmp_path):
    destination = tmp_path / "unrelated"
    destination.write_text("unchanged")
    gate.config.audit_file.symlink_to(destination)
    assert gate.execute("lexecon_read_file", {"path": "hello.txt"}) == {"ok": False, "error": "audit_unavailable"}
    assert destination.read_text() == "unchanged"
    assert gate.client.calls == []


@pytest.mark.parametrize("identity", [{"user": {"username": "hermes-test", "role": "admin"}},
                                    {"user": {"username": "other", "role": "viewer"}},
                                    {"user": {"username": "hermes-test"}}, {}, None])
def test_admin_mismatched_or_malformed_identity_denied(gate, identity):
    gate.client.whoami = lambda: identity
    result = gate.execute("lexecon_read_file", {"path": "hello.txt"})
    assert result == {"ok": False, "error": "dedicated_nonadmin_identity_required"}
    assert gate.client.calls == []


def test_credential_pinned_across_call(gate, monkeypatch):
    sent = []
    class Response:
        status = 200
        def read(self, size):
            return b'{}'
    class Connection:
        def __init__(self, *args, **kwargs):
            pass
        def request(self, method, path, body, headers):
            sent.append(headers["Authorization"])
        def getresponse(self):
            return Response()
        def close(self):
            pass
    monkeypatch.setattr(module.http.client, "HTTPConnection", Connection)
    pinned = LoopbackClient(gate.config.session_file).for_call()
    pinned.whoami()
    gate.config.session_file.write_text("replacement-session-placeholder")
    pinned.post("/decide", {})
    pinned.post("/capability/verify", {})
    assert sent == ["Bearer test-session-placeholder-123456"] * 3
