"""상태 DB 시험(M0-03, M0-19): 스키마 비교, 엔진이 만든 DB에서 DDL 점검 67개, 버전 확인."""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from quest.core import state
from quest.core.config import EnvError

DDL_DIR = Path(__file__).resolve().parent.parent / "docs" / "ddl"


def _load_run_checks():
    spec = importlib.util.spec_from_file_location("run_checks", DDL_DIR / "run_checks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = state.connect(tmp_path / "state.db")
    yield conn
    conn.close()


def test_engine_schema_matches_erd_ddl() -> None:
    assert state.SCHEMA_FILE.read_bytes() == (DDL_DIR / "v1.0.sql").read_bytes()


def test_engine_created_db_passes_all_ddl_checks(db: sqlite3.Connection) -> None:
    run_checks = _load_run_checks()
    blocks = run_checks.parse_checks((DDL_DIR / "v1.0-checks.sql").read_text(encoding="utf-8"))
    failed = [name for name, expect, sql in blocks if not run_checks.check_one(db, expect, sql)[0]]
    assert len(blocks) == 67
    assert failed == []


def test_new_db_records_schema_version_and_created_at(db: sqlite3.Connection) -> None:
    meta = dict(db.execute("SELECT key, value FROM meta"))
    assert meta["schema_version"] == "1.0"
    assert meta["created_at"].endswith("Z")


def test_reopen_keeps_data_and_foreign_keys_on(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    state.connect(path).close()
    conn = state.connect(path)
    assert conn.execute("SELECT count(*) FROM meta").fetchone()[0] == 2
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()


def test_db_path_follows_quest_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUEST_HOME", str(tmp_path))
    state.connect().close()
    assert (tmp_path / "state.db").exists()


def test_unknown_schema_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    with state.connect(path) as conn:
        conn.execute("UPDATE meta SET value = '9.9' WHERE key = 'schema_version'")
    conn.close()
    with pytest.raises(EnvError, match="9.9"):
        state.connect(path)


@pytest.mark.parametrize("version", ["3.36.9", "3.8.11"])
def test_old_sqlite_is_refused(version: str) -> None:
    with pytest.raises(EnvError, match="3.37.0"):
        state.check_sqlite_version(version)


@pytest.mark.parametrize("version", ["3.37.0", "3.53.1"])
def test_supported_sqlite_is_accepted(version: str) -> None:
    state.check_sqlite_version(version)


def test_transaction_rolls_back_on_error(db: sqlite3.Connection) -> None:
    with pytest.raises(RuntimeError), state.transaction(db):
        db.execute("INSERT INTO meta (key, value) VALUES ('engine_version', '0.1.0')")
        raise RuntimeError
    assert db.execute("SELECT count(*) FROM meta WHERE key = 'engine_version'").fetchone()[0] == 0


def test_transaction_commits(db: sqlite3.Connection) -> None:
    with state.transaction(db):
        db.execute("INSERT INTO meta (key, value) VALUES ('engine_version', '0.1.0')")
    row = db.execute("SELECT value FROM meta WHERE key = 'engine_version'").fetchone()
    assert row[0] == "0.1.0"
