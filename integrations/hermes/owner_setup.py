#!/usr/bin/env python3
"""Owner-operated isolated Hermes setup. Never accepts secrets in arguments or env."""

import argparse
import getpass
import hashlib
import http.client
import json
import os
import re
import shutil
import stat
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4

import yaml

API_PORT = ContextVar("lexecon_owner_api_port", default=8000)
SOURCE = Path(__file__).resolve().parent
USERNAME = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
TOKEN = re.compile(r"[A-Za-z0-9_.~-]{16,4096}\Z")


class SetupError(Exception):
    """An intentionally credential-free, owner-facing setup failure."""


class _UniqueSafeLoader(yaml.SafeLoader):
    """Accept Hermes YAML without silently replacing duplicate security settings."""

    def construct_mapping(self, node, deep=False) -> dict:
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in mapping:
                raise ValueError("Invalid or duplicate profile setting")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def read_isolated_config(home):
    """Read the prepared JSON or Hermes-rewritten YAML without running YAML tags."""
    path = checked_path(Path(home) / "config.yaml")
    try:
        with path.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise SetupError("Invalid isolated profile config; no credential or policy operation attempted.")
        loader = _UniqueSafeLoader(raw.decode("utf-8"))
        try:
            config = loader.get_single_data()
        finally:
            loader.dispose()
    except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError) as exc:
        raise SetupError("Invalid isolated profile config; no credential or policy operation attempted.") from exc
    if not isinstance(config, dict):
        raise SetupError("Invalid isolated profile config; no credential or policy operation attempted.")
    return config


def request(method, path, payload=None, token=None):
    connection = http.client.HTTPConnection("127.0.0.1", API_PORT.get(), timeout=5)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        connection.request(method, path, None if payload is None else json.dumps(payload), headers)
        response = connection.getresponse()
        if response.status != 200:
            raise SetupError(f"Local API refused the request (HTTP {response.status}).")
        body = response.read(65537)
        if len(body) > 65536:
            raise SetupError("Local API response is too large.")
        result = json.loads(body)
        if not isinstance(result, dict):
            raise SetupError("Local API returned an invalid response.")
        return result
    except (OSError, ValueError, http.client.HTTPException) as exc:
        raise SetupError("Local API unavailable or returned invalid JSON; request outcome is unknown.") from exc
    finally:
        connection.close()


def checked_path(path, *, exists=True):
    path = Path(os.path.abspath(path))
    for part in reversed((path, *path.parents)):
        try:
            info = part.lstat()
        except FileNotFoundError:
            if part == path and not exists:
                continue
            raise SetupError("Parent directory does not exist.") from None
        if stat.S_ISLNK(info.st_mode):
            raise SetupError("Symlink paths are not supported; use the physical directory path.")
    return path


@contextmanager
def private_directory(path):
    """Pin each physical ancestor, refusing symlink substitution during traversal."""
    path = checked_path(path)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise SetupError("Private directory must be owned by you with mode 0700.")
        yield fd
    finally:
        os.close(fd)


def private_file(path, value):
    """Atomically install private state; never replace an existing snapshot or token."""
    path = Path(path)
    with private_directory(path.parent) as parent:
        temporary = ".session-" + os.urandom(12).hex()
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            except FileExistsError as exc:
                raise SetupError("Private file already exists; refusing to overwrite it.") from exc
        finally:
            os.unlink(temporary, dir_fd=parent)
            os.fsync(parent)


def read_session(path):
    path = Path(path)
    with private_directory(path.parent) as parent:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd) as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise SetupError("Session file must be your regular file with mode 0600 and one link.")
            token = stream.read(4098).strip()
    if not TOKEN.fullmatch(token):
        raise SetupError("No usable session is stored; run login.")
    return token


