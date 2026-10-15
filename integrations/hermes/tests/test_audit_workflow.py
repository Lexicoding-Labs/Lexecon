"""Offline tests for the pinned source-audit workflow."""

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
snapshot = importlib.import_module("audit_snapshot")
owner = importlib.import_module("owner_setup")
collection = importlib.import_module("collect_audit")
acceptance = importlib.import_module("audit_acceptance")
service = importlib.import_module("start_audit_service")


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE).decode().strip()


def test_pinned_snapshot_excludes_evaluation_runtime_and_uncommitted_changes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    for name, text in {"src/lexecon/core.py": "first = 1\nsecond = 2\n",
                       "src/lexecon/__init__.py": "",
                       "src/lexecon/tests/test_hidden.py": "held out\n",
                       "src/lexecon/held_out.py": "held out\n",
                       ".env": "not included\n", "tests/test_case.py": "not included\n"}.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
    revision = git(repo, "rev-parse", "HEAD")
    (repo / "src/lexecon/core.py").write_text("uncommitted = 99\n")
    home = owner.prepare(tmp_path / "pilot", api_port=8765)
    result = snapshot.prepare_snapshot(repo, revision, home)
    assert {row["source_path"] for row in result["records"]} == {"src/lexecon/core.py"}
    record = result["records"][0]
    assert (home / "workspace" / record["snapshot_path"]).read_text() == "first = 1\nsecond = 2\n"
    assert result["commit"] == revision
    assert record["line_start"] == 1 and record["line_end"] == 2
    empty = [row for row in result["excluded"] if row["reason"] == "empty_source"]
    assert empty == [{"path": "src/lexecon/__init__.py", "reason": "empty_source", "bytes": 0,
                      "sha256": hashlib.sha256(b"").hexdigest(),
                      "git_blob": git(repo, "rev-parse", f"{revision}:src/lexecon/__init__.py")}]
    assert len(result["excluded"]) + len({row["source_path"] for row in result["records"]}) == 6
    with pytest.raises(ValueError, match="exists"):
        snapshot.prepare_snapshot(repo, revision, home)


@pytest.mark.parametrize("change", ["content", "whitespace", "invalid_hash", "missing_hash"])
def test_collection_refuses_unreviewed_manifest_before_runtime_or_dispatch(tmp_path, monkeypatch, change):
    home = owner.prepare(tmp_path / "pilot", api_port=8765)
    manifest = home / "private/snapshot.json"
    original = '{"records": [], "commit": "reviewed"}\n'
    owner.private_file(manifest, original)
    expected = hashlib.sha256(original.encode()).hexdigest()
    if change == "content":
        manifest.write_text(original.replace("reviewed", "changed"))
    elif change == "whitespace":
        manifest.write_text(original + "\n")
    elif change == "invalid_hash":
        expected = "not-a-sha256"

    def forbidden(*args, **kwargs):
        pytest.fail("Unreviewed manifest reached runtime initialization or API activity")

    monkeypatch.setattr(collection, "initialize_required_runtime", forbidden)
    monkeypatch.setattr(owner, "request", forbidden)
    args = ["--home", str(home), "--hermes-checkout", str(tmp_path / "host"),
            "--source", "src/lexecon/core.py"]
    if change != "missing_hash":
        args += ["--manifest-sha256", expected]
    with pytest.raises(SystemExit if change == "missing_hash" else owner.SetupError):
        collection.main(args)
    assert not list((home / "private").glob("audit-run-*"))


def test_private_manifest_hash_uses_exact_bytes_before_parsing(tmp_path):
    home = owner.prepare(tmp_path / "pilot", api_port=8765)
    manifest = home / "private/snapshot.json"
    raw = b'{"records": [], "label": "caf\\u00e9"}\r\n'
    owner.private_file(manifest, raw.decode())
    expected = hashlib.sha256(raw).hexdigest()
    assert owner.read_private_json(manifest, expected_sha256=expected) == {"records": [], "label": "café"}
    with pytest.raises(owner.SetupError, match="reviewed SHA-256"):
        owner.read_private_json(manifest, expected_sha256=hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest())


