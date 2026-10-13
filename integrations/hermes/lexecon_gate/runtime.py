"""Authorization is performed inside each handler, independent of Hermes hooks."""

import fcntl
import hashlib
import http.client
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .filesystem import (
    GateError,
    absolute_path,
    list_files,
    open_directory,
    open_private_file,
    read_file,
    relative_path,
)

TOOLS = {"lexecon_list_files": "list", "lexecon_read_file": "read"}


def arguments_digest(arguments):
    """Match the API's SHA-256 of compact, key-sorted JSON arguments."""
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GateConfig:
    """Operator-selected scope and private file locations; no default workspace."""
    workspace_root: Path
    username: str
    session_file: Path
    audit_file: Path
    api_port: int = 8000

    def validate(self):
        """Refuse ambiguous identities and workspace-readable private state."""
        if not isinstance(self.username, str) or not re.fullmatch(r"[A-Za-z0-9_.@-]{1,100}", self.username):
            raise GateError("invalid_username")
        if type(self.api_port) is not int or self.api_port not in {8000, 8765}:
            raise GateError("invalid_api_port")
        root = absolute_path(self.workspace_root)
        if root == Path("/"):
            raise GateError("workspace_too_broad")
        for value in (self.session_file, self.audit_file):
            path = absolute_path(value)
            if path == root or root in path.parents:
                raise GateError("private_files_must_be_outside_workspace")
        if Path(self.session_file) == Path(self.audit_file):
            raise GateError("private_paths_must_differ")


class LoopbackClient:
    """Fixed loopback destination; http.client ignores proxies and never follows redirects."""

    def __init__(self, session_file, api_port=8000):
        if type(api_port) is not int or api_port not in {8000, 8765}:
            raise GateError("invalid_api_port")
        self.api_port = api_port
        self.session_file = session_file
        self._token = None

    def _read_token(self):
        with open_private_file(self.session_file) as fd:
            if os.fstat(fd).st_size > 4096:
                raise GateError("invalid_session_file")
            token = os.read(fd, 4097).decode("ascii").strip()
        if not re.fullmatch(r"[A-Za-z0-9_.~-]{16,4096}", token):
            raise GateError("invalid_session_file")
        return token

    def for_call(self):
        """Pin one session for identity check, decision, and consumption."""
        bound = LoopbackClient(self.session_file, self.api_port)
        bound._token = self._read_token()
        return bound

    def whoami(self):
        """Read the authenticated identity; passwords never enter this client."""
        return self._request("GET", "/auth/me")

    def ledger_entries(self):
        """Independent fresh decision evidence for owner-operated reconciliation."""
        summary = self._request("GET", "/ledger/entries?event_type=decision&limit=1")
        total = summary.get("total")
        if type(total) is not int or total < 0:
            raise GateError("invalid_response")
        return self._request("GET", f"/ledger/entries?event_type=decision&limit=32&offset={max(0, total - 32)}")

    def post(self, path, payload):
        """Submit to one of the two fixed authorization endpoints."""
        if path not in {"/decide", "/capability/verify"}:
            raise GateError("invalid_endpoint")
        return self._request("POST", path, payload)

    def _request(self, method, path, payload=None):
        token = self._token if self._token is not None else self._read_token()
        connection = http.client.HTTPConnection("127.0.0.1", self.api_port, timeout=3)
        try:
            body = json.dumps(payload, allow_nan=False) if payload is not None else None
            connection.request(method, path, body, {
                "Content-Type": "application/json", "Authorization": f"Bearer {token}",
            })
            response = connection.getresponse()
            if response.status != 200:
                raise GateError("authentication_required" if response.status == 401 else "request_denied")
            body = response.read(65537)
            if len(body) > 65536:
                raise GateError("invalid_response")
            result = json.loads(body)
            if not isinstance(result, dict):
                raise GateError("invalid_response")
            return result
        finally:
            connection.close()


