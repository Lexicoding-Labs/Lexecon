"""Owner setup tests use temporary files and mocked HTTP/password entry only."""

import importlib.util
import json
import stat
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

SPEC = importlib.util.spec_from_file_location("owner_setup", Path(__file__).parents[1] / "owner_setup.py")
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)
TOKEN = "test_session_for_in_memory_tests_only"


@pytest.fixture
def home(tmp_path):
    return setup.prepare(tmp_path.resolve() / "hermes-isolated")


@pytest.fixture
def settings(home):
    return setup.settings_for(home)[1]


def login_result(username="lexecon_hermes", role="viewer", **kwargs):
    return {"success": True, "session_id": TOKEN, "user": {"username": username, "role": role}, **kwargs}


@pytest.mark.parametrize("answer", ["activate isolated audit", "Activate isolated audit ",
                                    "  ACTIVATE ISOLATED AUDIT\t"])
def test_confirmation_accepts_case_and_surrounding_whitespace(monkeypatch, answer):
    monkeypatch.setattr("builtins.input", lambda _: answer)
    setup.confirm("activate isolated audit", "Fixture confirmation")


@pytest.mark.parametrize("answer", ["", "   ", "yes", "activate", "activate another audit",
                                    "activate isolated audit now", "activate  isolated audit"])
def test_confirmation_still_requires_the_complete_phrase(monkeypatch, answer):
    monkeypatch.setattr("builtins.input", lambda _: answer)
    with pytest.raises(setup.SetupError, match="Run the command again"):
        setup.confirm("activate isolated audit", "Fixture confirmation")


def test_prepare_permissions_and_bounded_profile(home):
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
    assert stat.S_IMODE((home / "private").stat().st_mode) == 0o700
    assert (home / "workspace/welcome.txt").read_text().startswith("Welcome")
    assert (home / "plugins/lexecon-gate/plugin.yaml").is_file()
    config = json.loads((home / "config.yaml").read_text())
    assert config["platform_toolsets"]["cli"] == ["lexecon_workspace"]
    assert config["tools"]["tool_search"]["enabled"] is False
    assert config["plugins"]["enabled"] == ["lexecon-gate"]
    assert config["required_tool_gate"] == {
        "plugin": "lexecon-gate", "tools": ["lexecon_list_files", "lexecon_read_file"]}
    assert not (home / "private/session").exists()
    policy = json.loads((home / "starter-policy.json").read_text())
    assert {r["action"] for r in policy["relations"]} == {
        "action:read", "action:list", "tool:lexecon_read_file", "tool:lexecon_list_files"}
    assert all(r["subject"] == "actor:lexecon_hermes" for r in policy["relations"])


def test_prepare_refuses_overwrite(home):
    with pytest.raises(setup.SetupError, match="overwrite"):
        setup.prepare(home)


def test_prepare_refuses_symlink_parent(tmp_path):
    link = tmp_path / "alias"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(setup.SetupError, match="Symlink"):
        setup.prepare(link / "new-home")


def test_profile_cannot_redirect_credentials_into_workspace(home):
    path = home / "config.yaml"
    config = json.loads(path.read_text())
    config["plugins"]["entries"]["lexecon-gate"]["settings"]["session_file"] = str(home / "workspace/session")
    path.write_text(json.dumps(config))
    with pytest.raises(setup.SetupError, match="Invalid isolated"):
        setup.settings_for(home)


@pytest.mark.parametrize("replacement", [
    "- not-a-mapping\n",
    "plugins: {}\nplugins: {}\n",
    "plugins: !!python/object/apply:os.system ['echo forbidden']\n",
    "plugins: {entries: {lexecon-gate: {settings: {api_port: 8765, api_port: 8000}}}}\n",
])
def test_profile_rejects_unsafe_or_ambiguous_yaml(home, replacement):
    """Unsafe tags, duplicate keys, and non-mappings cannot define the profile."""
    (home / "config.yaml").write_text(replacement)
    with pytest.raises(setup.SetupError, match="Invalid isolated"):
        setup.settings_for(home)