def prepare(home, username="lexecon_hermes", api_port=8000):
    if type(api_port) is not int or api_port not in {8000, 8765}:
        raise SetupError("Only loopback ports 8000 and 8765 are supported.")
    if not USERNAME.fullmatch(username) or username == "admin":
        raise SetupError("Choose a dedicated non-admin username using letters, digits, _, ., or -.")
    home = checked_path(home, exists=False)
    default_home = Path.home() / ".hermes"
    if home == default_home or default_home in home.parents:
        raise SetupError("Use a new isolated home outside ~/.hermes.")
    if home.exists():
        raise SetupError("Home already exists; refusing to overwrite it.")
    home.mkdir(mode=0o700)
    for folder in ("workspace", "private", "plugins"):
        (home / folder).mkdir(mode=0o700)
    (home / "workspace/welcome.txt").write_text("Welcome to the isolated Lexecon workspace.\n")
    source = SOURCE / "lexecon_gate"
    # Only plugin Python and manifest files; never copy caches or hidden state.
    target = home / "plugins/lexecon-gate"
    target.mkdir(mode=0o700)
    for item in source.iterdir():
        if item.suffix not in {".py", ".yaml"}:
            continue
        if item.is_symlink() or not item.is_file():
            raise SetupError("Plugin source must contain regular files.")
        shutil.copyfile(item, target / item.name)
    policy = json.loads((SOURCE / "starter-policy.json").read_text())
    for relation in policy["relations"]:
        relation["subject"] = "actor:" + username
    (home / "starter-policy.json").write_text(json.dumps(policy, indent=2) + "\n")
    settings = {
        "workspace_root": str(home / "workspace"), "username": username,
        "session_file": str(home / "private/session"), "audit_file": str(home / "private/audit.jsonl"),
        "api_port": api_port,
    }
    config = {
        "plugins": {"enabled": ["lexecon-gate"], "entries": {"lexecon-gate": {"settings": settings}}},
        "platform_toolsets": {"cli": ["lexecon_workspace"]},
        "tools": {"tool_search": {"enabled": False}},
        "required_tool_gate": {
            "plugin": "lexecon-gate", "tools": ["lexecon_list_files", "lexecon_read_file"],
        },
    }
    # JSON is valid YAML and needs no external setup dependencies.
    (home / "config.yaml").write_text(json.dumps(config, indent=2) + "\n")
    print("Prepared isolated home. No accounts, sessions, or live policies were changed.")
    return home


def settings_for(home):
    home = checked_path(home)
    info = home.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise SetupError("Home must be owned by you with mode 0700.")
    try:
        settings = read_isolated_config(home)["plugins"]["entries"]["lexecon-gate"]["settings"]
        if not isinstance(settings, dict):
            raise SetupError("Invalid isolated profile settings; refusing credential operations.")
        if type(settings.get("api_port", 8000)) is not int or settings.get("api_port", 8000) not in {8000, 8765}:
            raise ValueError
        if not USERNAME.fullmatch(settings["username"]) or settings["username"] == "admin":
            raise ValueError
        for key, relative in (("workspace_root", "workspace"), ("session_file", "private/session"),
                              ("audit_file", "private/audit.jsonl")):
            if settings[key] != str(home / relative):
                raise ValueError
        private = checked_path(home / "private")
        if private.stat().st_uid != os.getuid() or stat.S_IMODE(private.stat().st_mode) != 0o700:
            raise ValueError
        return home, settings
    except (KeyError, ValueError, TypeError) as exc:
        raise SetupError("Invalid isolated profile settings; refusing credential operations.") from exc


def confirm(phrase, explanation):
    print(explanation)
    if input(f"Type {phrase!r} to continue: ").strip().casefold() != phrase.casefold():
        raise SetupError(f"Cancelled; requested change was not performed. Run the command again "
                         f"and enter {phrase!r} at the confirmation prompt to retry.")


def revoke(token):
    if request("POST", "/auth/logout", token=token).get("success") is not True:
        raise SetupError("Session revocation was not confirmed.")


def authenticate(username, *, admin=False):
    result = request("POST", "/auth/login", {"username": username, "password": getpass.getpass("Password (hidden): ")})
    token = result.get("session_id")
    user = result.get("user")
    valid_token = isinstance(token, str) and TOKEN.fullmatch(token)
    if (result.get("success") is not True or not valid_token or not isinstance(user, dict)
            or user.get("username") != username
            or user.get("role") not in {"admin", "viewer", "auditor", "compliance_officer"}
            or (user.get("role") == "admin") != admin):
        if valid_token:
            revoke(token)
        raise SetupError("Login was not accepted for the required role. Check credentials/password expiry in Lexecon.")
    return token


@contextmanager
def administrator():
    username = input("Existing administrator username [admin]: ").strip() or "admin"
    token = authenticate(username, admin=True)
    try:
        yield token
    finally:
        revoke(token)


def provision(settings):
    username = settings["username"]
    with administrator() as token:
        users = request("GET", "/auth/users", token=token).get("users")
        if not isinstance(users, list) or any(not isinstance(user, dict) for user in users):
            raise SetupError("Could not validate existing identities.")
        existing = next((user for user in users if user.get("username") == username), None)
        if existing:
            if existing.get("role") != "viewer" or existing.get("is_active") is not True:
                raise SetupError("Existing identity is not an active viewer; no account changes were made.")
            print("Existing viewer identity found; no password reset or account change performed.")
            return
        confirm("create " + username, "This creates one persistent viewer account. You choose and submit its password.")
        password = getpass.getpass("New dedicated account password (hidden): ")
        if password != getpass.getpass("Repeat dedicated password (hidden): ") or not password:
            raise SetupError("Passwords did not match or were empty; no account created.")
        result = request("POST", "/auth/users", {
            "username": username, "email": username + "@localhost.invalid", "password": password,
            "role": "viewer", "full_name": "Local Hermes bounded workspace",
        }, token=token)
        if result.get("success") is not True:
            raise SetupError("Account creation was not confirmed; inspect Lexecon before retrying.")
        print("Dedicated viewer created. Password was not stored by this helper.")


