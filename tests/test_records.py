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


def test_readonly_connection_refuses_attach(game: Path, quest: Quest) -> None:
    quest()
    conn = readonly_connect()
    other = game.parent / "other.db"
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        conn.execute(f"ATTACH '{other.as_posix()}' AS o")
    assert not other.exists()  # ATTACH가 빈 파일을 만들지도 못한다
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("DELETE FROM main.events")
    conn.close()
    code, out = quest("stats", "--sql", f"ATTACH '{other.as_posix()}' AS o")
    assert code == 2 and "SQL 오류" in out and not other.exists()


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


def test_status_and_home_do_not_write(game: Path, quest: Quest) -> None:
    """읽기 명령은 기록을 남기지 않는다. AI 튜터가 status를 자주 읽어도 DB를 잠그지 않게."""
    quest()
    cfg = game.parent / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("= 20", "= 0"), encoding="utf-8")
    assert json.loads(quest("status", "--json")[1])["review_lock"] is True
    assert "복습 잠금" in quest()[1]
    assert _db(game).execute("SELECT count(*) FROM events").fetchone() == (0,)
    quest("mission")  # 새 미션 시작에서 잠금이 걸리면 그때 기록한다
    rows = _db(game).execute("SELECT kind, payload FROM events").fetchall()
    assert rows == [("review_lock_on", '{"due": 0}')]


def test_reset_refused_during_incident(game: Path, quest: Quest, answers: list[str]) -> None:
    _pass_first(game, quest, answers)
    _db(game).execute(
        "INSERT INTO incidents (mission_key, source, status, injected_at, snapshot_ref)"
        " VALUES ('m_f0000001', 'mission', 'active', '2026-01-01T00:00:00Z', 'snap-1')"
    )
    answers.append("초기화")
    code, out = quest("reset")
    assert code == 2 and "incident abort" in out
    assert not (game.parent / "home" / "backups").exists()


def test_two_resets_in_one_second_keep_both_backups(
    game: Path, quest: Quest, answers: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from quest.commands import system

    class FrozenNow:
        @staticmethod
        def now(tz: object) -> object:
            from datetime import datetime as real

            return real(2026, 11, 13, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(system, "datetime", FrozenNow)
    _pass_first(game, quest, answers)
    answers.extend(["초기화", "초기화"])
    quest("reset")
    quest("reset")
    names = sorted(p.name for p in (game.parent / "home" / "backups").iterdir())
    assert names == ["state-20261113T120000Z-2.db", "state-20261113T120000Z.db"]
    first = sqlite3.connect(game.parent / "home" / "backups" / names[1])
    assert first.execute("SELECT xp_awarded FROM mission_progress").fetchone() == (12,)
    first.close()


# ───────────── IA-10 졸업 기준 ─────────────


def test_goals_counts_passed_missions_only(game: Path, quest: Quest, answers: list[str]) -> None:
    code, out = quest("goals")
    out = " ".join(out.split())  # 칸 맞춤 공백은 보지 않는다
    assert code == 0 and "⬜ 기획 0/2" in out and "⬜ 설계 — 콘텐츠 준비 전" in out
    assert "졸업 기준 0/13 충족" in out
    _pass_first(game, quest, answers)
    answers.extend(["1", "3"])
    quest("check", "0-2")
    out = " ".join(quest("goals")[1].split())
    assert "✅ 기획 2/2" in out and "졸업 기준 1/13 충족" in out


@pytest.mark.parametrize(
    ("goals", "reason"),
    [
        ('[goals]\nmagic = ["m_f0000001"]', "알 수 없는 영역"),
        ('[goals]\nplanning = ["5-1"]', "미션 키 형식이 틀렸습니다"),  # 화면 번호는 키가 아니다
        ("[goals]\nplanning = []", "목록이 비었거나"),
    ],
)
def test_bad_goals_table_is_refused(tmp_path: Path, goals: str, reason: str) -> None:
    import shutil

    root = Path(shutil.copytree(FAKE, tmp_path / "c"))
    manifest = root / "content.toml"
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(text[: text.index("[goals]")] + goals + "\n", encoding="utf-8")
    with pytest.raises(content.EnvError, match=reason):
        content.load_content(root)


def test_goals_can_list_missions_not_written_yet(tmp_path: Path) -> None:
    """콘텐츠는 한 장씩 앞서 만든다. 앞으로 만들 미션 키를 미리 적어도 불러온다."""
    import shutil

    root = Path(shutil.copytree(FAKE, tmp_path / "c"))
    manifest = root / "content.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'testing = ["m_f0000011"]', 'testing = ["m_f0000011", "m_abcdef01"]'
        ),
        encoding="utf-8",
    )
    assert content.load_content(root).goals["testing"] == ("m_f0000011", "m_abcdef01")


def test_pad_uses_display_width() -> None:
    from quest.core import ui

    assert ui.display_width("기획") == 4 and ui.display_width("Git·CI/CD") == 9
    assert ui.pad("기획", 6) == "기획  " and ui.pad("CI", 6) == "CI    "