class AuditLog:
    """Append+fsync before execution and before disclosing results; not tamper-proof."""

    def __init__(self, path):
        self.path = path

    def append(self, record):
        record = {**record, "timestamp": datetime.now(timezone.utc).isoformat()}
        data = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
        with open_private_file(self.path, append=True) as fd:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                if os.write(fd, data) != len(data):
                    raise GateError("audit_unavailable")
                os.fsync(fd)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)


class GateRuntime:
    """Authorize and consume a bound grant before reading the pinned workspace."""
    def __init__(self, config, client=None, audit=None):
        self.config = config
        self.client = client if client is not None else LoopbackClient(config.session_file, config.api_port)
        self.audit = audit if audit is not None else AuditLog(config.audit_file)

    def execute(self, tool_name, args):
        record = {"request_id": str(uuid4()), "decision_id": None,
                  "tool": tool_name if tool_name in TOOLS else "unmapped",
                  "action": TOOLS.get(tool_name), "arguments_digest": None}
        try:
            self.config.validate()
            if tool_name not in TOOLS:
                raise GateError("unmapped_tool")
            if not isinstance(args, dict) or set(args) != {"path"}:
                raise GateError("invalid_arguments")
            path = relative_path(args["path"], listing=tool_name == "lexecon_list_files")
            with open_directory(self.config.workspace_root) as root_fd:
                root_info = os.fstat(root_fd)
                arguments = {"workspace_root": str(self.config.workspace_root),
                             "workspace_device": root_info.st_dev, "workspace_inode": root_info.st_ino,
                             "path": path}
                digest = arguments_digest(arguments)
                record["arguments_digest"] = digest
                self.audit.append({**record, "outcome": "requested", "reason": "policy_check"})
                client = self.client.for_call() if isinstance(self.client, LoopbackClient) else self.client
                identity = client.whoami()
                user = identity.get("user") if isinstance(identity, dict) else None
                if (not isinstance(user, dict) or user.get("username") != self.config.username
                        or user.get("role") not in {"viewer", "auditor", "compliance_officer"}):
                    raise GateError("dedicated_nonadmin_identity_required")
                decision = client.post("/decide", {
                    "request_id": record["request_id"],
                    "actor": self.config.username, "proposed_action": TOOLS[tool_name],
                    "tool": tool_name, "tool_arguments": arguments,
                    "user_intent": "Read explicitly configured local workspace",
                })
                if not isinstance(decision, dict):
                    raise GateError("invalid_response")
                decision_id = decision.get("decision_id")
                if not isinstance(decision_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", decision_id):
                    raise GateError("invalid_response")
                record["decision_id"] = decision_id
                if decision.get("decision") != "permit":
                    raise GateError("policy_denied")
                grant = decision.get("capability_token")
                if not isinstance(grant, dict) or grant.get("arguments_digest") != digest:
                    raise GateError("unbound_or_mismatched_grant")
                verified = client.post("/capability/verify", {
                    "capability_token": grant, "action": TOOLS[tool_name], "tool": tool_name,
                    "tool_arguments": arguments, "consume": True,
                })
                if (not isinstance(verified, dict) or verified.get("valid") is not True
                        or verified.get("consumed") is not True):
                    raise GateError("verification_denied")
                self.audit.append({**record, "outcome": "authorized", "reason": "grant_consumed"})
                result = (list_files(root_fd, path) if tool_name == "lexecon_list_files"
                          else read_file(root_fd, path))
                self.audit.append({**record, "outcome": "completed", "reason": "success"})
                return {"ok": True, "decision_id": decision_id, **result}
        except Exception as exc:
            # Never surface HTTP bodies, paths, tool content, or credential-bearing exceptions.
            reason = str(exc) if isinstance(exc, GateError) else "gate_unavailable"
            try:
                self.audit.append({**record, "outcome": "blocked", "reason": reason})
            except Exception:
                reason = "audit_unavailable"
            return {"ok": False, "error": reason}
