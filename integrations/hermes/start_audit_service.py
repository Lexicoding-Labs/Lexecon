#!/usr/bin/env python3
"""Owner-operated isolated audit API; do not run before explicit activation approval."""

import argparse
import getpass
import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

from owner_setup import SetupError, confirm, settings_for

ROOT = Path(__file__).resolve().parents[2]


def isolated_environment(data_dir):
    # No inherited OIDC, cloud, database, signing, or model credentials/config.
    env = {key: os.environ[key] for key in ("PATH", "TMPDIR", "LANG", "TZ") if key in os.environ}
    env.update({"LEXECON_DATA_DIR": str(data_dir), "LEXECON_BASE_URL": "http://127.0.0.1:8765",
                "LEXECON_ENV": "development", "PYTHONPATH": str(ROOT / "src")})
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, type=Path)
    args = parser.parse_args(argv)
    home, settings = settings_for(args.home)
    if settings.get("api_port") != 8765 or not sys.stdin.isatty():
        raise SystemExit("Use a prepared port-8765 audit profile from an interactive terminal.")
    python = ROOT / ".venv/bin/python"
    if not python.is_file():
        raise SystemExit("The existing Lexecon virtual environment is required; no installation attempted.")
    data = home / "private/service-state"
    if data.is_symlink():
        raise SystemExit("Service state must not be a symlink.")
    # This listener check happens only during owner-approved activation, never preparation.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8765))
    try:
        confirm("activate isolated audit", "Start the isolated API at 127.0.0.1:8765. "
                "First run creates audit_admin and isolated security storage; existing port-8000 data is untouched.")
    except SetupError as error:
        print(str(error))
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled; no account created. Run this command again to retry.")
        return 1
    data.mkdir(mode=0o700, exist_ok=True)
    env = isolated_environment(data)
    db = data / "lexecon_auth.db"
    ready = False
    if db.exists():
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM users WHERE username='audit_admin' AND role='admin'",
            ).fetchone()[0]
            ready = count == 1
            total = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if not ready and total:
            raise SystemExit("Existing isolated state has users but no expected admin; no accounts changed.")
    if not ready:
        password = getpass.getpass("New isolated audit_admin password (hidden): ")
        if not password or password != getpass.getpass("Repeat password (hidden): "):
            raise SystemExit("Passwords empty or unequal; no account created.")
        bootstrap_env = {**env, "LEXECON_ADMIN_USERNAME": "audit_admin", "LEXECON_ADMIN_PASSWORD": password}
        try:
            subprocess.run([str(python), str(ROOT / "setup_security.py")], cwd=data, env=bootstrap_env, check=True)
        finally:
            bootstrap_env.pop("LEXECON_ADMIN_PASSWORD", None)
            del password
    print("Isolated API: http://127.0.0.1:8765. Ctrl+C stops this process; no live policy was replaced.")
    return subprocess.call([str(python), "-m", "uvicorn", "lexecon.api.server:app", "--host", "127.0.0.1",
                            "--port", "8765", "--workers", "1", "--no-proxy-headers"], cwd=data, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
