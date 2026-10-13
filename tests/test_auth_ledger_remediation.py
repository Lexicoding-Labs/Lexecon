"""Offline regressions for AUTH-RACE-01 and LEDGER-WRITE-01."""

import asyncio
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from starlette.requests import Request

from lexecon.api.models import LoginRequest
from lexecon.api.routers.auth import login
from lexecon.ledger.chain import LedgerChain
from lexecon.security.auth_service import AuthService, Role
from lexecon.security.auth_service_async import AsyncAuthService
from lexecon.storage.persistence import LedgerStorage

OLD_PASSWORD = "Th!sV7ryStr0ng"  # noqa: S105 - disposable fixture password
NEW_PASSWORD = "An0ther!SafePhrase"  # noqa: S105 - disposable fixture password


@pytest.fixture
def auth_pair(tmp_path):
    auth = AuthService(str(tmp_path / "auth.db"))
    user = auth.create_user("operator", "operator@example.test", OLD_PASSWORD, Role.ADMIN, "Operator")
    return auth, user


def test_stale_authenticated_user_cannot_create_session(auth_pair):
    auth, user = auth_pair
    previous = auth.create_session(user)
    stale_user, error = auth.authenticate(user.username, OLD_PASSWORD)
    assert error is None
    # A second instance models the concurrent request's independent connection.
    other = AuthService(auth.db_path)
    other.change_password(user.user_id, OLD_PASSWORD, NEW_PASSWORD)
    assert auth.validate_session(previous.session_id)[0] is None
    assert auth.authenticate(user.username, OLD_PASSWORD)[0] is None
    with pytest.raises(ValueError, match="credentials changed"):
        auth.create_session(stale_user)
    fresh_user, error = auth.authenticate(user.username, NEW_PASSWORD)
    assert error is None
    session = auth.create_session(fresh_user)
    assert auth.validate_session(session.session_id)[0] is not None


def test_login_race_returns_failure_without_session(auth_pair, monkeypatch):
    auth, user = auth_pair
    adapter = AsyncAuthService(auth)
    original_create = adapter.create_session

    async def rotate_before_session(authenticated_user, ip_address):
        await asyncio.to_thread(
            AuthService(auth.db_path).change_password,
            user.user_id, OLD_PASSWORD, NEW_PASSWORD,
        )
        return await original_create(authenticated_user, ip_address)

    monkeypatch.setattr(adapter, "create_session", rotate_before_session)
    services = SimpleNamespace(async_auth_service=adapter, audit_service=Mock())
    request = Request({"type": "http", "client": ("192.0.2.1", 1234)})
    response = asyncio.run(login(
        request, LoginRequest(username=user.username, password=OLD_PASSWORD), services,
    ))
    assert not response.success
    assert response.session_id is None
    services.audit_service.log_access.assert_not_called()
    with sqlite3.connect(auth.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sessions WHERE revoked = 0").fetchone()[0] == 0


def test_rotation_during_password_verification_keeps_original_generation(auth_pair, monkeypatch):
    auth, user = auth_pair
    original_hash = auth._hash_password

    def rotate_during_hash(password, salt):
        result = original_hash(password, salt)
        AuthService(auth.db_path).change_password(user.user_id, OLD_PASSWORD, NEW_PASSWORD)
        return result

    monkeypatch.setattr(auth, "_hash_password", rotate_during_hash)
    stale_user, _ = auth.authenticate(user.username, OLD_PASSWORD)
    with pytest.raises(ValueError, match="credentials changed"):
        auth.create_session(stale_user)


@pytest.mark.parametrize("commit_first", [False, True])
def test_failed_write_blocks_append_until_verified_reload(tmp_path, monkeypatch, commit_first):
    storage = LedgerStorage(str(tmp_path / "ledger.db"))
    ledger = LedgerChain(storage)
    before = ledger.to_dict()
    original_save = storage.save_entry

    def fail_save(entry):
        if commit_first:
            original_save(entry)
        raise sqlite3.OperationalError("injected write failure")

    monkeypatch.setattr(storage, "save_entry", fail_save)
    with pytest.raises(sqlite3.OperationalError, match="injected write failure"):
        ledger.append("uncertain", {"fixture": True})
    assert ledger.to_dict() == before
    monkeypatch.setattr(storage, "save_entry", original_save)
    with pytest.raises(RuntimeError, match="reload"):
        ledger.append("must_not_write", {})
    recovered = LedgerChain(storage)
    assert recovered.verify_integrity()["valid"]
    assert len(recovered.entries) == (2 if commit_first else 1)
    recovered.append("recovered", {})
    reloaded = LedgerChain(storage)
    assert reloaded.to_dict() == recovered.to_dict()
    assert reloaded.verify_integrity()["valid"]


def test_sqlite_insert_failure_does_not_advance_memory(tmp_path):
    storage = LedgerStorage(str(tmp_path / "ledger.db"))
    ledger = LedgerChain(storage)
    before = ledger.to_dict()
    with sqlite3.connect(storage.db_path) as conn:
        conn.execute("""
            CREATE TRIGGER fail_insert BEFORE INSERT ON ledger_entries
            BEGIN SELECT RAISE(ABORT, 'injected SQLite failure'); END
        """)
    with pytest.raises(sqlite3.IntegrityError, match="injected SQLite failure"):
        ledger.append("failed", {})
    assert ledger.to_dict() == before
    assert LedgerChain(storage).to_dict() == before
    with sqlite3.connect(storage.db_path) as conn:
        conn.execute("DROP TRIGGER fail_insert")
    recovered = LedgerChain(storage)
    recovered.append("successful", {})
    assert LedgerChain(storage).verify_integrity()["valid"]


def test_reload_rejects_broken_chain(tmp_path):
    storage = LedgerStorage(str(tmp_path / "ledger.db"))
    ledger = LedgerChain(storage)
    missing = ledger.append("missing", {})
    ledger.append("orphan", {})
    with sqlite3.connect(storage.db_path) as conn:
        conn.execute("DELETE FROM ledger_entries WHERE entry_id = ?", (missing.entry_id,))
    with pytest.raises(ValueError, match="Chain break"):
        LedgerChain(storage)


def test_deserialized_chain_can_append():
    original = LedgerChain()
    original.append("first", {})
    restored = LedgerChain.from_dict(original.to_dict())
    restored.append("second", {})
    assert restored.verify_integrity()["valid"]


def test_session_insert_waits_for_rotation_transaction(auth_pair, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, current_thread

    auth, user = auth_pair
    stale_user, _ = auth.authenticate(user.username, OLD_PASSWORD)
    other = AuthService(auth.db_path)
    original_connect = sqlite3.connect
    rotation_written = Event()
    session_insert_started = Event()
    finish_rotation = Event()

    def connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)

        def trace(statement):
            if "UPDATE sessions SET revoked" in statement:
                rotation_written.set()
                assert finish_rotation.wait(5)
            if "INSERT INTO sessions" in statement:
                session_insert_started.set()

        if current_thread().name.startswith("race-fixture"):
            conn.set_trace_callback(trace)
        return conn

    monkeypatch.setattr(sqlite3, "connect", connect)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="race-fixture") as pool:
        rotation = pool.submit(other.change_password, user.user_id, OLD_PASSWORD, NEW_PASSWORD)
        try:
            assert rotation_written.wait(5)
            creation = pool.submit(auth.create_session, stale_user)
            assert session_insert_started.wait(5)
        finally:
            finish_rotation.set()
        assert rotation.result(timeout=5)
        with pytest.raises(ValueError, match="credentials changed"):
            creation.result(timeout=5)


