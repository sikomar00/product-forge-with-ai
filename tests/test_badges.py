"""배지 시험(Spec "채점" 6, design.md 3.6절): 엔진 배지 4개와 콘텐츠 미션 배지."""

import sqlite3
from pathlib import Path

from conftest import Quest

from quest.core import badges, state


def _award(conn: sqlite3.Connection, at: str) -> list[str]:
    with state.transaction(conn, at) as tx:
        return badges.award(tx, None)


def _db(game: Path) -> sqlite3.Connection:
    return sqlite3.connect(game.parent / "home" / "state.db", isolation_level=None)


def _earned(game: Path) -> list[str]:
    return [k for (k,) in _db(game).execute("SELECT badge_key FROM badges ORDER BY badge_key")]


def test_first_pass_and_mission_badge(game: Path, quest: Quest, answers: list[str]) -> None:
    (game / "hello.txt").write_text("hi", encoding="utf-8")
    answers.extend(["2", "2"])
    code, out = quest("check")
    assert "🏅 배지 획득: 🎫 첫 미션 통과" in out and "🏅 배지 획득: 🏅 fake_first_file" in out
    assert _earned(game) == ["fake_first_file", "first_pass"]
    assert "배지: 🎫 첫 미션 통과, 🏅 fake_first_file" in quest("stats")[1]
    quest("check", "0-1")  # 다시 통과해도 두 번 주지 않는다
    assert _earned(game) == ["fake_first_file", "first_pass"]


def _passed(conn: sqlite3.Connection, rows: list[tuple[str, int]]) -> None:
    """(미션 키, 실패 수) 목록을 앞서 넣은 것보다 늦은 시각에 차례로 통과 처리한다."""
    done = conn.execute("SELECT count(*) FROM mission_progress").fetchone()[0]
    conn.executemany(
        "INSERT INTO mission_progress (mission_key, display_id, chapter, status, how, started_at,"
        " completed_at, fails, est_min, ai_tag) VALUES (?, '9-1', 0, 'passed', 'normal',"
        " '2026-01-01T00:00:00Z', ?, ?, 5, 'solo')",
        [(key, f"2026-01-{done + n + 1:02d}T00:00:00Z", fails)
         for n, (key, fails) in enumerate(rows)],
    )


def test_oneshot_run_must_be_five_in_a_row(game: Path, quest: Quest) -> None:
    quest()
    conn = _db(game)
    _passed(conn, [(f"m_aaaaaa0{n}", 0) for n in range(4)])
    assert "oneshot5" not in _award(conn, "2026-02-01T00:00:00Z")
    _passed(conn, [("m_bbbbbb01", 1)])  # 실패가 끼면 끊긴다
    _passed(conn, [(f"m_cccccc0{n}", 0) for n in range(4)])
    assert "oneshot5" not in _award(conn, "2026-02-01T00:00:00Z")
    _passed(conn, [("m_dddddd01", 0)])
    assert "oneshot5" in _award(conn, "2026-02-01T00:00:00Z")


def test_steady_needs_fourteen_review_days(game: Path, quest: Quest) -> None:
    quest()
    conn = _db(game)
    conn.executemany(
        "INSERT INTO events (at, kind) VALUES (?, 'review_finished')",
        [(f"2026-03-{day:02d}T01:00:00Z",) for day in range(1, 14)],
    )
    assert "steady14" not in _award(conn, "2026-03-13T02:00:00Z")
    conn.execute("INSERT INTO events (at, kind) VALUES ('2026-03-14T01:00:00Z', 'review_finished')")
    assert "steady14" in _award(conn, "2026-03-14T02:00:00Z")