def test_reviewed_manifest_reaches_runtime_only_after_validation(tmp_path, monkeypatch):
    home = owner.prepare(tmp_path / "pilot", api_port=8765)
    original = json.dumps({"records": [{"source_path": "src/lexecon/core.py"}]})
    owner.private_file(home / "private/snapshot.json", original)
    reached = []

    class StopBeforeActivation(Exception):
        pass

    def stopped(*args):
        reached.append(args)
        raise StopBeforeActivation

    monkeypatch.setattr(collection, "initialize_required_runtime", stopped)
    with pytest.raises(StopBeforeActivation):
        collection.main(["--home", str(home), "--hermes-checkout", str(tmp_path / "host"),
                         "--source", "src/lexecon/core.py",
                         "--manifest-sha256", hashlib.sha256(original.encode()).hexdigest()])
    assert len(reached) == 1


def test_chunking_preserves_exact_bytes_and_original_lines():
    data = ("é = 'sample'\n" * 4000).encode()
    pieces = list(snapshot.chunks(data))
    assert b"".join(row[2] for row in pieces) == data
    assert all(len(row[2]) <= snapshot.CHUNK_BYTES for row in pieces)
    assert sum(row[1] for row in pieces) == 4000
    assert pieces[1][0] == pieces[0][1] + 1


