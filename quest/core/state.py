"""학습 상태 DB: SQLite 연결, 스키마 적용, 트랜잭션(Spec "상태 DB", ERD v1.0)."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from quest.core.config import EnvError, home

MIN_SQLITE = (3, 37, 0)  # STRICT 표
SCHEMA_VERSION = "1.0"
SCHEMA_FILE = Path(__file__).parent / "schema" / "v1_0.sql"


def now_utc() -> str:
    """DB에 넣는 시각 형식(UTC ISO-8601, 초 단위)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_sqlite_version(version: str = sqlite3.sqlite_version) -> None:
    if tuple(int(part) for part in version.split(".")) < MIN_SQLITE:
        need = ".".join(map(str, MIN_SQLITE))
        raise EnvError(
            f"SQLite {version}은 너무 낮습니다. STRICT 표를 쓰려면 {need} 이상이 필요합니다."
        )


def db_path() -> Path:
    return home() / "state.db"


def connect(path: Path | None = None) -> sqlite3.Connection:
    """DB를 열고, 비어 있으면 스키마 v1.0을 적용한다."""
    check_sqlite_version()
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # 트랜잭션은 transaction()으로 직접 연다. 열린 트랜잭션 안에서는 PRAGMA foreign_keys가 무시된다.
    conn = sqlite3.connect(path, autocommit=True)
    conn.row_factory = sqlite3.Row  # 번호와 칸 이름 둘 다로 읽는다
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        _ensure_schema(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    has_meta = conn.execute(
        "SELECT count(*) FROM sqlite_schema WHERE type = 'table' AND name = 'meta'"
    ).fetchone()[0]
    if not has_meta:
        ddl = SCHEMA_FILE.read_text(encoding="utf-8")
        # 중간에 멈춰도 반쯤 만든 DB가 남지 않게 한 트랜잭션으로 적용한다.
        conn.executescript(
            f"BEGIN;\n{ddl}\nINSERT INTO meta (key, value) VALUES ('created_at', '{now_utc()}');\n"
            "COMMIT;"
        )
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    if row is None or row[0] != SCHEMA_VERSION:
        found = row[0] if row else "없음"
        raise EnvError(f"상태 DB 스키마 버전이 {found}입니다. 이 엔진은 {SCHEMA_VERSION}만 엽니다.")


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """명령 하나의 쓰기를 트랜잭션 하나로 묶는다. 예외가 나면 모두 되돌린다."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
