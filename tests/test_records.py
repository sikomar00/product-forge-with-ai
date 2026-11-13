"""기록·상태·초기화 시험(M0-06, M0-15, M0-16, IA-6·IA-11·IA-15·IA-17)."""

import json
import sqlite3
from pathlib import Path

import pytest
from conftest import FAKE, Quest

from quest.commands.records import readonly_connect
from quest.core import content, spoiler


def _db(game: Path) -> sqlite3.Connection:
    return sqlite3.connect(game.parent / "home" / "state.db", isolation_level=None)


def _pass_first(game: Path, quest: Quest, answers: list[str]) -> None:
    (game / "hello.txt").write_text("hi", encoding="utf-8")
    answers.extend(["2", "2"])
    assert quest("check")[0] == 0


# ───────────── IA-6 장 지도 ─────────────


def test_map_locks_later_chapters(game: Path, quest: Quest) -> None:
    code, out = quest("map")
    assert code == 0 and "▶  0장 작업장" in out and "🔒  1장 터미널·Linux" in out
    assert "🔒 17장 Forge Run" in out and "── 주니어" in out
    code, out = quest("map", "1")
    assert code == 2 and "잠긴 장" in out
    assert quest("map", "18")[0] == 2 and quest("map", "x")[0] == 2


def test_map_chapter_lists_missions_with_status(
    game: Path, quest: Quest, answers: list[str]
) -> None:
    _pass_first(game, quest, answers)
    quest("mission")  # 0-2 시작
    code, out = quest("map", "0")
    assert code == 0 and "0-1 🎫 가짜 실습 🤝 · 약 5분 · 코어 · ✅ 통과" in out
    assert "0-2 🧠 가짜 퀴즈 🔒 · 약 30분 · 코어 · 진행 중" in out and "0-3" in out


# ───────────── IA-11 기록 ─────────────


def test_stats_summary(game: Path, quest: Quest, answers: list[str]) -> None:
    _pass_first(game, quest, answers)
    code, out = quest("stats")
    assert code == 0 and " 0장   1/5" in out and "0%" in out
    assert "확신(3)했는데 틀린 비율: —" in out and "MTTR): —" in out


def test_stats_sql_reads(game: Path, quest: Quest, answers: list[str]) -> None:
    _pass_first(game, quest, answers)
    code, out = quest("stats", "--sql", "SELECT display_id, est_min FROM v_mission_time")
    assert code == 0 and "display_id | est_min\n0-1 | 5\n" in out and "(1행)" in out


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM events",
        "UPDATE mission_progress SET xp_awarded = 999",
        "CREATE TABLE x (a)",
        "SELECT 1; DELETE FROM events",  # 두 문장은 실행하지 않는다
    ],
)
def test_stats_sql_cannot_write(game: Path, quest: Quest, answers: list[str], sql: str) -> None:
    _pass_first(game, quest, answers)
    code, out = quest("stats", "--sql", sql)
    assert code == 2 and "SQL 오류" in out
    conn = _db(game)
    assert conn.execute("SELECT xp_awarded FROM mission_progress").fetchone() == (12,)
    assert conn.execute("SELECT count(*) FROM events").fetchone()[0] > 0


def test_readonly_connection_cannot_write_attached_file(game: Path, quest: Quest) -> None:
    quest()
    conn = readonly_connect()
    conn.execute(f"ATTACH '{(game.parent / 'other.db').as_posix()}' AS o")  # 붙이는 것은 된다
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("CREATE TABLE o.t (a)")
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("DELETE FROM main.events")
    conn.close()


def test_stats_usage(game: Path, quest: Quest) -> None:
    assert quest("stats", "--sq", "x")[0] == 2


# ───────────── IA-15 기계용 상태 ─────────────

STATUS_KEYS = {"schema", "mission", "mode", "remaining_checks", "incident_active", "review_lock"}


def test_status_json_has_only_allowed_keys(game: Path, quest: Quest) -> None:
    code, out = quest("status", "--json")
    data = json.loads(out)
    assert code == 0 and set(data) == STATUS_KEYS
    assert set(data["mission"]) == {"key", "id", "kind", "ai"}
    assert set(data["remaining_checks"]) == {"numbers", "count"}
    assert data == {
        "schema": 1,
        "mission": {"key": "m_f0000001", "id": "0-1", "kind": "ops", "ai": "pair"},
        "mode": "normal",
        "remaining_checks": {"numbers": [1], "count": 1},
        "incident_active": False,
        "review_lock": False,
    }


def test_status_json_leaks_no_check_text_hint_or_answer(
    game: Path, quest: Quest, answers: list[str]
) -> None:
    """금지 필드 0개(M0 게이트): 어떤 미션이 현재여도 설명·힌트·정답 글자가 나오지 않는다."""
    loaded = content.load_content(FAKE)
    secrets = set()
    for m in loaded.missions:
        secrets |= {c.desc for c in m.checks} | {c.hint for c in m.checks}
        secrets |= {spoiler.reveal(h) for h in m.hints} | {t.msg for t in m.traps}
        secrets |= {spoiler.reveal(i.answer) for i in (*m.items, *m.explain)}
        if m.solution:
            secrets.add(spoiler.reveal(m.solution))
    outputs = [quest("status", "--json")[1]]
    _pass_first(game, quest, answers)
    outputs.append(quest("status", "--json")[1])
    for out in outputs:
        found = [s for s in secrets if len(s) > 2 and s in out]
        assert found == []


def test_status_remaining_checks_follow_last_attempt(game: Path, quest: Quest) -> None:
    quest("check")  # hello.txt가 없어 체크 1 실패
    assert json.loads(quest("status", "--json")[1])["remaining_checks"] == {
        "numbers": [1], "count": 1,
    }


def test_status_needs_json_flag(game: Path, quest: Quest) -> None:
    assert quest("status")[0] == 2


# ───────────── IA-17 초기화 ─────────────


def test_reset_backs_up_and_starts_fresh(game: Path, quest: Quest, answers: list[str]) -> None:
    _pass_first(game, quest, answers)
    answers.append("초기화")
    code, out = quest("reset")
    assert code == 0 and "초기화했습니다" in out
    backups = list((game.parent / "home" / "backups").glob("state-*.db"))
    assert len(backups) == 1
    old = sqlite3.connect(backups[0])
    assert old.execute("SELECT xp_awarded FROM mission_progress").fetchone() == (12,)
    old.close()
    conn = _db(game)
    assert conn.execute("SELECT count(*) FROM mission_progress").fetchone() == (0,)
    events = conn.execute("SELECT kind, payload FROM events").fetchall()
    assert events == [("reset_backup", json.dumps({"backup": backups[0].name}))]
    assert "0 XP" in quest()[1]


@pytest.mark.parametrize("typed", ["y", "초기 화", ""])
def test_reset_needs_exact_phrase(
    game: Path, quest: Quest, answers: list[str], typed: str
) -> None:
    _pass_first(game, quest, answers)
    answers.append(typed)
    code, out = quest("reset")
    assert code == 0 and "초기화하지 않았습니다" in out
    assert not (game.parent / "home" / "backups").exists()
    assert "12 XP" in quest()[1]


def test_help_explains_restore(quest: Quest) -> None:
    code, out = quest("help")
    assert code == 0 and "백업에서 되돌리기" in out and "quest status --json" in out
