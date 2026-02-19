#!/usr/bin/env python3
"""000_base_schema — Create base auth tables.

Must run before all other migrations so that ALTER TABLE statements
in 001+ have tables to modify. Uses CREATE TABLE IF NOT EXISTS so it
is safe to run against a DB that AuthService has already initialized.
"""

import sqlite3
from datetime import datetime, timezone


def migrate(db_path: str) -> None:
    print(f"Creating base schema in {db_path}...")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL,
                full_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                password_changed_at TEXT,
                password_expires_at TEXT,
                mfa_enabled INTEGER DEFAULT 0,
                mfa_secret TEXT,
                last_login TEXT,
                is_active INTEGER DEFAULT 1,
                failed_login_attempts INTEGER DEFAULT 0,
                locked_until TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_history (
                history_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                ip_address TEXT,
                revoked INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                attempt_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                success INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TEXT NOT NULL,
                failure_reason TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)

        conn.commit()
        print("  [1/1] Base tables created (or already existed).")
    finally:
        conn.close()
