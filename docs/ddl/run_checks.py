"""ERD 점검 실행기.

docs/ddl/v1.0.sql을 빈 메모리 DB에 적용하고, v1.0-checks.sql의 점검을 위에서부터 차례로 돌린다.
오류가 나야 하는 점검은 예상한 오류 문구까지 확인한다(오타로 실패한 것을 통과로 세지 않으려고).
표준 라이브러리만 쓴다. 실행: uv run --python 3.14 python docs/ddl/run_checks.py
"""

import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent


def parse_checks(text: str) -> list[tuple[str, str, str]]:
    """'-- check:'로 시작하는 블록을 (설명, 기대, SQL) 목록으로 바꾼다."""
    blocks: list[tuple[str, str, str]] = []
    name, expect, sql = "", "", []
    for line in text.splitlines():
        if line.startswith("-- check:"):
            if name:
                blocks.append((name, expect, "\n".join(sql).strip()))
            name, expect, sql = line[len("-- check:"):].strip(), "", []
        elif line.startswith("-- expect:"):
            expect = line[len("-- expect:"):].strip()
        elif line.strip() and not line.startswith("--"):
            sql.append(line)
    if name:
        blocks.append((name, expect, "\n".join(sql).strip()))
    return blocks


def check_one(conn: sqlite3.Connection, expect: str, sql: str) -> tuple[bool, str]:
    """점검 하나를 실행하고 (통과 여부, 실제 결과)를 돌려준다."""
    if not expect:
        return False, "expect 줄이 없다"
    try:
        rows = conn.execute(sql.rstrip(";")).fetchall()
    except sqlite3.Error as exc:
        wanted = expect[len("error"):].strip()
        return expect.startswith("error") and wanted in str(exc), f"error: {exc}"
    if expect == "ok":
        return True, "ok"
    if expect.startswith("value "):
        actual = str(rows[0][0]) if rows else "<no rows>"
        return actual == expect[len("value "):], f"value: {actual}"
    return False, "ok (오류가 나야 했다)"


def run(ddl: Path, checks: Path) -> int:
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(ddl.read_text(encoding="utf-8"))
    blocks = parse_checks(checks.read_text(encoding="utf-8"))
    failed = []
    for number, (name, expect, sql) in enumerate(blocks, 1):
        passed, actual = check_one(conn, expect, sql)
        if not passed:
            failed.append(f"{number}. {name} — 기대 {expect!r}, 실제 {actual!r}")
    print(f"Python {sys.version.split()[0]} · SQLite {sqlite3.sqlite_version} · "
          f"점검 {len(blocks)}개 · 통과 {len(blocks) - len(failed)}개 · 실패 {len(failed)}개")
    for line in failed:
        print("  실패:", line)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run(HERE / "v1.0.sql", HERE / "v1.0-checks.sql"))
