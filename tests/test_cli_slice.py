"""첫 세로 조각 시험(T0-4): 가짜 실습 미션 하나가 홈 → 미션 → 채점 → 통과까지 돈다.

IA-1·IA-2·IA-3(체크 유형)·IA-16과 종료 코드 0·1·2·3을 본다.
"""

import sqlite3
from pathlib import Path

import pytest
from conftest import Quest


def test_ops_mission_end_to_end(game: Path, quest: Quest) -> None:
    code, out = quest()
    assert code == 0
    assert "견습 · 0 XP" in out and "0장 작업장" in out and "현재 미션: 0-1 🎫 가짜 실습" in out
    assert "다음: quest mission" in out

    code, out = quest("mission")
    assert code == 0 and "hello.txt를 만드세요" in out and "가짜 개념 앞면" in out

    code, out = quest("check")
    assert code == 1 and "❌ 1. hello.txt 파일이 있다" in out
    assert "↳ hello.txt 파일을 만드세요" in out

    (game / "hello.txt").write_text("hi", encoding="utf-8")
    code, out = quest("check")
    assert code == 0 and "✅ 1." in out and "+10 XP" in out and "원샷" not in out
    assert "카드 1장" in out and "다음 미션: 0-2" in out

    code, out = quest()
    assert "10 XP" in out and "현재 미션: 0-2" in out and "1/5" in out

    code, out = quest("check", "0-1")
    assert code == 0 and "이미 끝낸 미션" in out

    conn = sqlite3.connect(game.parent / "home" / "state.db")
    row = conn.execute(
        "SELECT status, how, fails, xp_awarded FROM mission_progress WHERE display_id = '0-1'"
    ).fetchone()
    assert row == ("passed", "normal", 1, 10)
    outcomes = [r[0] for r in conn.execute("SELECT outcome FROM attempts ORDER BY attempt_id")]
    assert outcomes == ["fail", "pass", "pass"]
    kinds = [r[0] for r in conn.execute("SELECT kind FROM events ORDER BY event_id")]
    assert kinds == ["mission_started", "first_check", "mission_passed"]
    assert conn.execute("SELECT box FROM cards").fetchall() == [(1,)]
    assert conn.execute("SELECT value FROM meta WHERE key = 'engine_version'").fetchone() == (
        "0.1.0",
    )


def test_one_shot_pass_gets_bonus(game: Path, quest: Quest) -> None:
    (game / "hello.txt").write_text("hi", encoding="utf-8")
    code, out = quest("check")
    assert code == 0 and "+12 XP (원샷 보너스)" in out


def test_audit_mission_hides_failed_check_description(
    game: Path, quest: Quest
) -> None:
    code, out = quest("check", "1-1")
    assert code == 1 and "체크 0/1 통과" in out and "fixed.txt 파일이 있다" not in out


def test_unknown_mission_id_is_usage_error(game: Path, quest: Quest) -> None:
    code, out = quest("mission", "9-9")
    assert code == 2 and "그런 미션이 없습니다: 9-9" in out


@pytest.mark.parametrize("args", [["dance"], ["mission", "0-1", "0-2"]])
def test_unknown_command_or_extra_args_show_help(
    args: list[str], quest: Quest
) -> None:
    code, out = quest(*args)
    assert code == 2 and "quest mission [ID]" in out


def test_help_lists_commands(quest: Quest) -> None:
    code, out = quest("help")
    assert code == 0 and "quest check [ID]" in out and "quest help" in out


def test_missing_content_is_env_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quest: Quest
) -> None:
    monkeypatch.setenv("QUEST_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("QUEST_CONFIG", str(tmp_path / "config.toml"))
    code, out = quest()
    assert code == 3 and "설정 파일을 만들었습니다" in out and "quest update" in out
