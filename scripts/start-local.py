#!/usr/bin/env python3
"""Start the supported single-organization Lexecon workspace on loopback."""

import argparse
import getpass
import hashlib
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
API_URL = "http://127.0.0.1:8000"
UI_URL = "http://127.0.0.1:3000/login"


def fail(message):
    raise RuntimeError(message)


def ensure_dependencies(include_frontend=True):
    python = ROOT / ".venv/bin/python"
    uvicorn = ROOT / ".venv/bin/uvicorn"
    if not shutil_which("uv"):
        fail("uv is required to reconcile the locked Python environment. Install it, then retry (see README.md).")
    print("Checking Python dependencies against uv.lock…", flush=True)
    dependency_env = os.environ.copy()
    dependency_env["UV_PROJECT_ENVIRONMENT"] = str(ROOT / ".venv")
    dependency_env.pop("LEXECON_ADMIN_PASSWORD", None)
    try:
        subprocess.run(["uv", "sync", "--locked", "--extra", "dev"], cwd=ROOT, env=dependency_env, check=True)
    except subprocess.CalledProcessError:
        fail("Locked Python dependency setup failed. Resolve the error above and retry; local data was not initialized.")
    if not python.exists() or not uvicorn.exists():
        fail("Dependency setup did not produce .venv/bin/python and uvicorn. Check uv's project environment settings.")
    if include_frontend:
        frontend = ROOT / "frontend"
        digest = hashlib.sha256()
        for name in ("package.json", "package-lock.json"):
            digest.update((frontend / name).read_bytes())
        fingerprint = digest.hexdigest()
        stamp = frontend / "node_modules/.lexecon-lock.sha256"
        installed = (frontend / "node_modules/.bin/react-scripts").exists()
        if not installed or not stamp.exists() or stamp.read_text().strip() != fingerprint:
            print("Installing frontend dependencies from package-lock.json…", flush=True)
            if not shutil_which("npm"):
                fail("Node.js and npm are required. Install them, then run this command again.")
            subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=frontend, check=True)
            stamp.write_text(fingerprint + "\n")
    return python, uvicorn


def shutil_which(program):
    from shutil import which
    return which(program)


def admin_state(db_path):
    if not db_path.exists():
        return "new"
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            admins = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
    except sqlite3.Error as error:
        fail(f"Cannot read {db_path}: {error}. Check the data directory before continuing.")
    if admins:
        return "ready"
    if count:
        fail(
            "The existing data directory has users but no administrator. "
            "Use an administrator recovery procedure; no account was changed."
        )
    return "new"


def prepare_data(python, data_dir):
    data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if admin_state(data_dir / "lexecon_auth.db") == "ready":
        print(f"Using existing local workspace: {data_dir}", flush=True)
        return
    if not sys.stdin.isatty():
        fail("First run needs a terminal to choose an administrator password.")
    print("First run: create the local administrator. Username: admin", flush=True)
    password = getpass.getpass("New administrator password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        fail("Passwords did not match. No administrator was created.")
    env = os.environ.copy()
    env["LEXECON_DATA_DIR"] = str(data_dir)
    env["LEXECON_ADMIN_PASSWORD"] = password
    try:
        subprocess.run([str(python), "setup_security.py"], cwd=ROOT, env=env, check=True)
    finally:
        env.pop("LEXECON_ADMIN_PASSWORD", None)
        del password, confirm


def check_port(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except PermissionError as error:
            fail(f"Cannot bind loopback port {port}: {error}. Check local network permission for this terminal.")
        except OSError:
            fail(f"Port {port} is already in use. Stop the process using it, then retry.")


def wait_for(url, process, seconds):
    from urllib.request import ProxyHandler, Request, build_opener
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + seconds
    last_error = "no response"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            fail(f"A server stopped before {url} was ready (exit {process.returncode}). See its output above.")
        try:
            with opener.open(Request(url, headers={"Accept": "text/html,application/json"}), timeout=5) as response:
                if response.status == 200:
                    return
                last_error = f"HTTP {response.status}"
        except (URLError, TimeoutError, OSError) as error:
            last_error = str(error)
        time.sleep(0.5)
    fail(f"Timed out waiting for {url}: {last_error}. See the server output above.")


def stop(process):
    if process and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="Print the URL without opening a browser")
    parser.add_argument(
        "--macos", action="store_true",
        help="Build and open the native macOS app instead of the browser dashboard",
    )
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".lexecon", help="Private local data directory")
    args = parser.parse_args()
    data_dir = args.data_dir.expanduser().resolve()
    if data_dir.is_relative_to(ROOT) and not data_dir.is_relative_to(ROOT / ".lexecon"):
        fail("Data inside the repository must be under its ignored .lexecon directory.")
    check_port(8000)
    if not args.macos:
        check_port(3000)
    if args.macos:
        # Build/toolchain failures must happen before prompting for credentials or
        # initializing the owner's data directory.
        subprocess.run([str(ROOT / "scripts/build-macos.sh")], cwd=ROOT, check=True)
    python, uvicorn = ensure_dependencies(include_frontend=not args.macos)
    prepare_data(python, data_dir)

    api = ui = None
    try:
        env = os.environ.copy()
        env.pop("LEXECON_ADMIN_PASSWORD", None)
        env["LEXECON_DATA_DIR"] = str(data_dir)
        print("Starting Lexecon API…", flush=True)
        api = subprocess.Popen(
            [str(uvicorn), "lexecon.api.server:app", "--host", "127.0.0.1", "--port", "8000", "--no-proxy-headers"],
            cwd=ROOT, env=env, start_new_session=True,
        )
        wait_for(API_URL + "/health", api, 45)
        if args.macos:
            app_path = ROOT / "macos/dist/Lexecon.app"
            print(
                f"\nReady: {app_path}\nSign in as admin with the password you chose. "
                "Press Ctrl+C to stop the API.\n", flush=True,
            )
            if not args.no_browser:
                subprocess.run(["open", str(app_path)], check=True)
        else:
            print("Starting dashboard…", flush=True)
            env.update({"HOST": "127.0.0.1", "PORT": "3000", "BROWSER": "none"})
            ui = subprocess.Popen(["npm", "start"], cwd=ROOT / "frontend", env=env, start_new_session=True)
            wait_for(UI_URL, ui, 120)
            print(
                f"\nReady: {UI_URL}\nSign in as admin with the password you chose. "
                "Press Ctrl+C to stop both servers.\n", flush=True,
            )
            if not args.no_browser:
                webbrowser.open(UI_URL)
        while api.poll() is None and (args.macos or (ui and ui.poll() is None)):
            time.sleep(0.5)
        fail("A server stopped. See its output above.")
    except KeyboardInterrupt:
        print("\nStopping Lexecon…", flush=True)
    finally:
        stop(ui)
        stop(api)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Lexecon startup failed: {error}", file=sys.stderr)
        sys.exit(1)