def test_existing_database_migrates_without_invalidating_current_sessions(auth_pair):
    auth, user = auth_pair
    session = auth.create_session(user)
    with sqlite3.connect(auth.db_path) as conn:
        conn.execute("ALTER TABLE users DROP COLUMN credential_version")
        conn.execute("DELETE FROM schema_version WHERE version = 3")
        conn.execute("INSERT OR IGNORE INTO schema_version VALUES (2, '2026-01-01')")
    migrated = AuthService(auth.db_path)
    assert migrated.validate_session(session.session_id)[0] is not None
    stale_user, _ = migrated.authenticate(user.username, OLD_PASSWORD)
    migrated.change_password(user.user_id, OLD_PASSWORD, NEW_PASSWORD)
    with pytest.raises(ValueError, match="credentials changed"):
        migrated.create_session(stale_user)
    reopened = AuthService(auth.db_path)
    for fresh_user in (reopened.get_user_by_id(user.user_id), reopened.list_users()[0]):
        assert reopened.validate_session(reopened.create_session(fresh_user).session_id)[0] is not None


def test_repeated_rotation_rejects_each_prior_generation(auth_pair):
    auth, user = auth_pair
    first, _ = auth.authenticate(user.username, OLD_PASSWORD)
    auth.change_password(user.user_id, OLD_PASSWORD, NEW_PASSWORD)
    second, _ = auth.authenticate(user.username, NEW_PASSWORD)
    auth.change_password(user.user_id, NEW_PASSWORD, "Th!rdStr0ngPhrase")
    for stale_user in (first, second):
        with pytest.raises(ValueError, match="credentials changed"):
            auth.create_session(stale_user)


def test_concurrent_appends_remain_durable_and_linked(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    storage = LedgerStorage(str(tmp_path / "ledger.db"))
    ledger = LedgerChain(storage)
    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(lambda number: ledger.append("parallel", {"number": number}), range(20)))
    assert len({entry.entry_id for entry in entries}) == 20
    reloaded = LedgerChain(storage)
    assert len(reloaded.entries) == 21
    assert reloaded.to_dict() == ledger.to_dict()
    assert reloaded.verify_integrity()["valid"]


def test_genesis_failure_does_not_publish_in_memory():
    class FailingGenesisStorage:
        @staticmethod
        def load_all_entries():
            return []

        @staticmethod
        def save_entry(_entry):
            raise sqlite3.OperationalError("genesis failure")

    ledger = LedgerChain.__new__(LedgerChain)
    with pytest.raises(sqlite3.OperationalError, match="genesis failure"):
        ledger.__init__(FailingGenesisStorage())
    assert ledger.entries == []
