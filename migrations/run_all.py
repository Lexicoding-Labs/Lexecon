#!/usr/bin/env python3
"""Run all pending database migrations in order.

Tracks applied migrations in a `schema_migrations` table so each
migration runs exactly once. Safe to call repeatedly (idempotent).

Usage:
    python migrations/run_all.py [db_path]
    python migrations/run_all.py              # defaults to lexecon_auth.db
"""

import importlib.util
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent


def _ensure_tracking_table(conn: sqlite3.Connection) -> None:
    """Create the schema_migrations table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)
    conn.commit()


def _applied_versions(conn: sqlite3.Connection) -> set[str]:
    """Return set of already-applied migration versions."""
    cursor = conn.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cursor.fetchall()}


def _discover_migrations() -> list[tuple[str, Path]]:
    """Find migration scripts matching NNN_*.py pattern, sorted by version."""
    migrations = []
    for f in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.py")):
        version = f.stem  # e.g. "001_add_mfa_support"
        migrations.append((version, f))
    return migrations


def _run_migration(version: str, path: Path, db_path: str) -> None:
    """Import and execute a single migration's migrate() function."""
    spec = importlib.util.spec_from_file_location(version, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if not hasattr(mod, "migrate"):
        raise RuntimeError(f"Migration {version} has no migrate() function")

    mod.migrate(db_path)


def run_all(db_path: str = "lexecon_auth.db") -> int:
    """Run all pending migrations.

    Returns the number of migrations applied.
    """
    conn = sqlite3.connect(db_path)
    try:
        _ensure_tracking_table(conn)
        applied = _applied_versions(conn)
        all_migrations = _discover_migrations()

        pending = [(v, p) for v, p in all_migrations if v not in applied]

        if not pending:
            print("No pending migrations.")
            return 0

        print(f"Found {len(pending)} pending migration(s):")
        for v, _ in pending:
            print(f"  - {v}")
        print()

        applied_count = 0
        for version, path in pending:
            print(f"Applying {version}...")
            _run_migration(version, path, db_path)

            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            applied_count += 1
            print(f"  Done.\n")

        print(f"Applied {applied_count} migration(s) successfully.")
        return applied_count

    finally:
        conn.close()


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else os.getenv("LEXECON_DB_PATH", "lexecon_auth.db")
    try:
        run_all(db)
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