def test_interrupted_collection_remains_unknown_and_cannot_back_findings(tmp_path):
    record = {"snapshot_path": "code/00000.txt", "source_path": "src/lexecon/core.py",
              "line_start": 1, "line_end": 1, "sha256": hashlib.sha256(b"sample\n").hexdigest()}

    def interrupted(*args):
        raise KeyboardInterrupt

    destination = tmp_path / "evidence"
    with pytest.raises(KeyboardInterrupt):
        collection.collect_reads(interrupted, [record], destination)
    rows = [json.loads(row) for row in (destination / "attempts.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["state"] == "Unknown"
    report = {"findings": [{"claim": "Unverified", "references": [{"read_id": rows[0]["read_id"]}]}]}
    with pytest.raises(ValueError):
        collection.validate_findings(report, {"commit": "pinned", "reads": rows})


def test_failed_corroboration_keeps_returned_bytes_unknown(tmp_path):
    content = "sample\n"
    record = {"snapshot_path": "code/00000.txt", "source_path": "src/lexecon/core.py",
              "line_start": 1, "line_end": 1, "sha256": hashlib.sha256(content.encode()).hexdigest()}
    destination = tmp_path / "evidence"

    def unavailable(*args):
        raise RuntimeError("Decision ledger unavailable; attempt remains Unknown")

    with pytest.raises(RuntimeError, match="Unknown"):
        collection.collect_reads(lambda *args: {"ok": True, "decision_id": "dec_1", "content": content},
                                 [record], destination, unavailable)
    rows = [json.loads(row) for row in (destination / "attempts.jsonl").read_text().splitlines()]
    assert [row["state"] for row in rows] == ["Unknown"]
    assert list((destination / "reads").iterdir()) == []


def test_collected_read_requires_gate_and_matching_service_decision():
    from lexecon.ledger.chain import LedgerEntry

    digest = "a" * 64
    request_id, decision_id = "request-1", "dec_1"
    gate = [{"request_id": request_id, "decision_id": None, "tool": "lexecon_read_file",
             "action": "read", "arguments_digest": digest, "outcome": "requested", "reason": "policy_check"},
            {"request_id": request_id, "decision_id": decision_id, "tool": "lexecon_read_file",
             "action": "read", "arguments_digest": digest, "outcome": "authorized", "reason": "grant_consumed"},
            {"request_id": request_id, "decision_id": decision_id, "tool": "lexecon_read_file",
             "action": "read", "arguments_digest": digest, "outcome": "completed", "reason": "success"}]
    entry = LedgerEntry(entry_id="entry_1", event_type="decision", timestamp="fixture",
                        previous_hash="0" * 64, data={"decision_id": decision_id,
                        "request_id": request_id, "decision": "permit", "actor": "audit-viewer",
                        "action": "read", "tool": "lexecon_read_file", "arguments_digest": digest,
                        "evaluation_source": "policy_engine"}).to_dict()
    ledger = {"entries": [entry]}
    proof = collection.correlate_read(decision_id, gate, ledger, digest, "audit-viewer")
    assert proof == {"gate_records": gate, "ledger_entry": entry}
    for bad_gate, bad_ledger, bad_digest, bad_actor in (
        (gate[:2], ledger, digest, "audit-viewer"),
        ([*gate, gate[-1]], ledger, digest, "audit-viewer"),
        (gate, {"entries": []}, digest, "audit-viewer"),
        (gate, ledger, "b" * 64, "audit-viewer"),
        (gate, ledger, digest, "other-viewer"),
        (gate, {"entries": [{**entry, "entry_hash": "0" * 64}]}, digest, "audit-viewer"),
    ):
        with pytest.raises(RuntimeError, match="Unknown"):
            collection.correlate_read(decision_id, bad_gate, bad_ledger, bad_digest, bad_actor)


@pytest.mark.parametrize("matching_ledger", [True, False])
def test_collection_entrypoint_requires_correlated_ledger_before_observed_read(
        tmp_path, monkeypatch, matching_ledger):
    from lexecon.ledger.chain import LedgerEntry
    from lexecon_gate import runtime

    home = owner.prepare(tmp_path / "pilot", api_port=8765)
    settings = owner.settings_for(home)[1]
    content = "sample\n"
    record = {"snapshot_path": "code/00000.txt", "source_path": "src/lexecon/core.py",
              "line_start": 1, "line_end": 1, "sha256": hashlib.sha256(content.encode()).hexdigest()}
    manifest = json.dumps({"records": [record], "commit": "pinned", "tree": "tree"})
    owner.private_file(home / "private/snapshot.json", manifest)
    audit_path = Path(settings["audit_file"])
    owner.private_file(audit_path, "")
    root = Path(settings["workspace_root"])
    info = root.stat()
    digest = runtime.arguments_digest({"workspace_root": str(root), "workspace_device": info.st_dev,
                                       "workspace_inode": info.st_ino, "path": record["snapshot_path"]})
    entry = LedgerEntry(entry_id="entry_1", event_type="decision", timestamp="fixture",
                        previous_hash="0" * 64, data={"decision_id": "dec_1", "request_id": "req_1",
                        "decision": "permit", "actor": settings["username"], "action": "read",
                        "tool": "lexecon_read_file", "arguments_digest": digest if matching_ledger else "b" * 64,
                        "evaluation_source": "policy_engine"}).to_dict()
    client = SimpleNamespace(whoami=lambda: {"user": {"username": settings["username"], "role": "viewer"}},
                             ledger_entries=lambda: {"entries": [entry]})
    monkeypatch.setattr(runtime.LoopbackClient, "for_call", lambda self: client)

    def dispatch(tool, arguments):
        assert tool == "lexecon_read_file" and arguments == {"path": record["snapshot_path"]}
        for outcome, reason, decision in (("requested", "policy_check", None),
                                          ("authorized", "grant_consumed", "dec_1"),
                                          ("completed", "success", "dec_1")):
            collection.append_journal(audit_path, {"request_id": "req_1", "decision_id": decision,
                                                   "tool": tool, "action": "read", "arguments_digest": digest,
                                                   "outcome": outcome, "reason": reason})
        return {"ok": True, "decision_id": "dec_1", "content": content}

    host = SimpleNamespace(plugin=importlib.import_module("lexecon_gate"),
                           model_tools=SimpleNamespace(handle_function_call=dispatch))
    monkeypatch.setattr(collection, "initialize_required_runtime", lambda *args: host)
    args = ["--home", str(home), "--hermes-checkout", str(tmp_path / "unused-host"),
            "--source", record["source_path"],
            "--manifest-sha256", hashlib.sha256(manifest.encode()).hexdigest()]
    if matching_ledger:
        assert collection.main(args) == 0
    else:
        with pytest.raises(RuntimeError, match="Unknown"):
            collection.main(args)
    output = next((home / "private").glob("audit-run-*"))
    rows = [json.loads(row) for row in (output / "attempts.jsonl").read_text().splitlines()]
    assert [row["state"] for row in rows] == (["Unknown", "ObservedRead"] if matching_ledger
                                               else ["Unknown"])
    if matching_ledger:
        evidence = json.loads((output / "evidence.json").read_text())
        assert evidence["version"] == 2
        assert evidence["reads"][0]["ledger_entry"] == entry
        assert len(evidence["reads"][0]["gate_records"]) == 3
    else:
        assert not (output / "evidence.json").exists()
        assert list((output / "reads").iterdir()) == []


def test_only_matching_gated_bytes_revision_and_lines_support_report(tmp_path):
    record = {"snapshot_path": "code/00000.txt", "source_path": "src/lexecon/core.py",
              "line_start": 20, "line_end": 21, "sha256": hashlib.sha256(b"a\nb\n").hexdigest()}
    reads = collection.collect_reads(lambda *args: {"ok": True, "decision_id": "fixture", "content": "a\nb\n"},
                                     [record], tmp_path / "evidence")
    evidence = {"commit": "pinned", "reads": reads}
    reference = {"read_id": reads[0]["read_id"], "path": record["source_path"], "revision": "pinned",
                 "line_start": 20, "line_end": 21}
    report = {"findings": [{"claim": "Fixture claim, not an audit finding", "references": [reference]}]}
    assert collection.validate_findings(report, evidence)
    reference["line_end"] = 22
    with pytest.raises(ValueError):
        collection.validate_findings(report, evidence)


def interruption_evidence():
    from lexecon.ledger.chain import LedgerEntry

    digest = "a" * 64
    after = [{"request_id": "r", "decision_id": decision, "arguments_digest": digest,
              "tool": "lexecon_read_file", "action": "read", "outcome": outcome, "reason": reason}
             for outcome, reason, decision in (("requested", "policy_check", None),
                                               ("authorized", "grant_consumed", "d"),
                                               ("completed", "success", "d"))]
    data = {"decision_id": "d", "request_id": "r", "arguments_digest": digest,
            "decision": "permit", "actor": "audit-viewer", "action": "read",
            "tool": "lexecon_read_file", "evaluation_source": "policy_engine"}
    entry = LedgerEntry(entry_id="entry_1", event_type="decision", timestamp="fixture",
                        previous_hash="0" * 64, data=data).to_dict()
    return after, {"entries": [entry]}


@pytest.mark.parametrize("failure", ["no_audit", "no_ledger", "wrong_digest", "wrong_probe",
                                     "multiple_reads"])
def test_reconciliation_needs_fresh_agreement(failure):
    after, ledger = interruption_evidence()
    assert acceptance.reconcile_interruption([], after, ledger, "a" * 64,
                                             "audit-viewer")["state"] == "ObservedCompletedRead"
    if failure == "no_audit":
        after = []
    elif failure == "no_ledger":
        ledger = {"entries": []}
    elif failure == "wrong_digest":
        ledger["entries"][0]["data"]["arguments_digest"] = "b" * 64
    elif failure == "wrong_probe":
        assert acceptance.reconcile_interruption([], after, ledger, "b" * 64,
                                                 "audit-viewer") == {"state": "Unknown"}
        return
    else:
        after.append(dict(after[-1]))
    assert acceptance.reconcile_interruption([], after, ledger, "a" * 64,
                                             "audit-viewer") == {"state": "Unknown"}


@pytest.mark.parametrize("failure", ["requested_reason", "authorized_reason", "completed_reason",
                                     "wrong_action", "blocked_same_request", "extra_requested",
                                     "out_of_order", "altered_prior_audit", "reused_request_id"])
def test_reconciliation_rejects_inconsistent_lifecycle(failure):
    after, ledger = interruption_evidence()
    before = []
    if failure == "requested_reason":
        after[0]["reason"] = "unexpected"
    elif failure == "authorized_reason":
        after[1]["reason"] = "unexpected"
    elif failure == "completed_reason":
        after[2]["reason"] = "unexpected"
    elif failure == "wrong_action":
        after[1]["action"] = "list"
    elif failure == "blocked_same_request":
        after.insert(2, {**after[1], "outcome": "blocked", "reason": "verification_denied"})
    elif failure == "extra_requested":
        after.insert(1, dict(after[0]))
    elif failure == "out_of_order":
        after[1], after[2] = after[2], after[1]
    elif failure == "altered_prior_audit":
        before = [{"request_id": "old", "outcome": "blocked"}]
        after.insert(0, {"request_id": "old", "outcome": "completed"})
    else:
        before = [{"request_id": "r", "outcome": "blocked"}]
        after.insert(0, dict(before[0]))
    assert acceptance.reconcile_interruption(before, after, ledger, "a" * 64,
                                             "audit-viewer") == {"state": "Unknown"}


@pytest.mark.parametrize("failure", ["wrong_actor", "wrong_action", "wrong_tool",
                                     "wrong_source", "second_same_request_decision", "bad_hash"])
def test_reconciliation_rejects_inconsistent_ledger(failure):
    from lexecon.ledger.chain import LedgerEntry

    after, ledger = interruption_evidence()
    data = dict(ledger["entries"][0]["data"])
    if failure == "wrong_actor":
        data["actor"] = "someone-else"
    elif failure == "wrong_action":
        data["action"] = "list"
    elif failure == "wrong_tool":
        data["tool"] = "lexecon_list_files"
    elif failure == "wrong_source":
        data["evaluation_source"] = "fallback"
    elif failure == "second_same_request_decision":
        data["decision_id"] = "other"
        ledger["entries"].append(LedgerEntry(entry_id="entry_2", event_type="decision",
                                             timestamp="fixture", previous_hash="0" * 64,
                                             data=data).to_dict())
    else:
        ledger["entries"][0]["entry_hash"] = "0" * 64
    if failure not in {"second_same_request_decision", "bad_hash"}:
        ledger["entries"] = [LedgerEntry(entry_id="entry_1", event_type="decision",
                                         timestamp="fixture", previous_hash="0" * 64,
                                         data=data).to_dict()]
    assert acceptance.reconcile_interruption([], after, ledger, "a" * 64,
                                             "audit-viewer") == {"state": "Unknown"}


@pytest.mark.parametrize("mode", ["matching", "wrong_digest", "blocked_same_request"])
def test_interruption_probe_links_unique_fixture_and_removes_it(tmp_path, mode):
    from lexecon.ledger.chain import LedgerEntry
    from lexecon_gate import runtime
    from verify_live import ProofError

    home = owner.prepare(tmp_path / "pilot", api_port=8765)
    settings = owner.settings_for(home)[1]
    rows, ledger = [], {"entries": []}

    def dispatch(tool, arguments):
        assert tool == "lexecon_read_file"
        assert arguments["path"].startswith("validation-") and arguments["path"].endswith(".txt")
        root = Path(settings["workspace_root"])
        assert (root / arguments["path"]).is_file()
        info = root.stat()
        digest = runtime.arguments_digest({"workspace_root": str(root), "workspace_device": info.st_dev,
                                           "workspace_inode": info.st_ino, "path": arguments["path"]})
        if mode == "wrong_digest":
            digest = "b" * 64
        for outcome, reason, decision in (("requested", "policy_check", None),
                                          ("authorized", "grant_consumed", "dec_1"),
                                          ("completed", "success", "dec_1")):
            rows.append({"request_id": "req_1", "decision_id": decision,
                         "arguments_digest": digest, "tool": tool, "action": "read",
                         "outcome": outcome, "reason": reason})
        if mode == "blocked_same_request":
            rows.append({**rows[-1], "outcome": "blocked", "reason": "gate_unavailable"})
        ledger["entries"].append(LedgerEntry(entry_id="entry_1", event_type="decision",
                                              timestamp="fixture", previous_hash="0" * 64, data={
            "request_id": "req_1", "decision_id": "dec_1", "arguments_digest": digest,
            "decision": "permit", "actor": settings["username"], "action": "read",
            "tool": tool, "evaluation_source": "policy_engine"}).to_dict())
        return {"ok": True, "decision_id": "dec_1", "content": "discarded response"}

    host = SimpleNamespace(home=home, settings=settings,
                           plugin=importlib.import_module("lexecon_gate"),
                           model_tools=SimpleNamespace(handle_function_call=dispatch))
    client = SimpleNamespace(ledger_entries=lambda: ledger)
    if mode == "matching":
        result = acceptance.interruption_probe(host, client, lambda: list(rows))
        assert result["state"] == "ObservedCompletedRead" and result["initial"] == "Unknown"
    else:
        with pytest.raises(ProofError, match="interruption_remains_unknown"):
            acceptance.interruption_probe(host, client, lambda: list(rows))
    assert not list((home / "workspace").glob("validation-*.txt"))
    journal = next((home / "private").glob("validation-interruption-*.jsonl"))
    states = [json.loads(line)["state"] for line in journal.read_text().splitlines()]
    assert states == (["Unknown", "ObservedCompletedRead"] if mode == "matching"
                      else ["Unknown", "Unknown"])


def test_isolated_service_environment_excludes_inherited_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("OIDC_GOOGLE_CLIENT_SECRET", "fixture-value")
    monkeypatch.setenv("LEXECON_DATA_DIR", "/live-state")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-value")
    env = service.isolated_environment(tmp_path)
    assert env["LEXECON_DATA_DIR"] == str(tmp_path)
    assert "OIDC_GOOGLE_CLIENT_SECRET" not in env and "OPENAI_API_KEY" not in env
    assert env["LEXECON_BASE_URL"] == "http://127.0.0.1:8765"


@pytest.mark.parametrize("answer", ["", "wrong phrase", EOFError, KeyboardInterrupt])
def test_startup_cancellation_is_clean_and_has_no_setup_effects(monkeypatch, tmp_path, capsys, answer):
    home = owner.prepare(tmp_path / "pilot", api_port=8765)
    monkeypatch.setattr(service.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(service.socket, "socket", MagicMock())

    def respond(_):
        if isinstance(answer, type):
            raise answer
        return answer

    def forbidden(*args, **kwargs):
        pytest.fail("Cancelled startup reached credentials or a subprocess")

    monkeypatch.setattr("builtins.input", respond)
    monkeypatch.setattr(service.getpass, "getpass", forbidden)
    monkeypatch.setattr(service.subprocess, "run", forbidden)
    monkeypatch.setattr(service.subprocess, "call", forbidden)
    assert service.main(["--home", str(home)]) == 1
    captured = capsys.readouterr()
    assert "Cancelled" in captured.out and "retry" in captured.out
    assert "Traceback" not in captured.out + captured.err
    assert not (home / "private/service-state").exists()
    assert not (home / "private/session").exists()


@pytest.mark.parametrize("port", [True, 0, 443, "8765", -1, 65536])
def test_transport_rejects_unapproved_ports(port):
    from lexecon_gate.runtime import GateError, LoopbackClient

    with pytest.raises(GateError, match="api_port"):
        LoopbackClient(Path("/unused"), port)


def test_audit_port_is_preserved_in_session_snapshot(monkeypatch):
    from lexecon_gate.runtime import LoopbackClient

    monkeypatch.setattr(LoopbackClient, "_read_token", lambda self: "fixture-session-never-live")
    client = LoopbackClient(Path("/unused"), 8765).for_call()
    assert client.api_port == 8765
    assert client._token == "fixture-session-never-live"


def test_reconciliation_fetch_is_bounded_to_recent_ledger_entries(monkeypatch):
    from lexecon_gate.runtime import LoopbackClient

    paths = []
    def request(self, method, path):
        paths.append(path)
        return {"total": 500, "entries": []}
    monkeypatch.setattr(LoopbackClient, "_request", request)
    LoopbackClient(Path("/unused"), 8765).ledger_entries()
    assert paths == ["/ledger/entries?event_type=decision&limit=1",
                     "/ledger/entries?event_type=decision&limit=32&offset=468"]