def test_yaml_profile_cannot_redirect_session_into_workspace(home):
    """YAML must preserve the same private-session boundary as JSON."""
    path = home / "config.yaml"
    config = json.loads(path.read_text())
    config["plugins"]["entries"]["lexecon-gate"]["settings"]["session_file"] = str(home / "workspace/session")
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(setup.SetupError, match="Invalid isolated"):
        setup.settings_for(home)


def test_login_requires_confirmation_and_stores_only_session(monkeypatch, settings, capsys):
    request = Mock(return_value=login_result())
    monkeypatch.setattr(setup, "request", request)
    monkeypatch.setattr("builtins.input", lambda _: "login")
    monkeypatch.setattr(setup.getpass, "getpass", lambda _: "owner entered password")
    setup.login(settings)
    path = Path(settings["session_file"])
    assert path.read_text().strip() == TOKEN
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert TOKEN not in capsys.readouterr().out
    assert request.call_args.args[:2] == ("POST", "/auth/login")
    with pytest.raises(setup.SetupError, match="already exists"):
        setup.login(settings)
    assert request.call_count == 1


@pytest.mark.parametrize("result", [
    login_result(role="admin"), login_result(success=False), login_result(user=None),
    login_result(username="someone_else"), login_result(role="unknown"),
])
def test_login_rejects_invalid_auth_and_revokes(monkeypatch, settings, result):
    request = Mock(side_effect=[result, {"success": True}])
    monkeypatch.setattr(setup, "request", request)
    monkeypatch.setattr("builtins.input", lambda _: "login")
    monkeypatch.setattr(setup.getpass, "getpass", lambda _: "not a real credential")
    with pytest.raises(setup.SetupError):
        setup.login(settings)
    assert not Path(settings["session_file"]).exists()
    assert request.call_args.args == ("POST", "/auth/logout")


def test_login_cancelled_never_contacts_api(monkeypatch, settings):
    request = Mock()
    monkeypatch.setattr(setup, "request", request)
    monkeypatch.setattr("builtins.input", lambda _: "no")
    with pytest.raises(setup.SetupError, match="Cancelled"):
        setup.login(settings)
    request.assert_not_called()


def test_private_file_rejects_symlink_and_public_parent(home):
    destination = home / "private/session"
    victim = home / "outside"
    victim.write_text("untouched")
    destination.symlink_to(victim)
    with pytest.raises(setup.SetupError):
        setup.private_file(destination, TOKEN)
    assert victim.read_text() == "untouched"
    destination.unlink()
    destination.parent.chmod(0o755)
    with pytest.raises(setup.SetupError):
        setup.private_file(destination, TOKEN)


def test_provision_existing_identity_never_resets_password(monkeypatch, settings):
    request = Mock(side_effect=[login_result("admin", "admin"), {"users": [
        {"username": settings["username"], "role": "viewer", "is_active": True}]}, {"success": True}])
    monkeypatch.setattr(setup, "request", request)
    monkeypatch.setattr("builtins.input", lambda _: "admin")
    passwords = Mock(return_value="owner entered admin password")
    monkeypatch.setattr(setup.getpass, "getpass", passwords)
    setup.provision(settings)
    assert [call.args[1] for call in request.call_args_list] == ["/auth/login", "/auth/users", "/auth/logout"]
    assert request.call_args_list[1].args[0] == "GET"
    assert passwords.call_count == 1