def policy_export(value):
    """Validate a detached server export without printing its potentially private rules."""
    if not isinstance(value, dict) or not isinstance(value.get("policy"), dict):
        raise SetupError("Invalid policy export; no policy changes attempted.")
    policy = value["policy"]
    if (set(policy) != {"mode", "terms", "relations"}
            or policy["mode"] not in {"strict", "permissive", "paranoid"}
            or not isinstance(policy["terms"], list) or not isinstance(policy["relations"], list)):
        raise SetupError("Policy export is incomplete; no policy changes attempted.")
    encoded = json.dumps(policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if value.get("policy_hash") != hashlib.sha256(encoded).hexdigest():
        raise SetupError("Policy export hash mismatch; refusing unsafe recovery.")
    return {"policy": policy, "policy_hash": value["policy_hash"]}


def target_policy(policy):
    # Pure local policy normalization: no API, database, signing key, or auth service.
    sys.path.insert(0, str(SOURCE.parents[1] / "src"))
    from lexecon.policy.engine import PolicyEngine

    target = PolicyEngine({"mode": "strict", **policy}).export_policy()
    if target["policy"]["mode"] != "strict":
        raise SetupError("The bounded workspace starter policy must use strict mode.")
    return policy_export(target)


def read_private_json(path, *, expected_sha256=None):
    if expected_sha256 is not None and (
            not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None):
        raise SetupError("Expected manifest SHA-256 must be 64 lowercase hexadecimal characters.")
    path = Path(path)
    with private_directory(path.parent) as parent:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                    or info.st_size > 1024 * 1024):
                raise SetupError("Recovery snapshot must be a bounded private regular file.")
            data = stream.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                raise SetupError("Recovery snapshot exceeds the private file size bound.")
            if expected_sha256 is not None and hashlib.sha256(data).hexdigest() != expected_sha256:
                raise SetupError("Snapshot manifest does not match the reviewed SHA-256; collection refused.")
            return json.loads(data)


def write_receipt(snapshot, name, content):
    private_file(snapshot.with_name(snapshot.stem + "-" + name + ".json"),
                 json.dumps(content, sort_keys=True) + "\n")


def conditional_policy_write(token, policy, expected_hash, target_hash):
    """Resolve uncertain responses by observation, never by repeating a mutation."""
    try:
        result = request("POST", "/policies/load", {
            "policy": policy, "expected_policy_hash": expected_hash,
        }, token=token)
        if (result.get("status") == "success" and result.get("policy_hash") == target_hash
                and result.get("previous_policy_hash") == expected_hash):
            return "confirmed"
    except SetupError:
        pass
    # A response can be lost after the server changed policy. Never claim it did not run.
    try:
        observed = policy_export(request("GET", "/policies/export", token=token))
    except Exception as exc:
        raise SetupError("Policy change outcome remains unknown. Keep the snapshot; do not retry blindly.") from exc
    if observed["policy_hash"] == target_hash:
        return "observed_target_after_uncertain_response"
    if observed["policy_hash"] == expected_hash:
        raise SetupError("Change was not confirmed; current policy matches the prior snapshot. Backup retained.")
    raise SetupError("Concurrent or unexpected policy change detected; no further mutation attempted. Backup retained.")


def load_policy(home, *, allow_nonempty=False):
    policy = json.loads(checked_path(home / "starter-policy.json").read_text())
    if not isinstance(policy, dict) or not isinstance(policy.get("relations"), list):
        raise SetupError("Invalid policy template.")
    target = target_policy(policy)
    print(json.dumps(target["policy"], indent=2))
    confirm("replace policy", "This replaces the active in-memory policy for ALL callers "
            "and invalidates existing grants. A private recovery snapshot will be saved before mutation.\n"
            "API restart does not retain the active policy. Concurrent policy changes will be refused.")
    with administrator() as token:
        before = policy_export(request("GET", "/policies/export", token=token))
        if (before["policy"]["terms"] or before["policy"]["relations"]
                or before["policy"]["mode"] != "strict") and not allow_nonempty:
            raise SetupError("Default setup requires an empty strict policy; no policy changed. "
                             "Nonempty replacement needs a separate explicit approval and override.")
        snapshot = home / "private" / ("policy-" + uuid4().hex + ".json")
        private_file(snapshot, json.dumps({
            "version": 1, "before": before, "target": target,
        }, sort_keys=True) + "\n")
        print("Recovery snapshot: " + str(snapshot))
        result = conditional_policy_write(token, target["policy"], before["policy_hash"], target["policy_hash"])
        write_receipt(snapshot, "loaded", {"outcome": result, "policy_hash": target["policy_hash"]})
    print("Target policy accepted. Receipt distinguishes confirmed response from observed recovery.")
    print("To restore the snapshot, run rollback-policy with this --home and --snapshot path.")


