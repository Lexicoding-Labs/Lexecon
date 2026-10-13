"""Tests exercise the live proof's core with fake dispatch and HTTP only."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("verify_live", ROOT / "verify_live.py")
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)


@pytest.fixture
def inputs():
    client = Mock()
    client.whoami.return_value = {"user": {"username": "hermes", "role": "viewer"}}
    client.post.return_value = {"decision": "deny", "decision_id": "deny_3"}
    results = [
        {"ok": True, "decision_id": "list_1", "entries": [{"name": "welcome.txt", "type": "file"}]},
        {"ok": True, "decision_id": "read_2", "content": proof.WELCOME},
        {"ok": False, "error": "path_not_allowed"},
    ]
    records = []
    for identifier, tool in (("list_1", "lexecon_list_files"), ("read_2", "lexecon_read_file")):
        for outcome, reason in (("authorized", "grant_consumed"), ("completed", "success")):
            records.append({"decision_id": identifier, "tool": tool, "request_id": identifier,
                            "arguments_digest": "digest", "outcome": outcome, "reason": reason})
    records.append({"tool": "lexecon_read_file", "outcome": "blocked", "reason": "path_not_allowed"})
    return client, results, records


def test_proof_checks_real_shapes_without_outputting_contents(inputs):
    client, results, records = inputs
    dispatch = Mock(side_effect=[json.dumps(result) for result in results])
    result = proof.run_proof(dispatch, client, lambda: records, "hermes")
    assert result["ok"] is True
    assert proof.WELCOME not in json.dumps(result)
    assert [call.args[0] for call in dispatch.call_args_list] == [
        "lexecon_list_files", "lexecon_read_file", "lexecon_read_file"]
    assert client.post.call_args.args[0] == "/decide"
    assert client.post.call_args.args[1]["proposed_action"] == "delete"
    assert result["denied"]["delete_policy_decision_id"] == "deny_3"


@pytest.mark.parametrize("user", [None, {"username": "hermes", "role": "admin"},
                                  {"username": "other", "role": "viewer"}])
def test_bad_identity_stops_before_dispatch(inputs, user):
    client, _, records = inputs
    client.whoami.return_value = {"user": user}
    dispatch = Mock()
    with pytest.raises(proof.ProofError, match="identity"):
        proof.run_proof(dispatch, client, lambda: records, "hermes")
    dispatch.assert_not_called()
    client.post.assert_not_called()


@pytest.mark.parametrize("position,replacement", [
    (0, {"ok": False, "error": "authentication_required"}),
    (1, {"ok": True, "decision_id": "read_2", "content": "changed"}),
    (2, {"ok": True, "content": "escaped"}),
])
def test_unexpected_tool_result_fails_proof(inputs, position, replacement):
    client, results, records = inputs
    results[position] = replacement
    with pytest.raises(proof.ProofError):
        proof.run_proof(Mock(side_effect=results), client, lambda: records, "hermes")


def test_policy_permit_is_not_reported_as_denial(inputs):
    client, results, records = inputs
    client.post.return_value = {"decision": "permit", "decision_id": "unsafe"}
    with pytest.raises(proof.ProofError, match="delete_policy_not_denied"):
        proof.run_proof(Mock(side_effect=results), client, lambda: records, "hermes")


def test_missing_audit_consumption_fails_proof(inputs):
    client, results, records = inputs
    records.pop(0)
    with pytest.raises(proof.ProofError, match="audit_sequence"):
        proof.run_proof(Mock(side_effect=results), client, lambda: records, "hermes")


def test_uncorrelated_audit_fails_proof(inputs):
    client, results, records = inputs
    records[1]["request_id"] = "other-request"
    with pytest.raises(proof.ProofError, match="audit_correlation"):
        proof.run_proof(Mock(side_effect=results), client, lambda: records, "hermes")


def test_main_hides_arbitrary_exception_content(monkeypatch, capsys):
    monkeypatch.setattr(proof, "settings_for", Mock(side_effect=RuntimeError("secret-token")))
    assert proof.main(["--home", "/not-used", "--hermes-checkout", "/not-used"]) == 1
    output = capsys.readouterr().out
    assert "secret-token" not in output
    assert json.loads(output)["ok"] is False