def test_provision_requires_confirmation_and_owner_password_twice(monkeypatch, settings):
    request = Mock(side_effect=[login_result("admin", "admin"), {"users": []}, {"success": True}, {"success": True}])
    monkeypatch.setattr(setup, "request", request)
    answers = iter(["admin", "create lexecon_hermes"])
    passwords = iter(["admin credential", "dedicated credential", "dedicated credential"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(setup.getpass, "getpass", lambda _: next(passwords))
    setup.provision(settings)
    payload = request.call_args_list[2].args[2]
    assert payload["role"] == "viewer"
    assert payload["password"] == "dedicated credential"
    assert request.call_args.args[1] == "/auth/logout"
    assert not Path(settings["session_file"]).exists()


def test_provision_mismatch_revokes_admin_session(monkeypatch, settings):
    request = Mock(side_effect=[login_result("admin", "admin"), {"users": []}, {"success": True}])
    monkeypatch.setattr(setup, "request", request)
    answers = iter(["admin", "create lexecon_hermes"])
    passwords = iter(["admin credential", "a", "b"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(setup.getpass, "getpass", lambda _: next(passwords))
    with pytest.raises(setup.SetupError, match="match"):
        setup.provision(settings)
    assert request.call_count == 3
    assert request.call_args.args[1] == "/auth/logout"


def test_policy_replace_cancelled_before_login(monkeypatch, home, capsys):
    request = Mock()
    monkeypatch.setattr(setup, "request", request)
    monkeypatch.setattr("builtins.input", lambda _: "no")
    with pytest.raises(setup.SetupError, match="Cancelled"):
        setup.load_policy(home, allow_nonempty=True)
    request.assert_not_called()
    assert "ALL callers" in capsys.readouterr().out



def test_logout_removes_only_after_confirmed_revocation(monkeypatch, settings):
    path = Path(settings["session_file"])
    setup.private_file(path, TOKEN)
    monkeypatch.setattr(setup, "request", Mock(return_value={"success": False}))
    with pytest.raises(setup.SetupError):
        setup.logout(settings)
    assert path.exists()
    monkeypatch.setattr(setup, "request", Mock(return_value={"success": True}))
    setup.logout(settings)
    assert not path.exists()


def test_status_is_strictly_offline(monkeypatch, home, settings, capsys):
    request = Mock()
    monkeypatch.setattr(setup, "request", request)
    setup.status(home, settings)
    request.assert_not_called()
    assert "validity are not checked" in capsys.readouterr().out


@pytest.mark.parametrize("status,body", [(302, b"{}"), (401, b"{}"), (200, b"[]"), (200, b"bad"), (200, b"a" * 65537)])
def test_transport_rejects_redirects_errors_and_bad_json(monkeypatch, status, body):
    response = Mock(status=status)
    response.read.return_value = body
    connection = Mock()
    connection.getresponse.return_value = response
    factory = Mock(return_value=connection)
    monkeypatch.setattr(setup.http.client, "HTTPConnection", factory)
    with pytest.raises(setup.SetupError):
        setup.request("POST", "/auth/login", {})
    factory.assert_called_once_with("127.0.0.1", 8000, timeout=5)
    connection.close.assert_called_once()



def test_atomic_session_install_never_overwrites(home):
    path = home / "private/session"
    setup.private_file(path, TOKEN)
    with pytest.raises(setup.SetupError, match="already exists"):
        setup.private_file(path, "another_session_that_must_not_replace")
    assert path.read_text() == TOKEN
    assert not list(path.parent.glob(".session-*"))


def test_session_rejects_hardlink_and_symlink_ancestors(home):
    path = home / "private/session"
    setup.private_file(path, TOKEN)
    alias = home / "private/alias"
    alias.hardlink_to(path)
    with pytest.raises(setup.SetupError, match="one link"):
        setup.read_session(path)
    alias.unlink()
    ancestor = home / "alias"
    ancestor.symlink_to(path.parent, target_is_directory=True)
    with pytest.raises(setup.SetupError, match="Symlink"):
        setup.read_session(ancestor / "session")


def test_main_preserves_safe_error_but_hides_raw_exception(monkeypatch, home, capsys):
    assert setup.main(["prepare", "--home", str(home)]) == 1
    assert "refusing to overwrite" in capsys.readouterr().out
    monkeypatch.setattr(setup, "settings_for", Mock(side_effect=OSError("secret example")))
    assert setup.main(["status", "--home", str(home)]) == 1
    assert "secret example" not in capsys.readouterr().out


@pytest.fixture
def policy_api(monkeypatch):
    from lexecon.policy.engine import PolicyEngine

    engine = PolicyEngine({"mode": "permissive", "terms": [], "relations": [
        {"type": "forbids", "subject": "actor:prior", "action": "action:delete"}]})
    state = {"engine": engine, "calls": [], "lose_response": False, "fail_exports": False}

    def request(method, path, payload=None, token=None):
        state["calls"].append((method, path, payload))
        if path == "/auth/login":
            return login_result("admin", "admin")
        if path == "/auth/logout":
            return {"success": True}
        assert token == TOKEN
        if path == "/policies/export":
            if state["fail_exports"]:
                raise setup.SetupError("unknown")
            return engine.export_policy()
        assert path == "/policies/load"
        snapshot = engine.load_policy(payload["policy"], expected_policy_hash=payload["expected_policy_hash"])
        if state["lose_response"]:
            raise setup.SetupError("Response lost")
        return {"status": "success", **snapshot}

    monkeypatch.setattr(setup, "request", request)
    monkeypatch.setattr(setup.getpass, "getpass", lambda _: "owner credential")
    return state


def answer(monkeypatch, *answers):
    responses = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _: next(responses))


def snapshots(home):
    return [path for path in (home / "private").glob("policy-*.json")
            if len(path.stem) == len("policy-") + 32]


def test_load_captures_restorable_nonempty_policy_before_mutation(monkeypatch, home, policy_api):
    original = policy_api["engine"].export_policy()
    real_write = setup.conditional_policy_write

    def checked_write(*args):
        saved = setup.read_private_json(snapshots(home)[0])
        assert saved["before"] == original
        assert stat.S_IMODE(snapshots(home)[0].stat().st_mode) == 0o600
        return real_write(*args)

    monkeypatch.setattr(setup, "conditional_policy_write", checked_write)
    answer(monkeypatch, "replace policy", "admin")
    setup.load_policy(home, allow_nonempty=True)
    snapshot = snapshots(home)[0]
    saved = setup.read_private_json(snapshot)
    assert saved["target"] == policy_api["engine"].export_policy()
    assert saved["target"]["policy"]["mode"] == "strict"
    assert TOKEN not in snapshot.read_text()
    assert "owner credential" not in snapshot.read_text()
    assert setup.read_private_json(snapshot.with_name(snapshot.stem + "-loaded.json"))["outcome"] == "confirmed"
    assert policy_api["calls"][-1][1] == "/auth/logout"


def test_restore_is_conditional_and_preserves_snapshot(monkeypatch, home, policy_api):
    original = policy_api["engine"].export_policy()
    answer(monkeypatch, "replace policy", "admin", "restore policy", "admin")
    setup.load_policy(home, allow_nonempty=True)
    snapshot = snapshots(home)[0]
    saved = snapshot.read_bytes()
    setup.rollback_policy(home, snapshot)
    assert policy_api["engine"].export_policy() == original
    assert snapshot.read_bytes() == saved
    with pytest.raises(setup.SetupError, match="already has"):
        setup.rollback_policy(home, snapshot)


def test_restore_refuses_intervening_policy_change(monkeypatch, home, policy_api):
    answer(monkeypatch, "replace policy", "admin", "restore policy", "admin")
    setup.load_policy(home, allow_nonempty=True)
    policy_api["engine"].load_policy({"mode": "paranoid", "relations": []})
    current = policy_api["engine"].export_policy()
    writes = sum(call[1] == "/policies/load" for call in policy_api["calls"])
    with pytest.raises(setup.SetupError, match="concurrent"):
        setup.rollback_policy(home, snapshots(home)[0])
    assert policy_api["engine"].export_policy() == current
    assert sum(call[1] == "/policies/load" for call in policy_api["calls"]) == writes


def test_lost_load_response_observed_without_retry_and_can_restore(monkeypatch, home, policy_api):
    original = policy_api["engine"].export_policy()
    policy_api["lose_response"] = True
    answer(monkeypatch, "replace policy", "admin", "restore policy", "admin")
    setup.load_policy(home, allow_nonempty=True)
    snapshot = snapshots(home)[0]
    receipt = setup.read_private_json(snapshot.with_name(snapshot.stem + "-loaded.json"))
    assert receipt["outcome"] == "observed_target_after_uncertain_response"
    assert sum(call[1] == "/policies/load" for call in policy_api["calls"]) == 1
    setup.rollback_policy(home, snapshot)
    assert policy_api["engine"].export_policy() == original
    assert sum(call[1] == "/policies/load" for call in policy_api["calls"]) == 2


def test_snapshot_write_failure_prevents_policy_mutation(monkeypatch, home, policy_api):
    original = policy_api["engine"].export_policy()
    monkeypatch.setattr(setup, "private_file", Mock(side_effect=OSError("disk full")))
    answer(monkeypatch, "replace policy", "admin")
    with pytest.raises(OSError):
        setup.load_policy(home, allow_nonempty=True)
    assert policy_api["engine"].export_policy() == original
    assert not any(call[1] == "/policies/load" for call in policy_api["calls"])
    assert policy_api["calls"][-1][1] == "/auth/logout"


def test_ambiguous_response_and_failed_observation_preserves_intent(monkeypatch, home, policy_api):
    original_request = setup.request

    def request(method, path, payload=None, token=None):
        if path == "/policies/load":
            policy_api["lose_response"] = True
            policy_api["fail_exports"] = True
        return original_request(method, path, payload, token)

    monkeypatch.setattr(setup, "request", request)
    answer(monkeypatch, "replace policy", "admin")
    with pytest.raises(setup.SetupError, match="outcome remains unknown"):
        setup.load_policy(home, allow_nonempty=True)
    snapshot = snapshots(home)[0]
    assert setup.read_private_json(snapshot)["target"]["policy_hash"] == policy_api["engine"].get_policy_hash()
    assert not snapshot.with_name(snapshot.stem + "-loaded.json").exists()


def test_export_hash_tampering_is_rejected():
    with pytest.raises(setup.SetupError, match="hash mismatch"):
        setup.policy_export({"policy": {"mode": "strict", "terms": [], "relations": []}, "policy_hash": "0" * 64})


def test_backup_is_never_overwritten_across_multiple_loads(monkeypatch, home, policy_api):
    answer(monkeypatch, "replace policy", "admin", "replace policy", "admin")
    setup.load_policy(home, allow_nonempty=True)
    first = snapshots(home)[0]
    before = first.read_bytes()
    setup.load_policy(home, allow_nonempty=True)
    assert len(snapshots(home)) == 2
    assert first.read_bytes() == before


def test_conditional_write_reports_unchanged_state_without_retry(monkeypatch):
    prior = setup.target_policy({"relations": []})
    target = setup.target_policy({"relations": [{"type": "permits", "subject": "actor:new", "action": "action:read"}]})
    request = Mock(side_effect=[setup.SetupError("conflict"), prior])
    monkeypatch.setattr(setup, "request", request)
    with pytest.raises(setup.SetupError, match="matches the prior snapshot"):
        setup.conditional_policy_write(TOKEN, target["policy"], prior["policy_hash"], target["policy_hash"])
    assert request.call_count == 2


def test_default_policy_setup_refuses_nonempty_state(home, policy_api, monkeypatch):
    answer(monkeypatch, "replace policy", "admin")
    with pytest.raises(setup.SetupError, match="empty strict"):
        setup.load_policy(home)
    assert not any(call[1] == "/policies/load" for call in policy_api["calls"])