def rollback_policy(home, snapshot):
    snapshot = checked_path(snapshot)
    if (snapshot.parent != home / "private"
            or not re.fullmatch(r"policy-[0-9a-f]{32}\.json", snapshot.name)):
        raise SetupError("Choose the exact private recovery snapshot printed by load-policy.")
    saved = read_private_json(snapshot)
    if not isinstance(saved, dict) or saved.get("version") != 1:
        raise SetupError("Unsupported recovery snapshot.")
    before = policy_export(saved.get("before"))
    target = policy_export(saved.get("target"))
    restored = snapshot.with_name(snapshot.stem + "-restored.json")
    if restored.exists() or restored.is_symlink():
        raise SetupError("This snapshot already has a restore receipt; refusing repeated rollback.")
    confirm("restore policy", "Restore this snapshot's previous policy for ALL callers. "
            "This invalidates current grants. Rollback will refuse a different current policy hash.")
    with administrator() as token:
        current = policy_export(request("GET", "/policies/export", token=token))
        if current["policy_hash"] != target["policy_hash"]:
            raise SetupError("Current policy differs from the starter target; "
                             "refusing to overwrite concurrent changes.")
        # Current target observation also recovers an activation whose POST response was lost.
        result = conditional_policy_write(token, before["policy"], target["policy_hash"], before["policy_hash"])
        write_receipt(snapshot, "restored", {"outcome": result, "policy_hash": before["policy_hash"]})
    print("Previous policy restored; private backup and restore receipt retained.")


def login(settings):
    path = Path(settings["session_file"])
    if path.exists() or path.is_symlink():
        raise SetupError("Session file already exists. Logout first; existing sessions are never silently replaced.")
    confirm("login", "This creates a server session for the dedicated identity "
            "and stores it privately outside the workspace.")
    token = authenticate(settings["username"])
    try:
        private_file(path, token + "\n")
    except Exception:
        revoke(token)
        raise
    print("Dedicated session stored privately. No token is printed.")


def logout(settings):
    path = Path(settings["session_file"])
    token = read_session(path)
    revoke(token)
    # Remove only the helper's known token file after successful server revocation.
    with private_directory(path.parent) as parent:
        os.unlink(path.name, dir_fd=parent)
    print("Dedicated session revoked and its local token file removed.")


def status(home, settings):
    print("Offline profile checks only; API health, policy, and session validity are not checked.")
    checked_path(home / "workspace")
    checked_path(home / "plugins/lexecon-gate/plugin.yaml")
    path = Path(settings["session_file"])
    if path.exists() or path.is_symlink():
        read_session(path)
        print("Private session file is well-formed; server validity is unknown.")
    else:
        print("No local session file. Owner login is required.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=(
        "prepare", "provision", "load-policy", "rollback-policy", "login", "logout", "status",
    ))
    parser.add_argument("--home", required=True, type=Path, help="New dedicated physical directory; never ~/.hermes")
    parser.add_argument("--username", default="lexecon_hermes", help="Used by prepare only")
    parser.add_argument("--snapshot", type=Path, help="Exact private snapshot required by rollback-policy")
    parser.add_argument("--api-port", type=int, choices=(8000, 8765), default=8000, help="Used by prepare only")
    parser.add_argument("--allow-policy-replacement", action="store_true",
                        help="Requires separate approval; permits replacing nonempty policy with a private snapshot")
    args = parser.parse_args(argv)
    port_token = None
    try:
        if args.command == "prepare":
            prepare(args.home, args.username, args.api_port)
        else:
            home, settings = settings_for(args.home)
            port_token = API_PORT.set(settings.get("api_port", 8000))
            if args.command == "provision":
                provision(settings)
            elif args.command == "load-policy":
                load_policy(home, allow_nonempty=args.allow_policy_replacement)
            elif args.command == "rollback-policy":
                if args.snapshot is None:
                    raise SetupError("rollback-policy requires the printed --snapshot path.")
                rollback_policy(home, args.snapshot)
            elif args.command == "login":
                login(settings)
            elif args.command == "logout":
                logout(settings)
            else:
                status(home, settings)
    except SetupError as exc:
        print(str(exc))
        return 1
    except (OSError, ValueError, EOFError, KeyboardInterrupt):
        # Exception text from transports/files may contain sensitive response data.
        print("Setup did not complete. Check the local API, profile permissions, "
              "and entered confirmations; no secrets are printed.")
        return 1
    finally:
        if port_token is not None:
            API_PORT.reset(port_token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
