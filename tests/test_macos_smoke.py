"""Native store/view-state regressions plus a disposable real API integration test."""

import errno
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("swiftc"), reason="macOS Swift toolchain required")


def seed_decision(index):
    return {"entry_id": str(index), "event_type": "decision", "timestamp": "2026-10-07T12:00:00",
            "entry_hash": "abc", "previous_hash": "def",
            "data": {"action": "read", "actor": "admin", "decision": "permit", "decision_id": f"seed-{index}"}}


class LocalAPI(BaseHTTPRequestHandler):
    decisions: ClassVar[list] = []
    scenario = "flow"
    failure = "http"
    entry_requests = 0
    verify_requests = 0

    def log_message(self, *_args):
        pass

    def send_json(self, value):
        data = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        assert self.headers.get("X-Tenant-ID") == "default"
        assert self.headers.get("Authorization") == "Bearer disposable-session"
        if self.path.startswith("/ledger/entries"):
            type(self).entry_requests += 1
            if self.scenario == "refresh-failure" and self.entry_requests > 1:
                self.fail_request()
                return
            query = parse_qs(urlparse(self.path).query)
            offset = int(query.get("offset", [0])[0])
            limit = int(query.get("limit", [200])[0])
            self.send_json({"entries": self.decisions[offset:offset + limit], "total": len(self.decisions)})
        elif self.path == "/auth/me":
            self.send_json({"user": {"username": "admin", "role": "admin"}})
        elif self.path == "/policies":
            self.send_json({"terms_count": 0, "relations_count": 1})
        elif self.path == "/ledger/verify":
            type(self).verify_requests += 1
            if self.scenario == "verify-failure" and self.verify_requests > 1:
                self.fail_request()
                return
            self.send_json({"valid": True, "entries_checked": 2})
        else:
            self.send_error(404)

    def fail_request(self):
        time.sleep(0.3)
        if self.failure == "http":
            self.send_error(503, "Disposable failure")
        else:
            # Close without an HTTP response to exercise URLSession's transport error path.
            self.close_connection = True

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        assert self.headers.get("X-Tenant-ID") == "default"
        if self.path != "/auth/login":
            assert self.headers.get("Authorization") == "Bearer disposable-session"
        if self.path == "/auth/login":
            self.send_json({
                "success": True, "session_id": "disposable-session",
                "user": {"username": "admin", "role": "admin"},
            })
        elif self.path == "/policies/load":
            assert len(body["policy"]["relations"]) == 2
            self.send_json({"status": "success"})
        elif self.path == "/decide":
            action = body["proposed_action"]
            outcome = "permit" if action == "read" else "deny"
            self.decisions.append({"entry_id": str(len(self.decisions) + 1), "event_type": "decision",
                                   "timestamp": "2026-10-07T12:00:00", "entry_hash": "abc", "previous_hash": "def",
                                   "data": {"action": action, "actor": "admin", "decision": outcome,
                                            "decision_id": action, "evaluation_source": "policy_engine"}})
            self.send_json({"decision": outcome, "ledger_entry_hash": "abc"})
        elif self.path == "/decide/verify":
            self.send_json({"verified": True})
        elif self.path == "/evidence/export":
            data = b"PK\x03\x04disposable-test-data"
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/auth/logout":
            self.send_json({"success": True})
        else:
            self.send_error(404)


@pytest.fixture(scope="module")
def native_binary():
    with tempfile.TemporaryDirectory(prefix="lexecon-macos-smoke-") as temporary:
        binary = Path(temporary) / "LexeconSmoke"
        sources = sorted((ROOT / "macos/Lexecon").rglob("*.swift"))
        command = ["swiftc", "-parse-as-library", "-DLEXECON_SMOKE", "-module-name", "LexeconSmoke",
                   *map(str, sources), str(ROOT / "macos/Tests/Smoke.swift"), "-o", str(binary)]
        subprocess.run(command, check=True, cwd=ROOT, timeout=120)
        yield binary


@pytest.mark.parametrize(("scenario", "failure"), [
    ("flow", "http"), ("paging", "http"),
    ("verify-failure", "http"), ("verify-failure", "disconnect"),
    ("refresh-failure", "http"), ("refresh-failure", "disconnect"),
])
def test_native_api_flow(native_binary, scenario, failure):
    LocalAPI.scenario, LocalAPI.failure = scenario, failure
    LocalAPI.entry_requests = LocalAPI.verify_requests = 0
    LocalAPI.decisions = [seed_decision(i) for i in range(201 if scenario == "paging" else 1 if "failure" in scenario else 0)]
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 8000), LocalAPI)
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            pytest.skip("loopback port 8000 is occupied")
        raise
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([str(native_binary), scenario], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stderr
        assert "passed:" in result.stdout
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_native_real_api(native_binary, tmp_path):
    # Reserve the app's loopback port before starting; never connect to an existing API.
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind(("127.0.0.1", 8000))
        listener.listen()
    except OSError as error:
        listener.close()
        if error.errno == errno.EADDRINUSE:
            pytest.skip("loopback port 8000 is occupied")
        raise
    # Deliberately exclude account, telemetry, and provider settings from the server.
    environment = {
        "PATH": os.environ["PATH"], "PYTHONPATH": str(ROOT / "src"),
        "LEXECON_DATA_DIR": str(tmp_path / "data"), "LEXECON_ENV": "test",
        "LEXECON_TEST_USERNAME": "native_test_admin",
        "LEXECON_TEST_PASSWORD": "T3st!" + secrets.token_hex(16),
        "LEXECON_TEST_EXPORT": str(tmp_path / "evidence.zip"),
    }
    with (tmp_path / "api.log").open("w+") as log:
        try:
            server = subprocess.Popen(
                [sys.executable, str(ROOT / "tests/macos_live_api.py"), str(listener.fileno())],
                cwd=tmp_path, env=environment, pass_fds=(listener.fileno(),), stdout=log, stderr=log,
            )
        finally:
            listener.close()
        try:
            for _ in range(100):
                assert server.poll() is None, "Disposable API exited before becoming ready"
                try:
                    with urlopen("http://127.0.0.1:8000/health", timeout=0.2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                pytest.fail("Disposable API did not become ready")
            result = subprocess.run(
                [str(native_binary), "live"], cwd=tmp_path, env=environment,
                capture_output=True, text=True, timeout=45, check=False,
            )
            assert result.returncode == 0, result.stderr
            assert "macOS API flow passed" in result.stdout
            verified = subprocess.run(
                [sys.executable, str(ROOT / "scripts/verify-evidence-zip.py"), environment["LEXECON_TEST_EXPORT"]],
                capture_output=True, text=True, timeout=10, check=True,
            )
            assert json.loads(verified.stdout)["events_rehashed"] >= 203
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
