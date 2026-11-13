"""힌트·모범 답안 시험(M0-08, M0-09, IA-4, IA-5): 확인 질문, 감점, 기록."""

import sqlite3
from pathlib import Path

from conftest import Quest


def _row(game: Path, *cols: str) -> tuple:
    conn = sqlite3.connect(game.parent / "home" / "state.db")
    row = conn.execute(
        f"SELECT {', '.join(cols)} FROM mission_progress WHERE display_id = '0-1'"
    ).fetchone()
    conn.close()
    return row


def _events(game: Path) -> list[tuple[str, str | None]]:
    conn = sqlite3.connect(game.parent / "home" / "state.db")
    rows = conn.execute("SELECT kind, payload FROM events ORDER BY event_id").fetchall()
    conn.close()
    return rows


def test_hint_asks_first_and_shows_penalty(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.append("n")
    code, out = quest("hint")
    assert code == 0 and "힌트 1단계를 열면 보상이 12 → 8 XP" in out and "열지 않았습니다" in out
    assert _row(game, "hints_used") == (0,)


def test_no_input_means_no(game: Path, quest: Quest, answers: list[str]) -> None:
    code, out = quest("hint")
    assert "열지 않았습니다" in out and _row(game, "hints_used") == (0,)


def test_three_hints_then_solution_guidance(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.extend(["y", "Y", "ㅛ"])
    outs = [quest("hint")[1] for _ in range(3)]
    assert "💡 힌트 1/3\n방향 1" in outs[0]
    assert "💡 힌트 3/3\n구체 명령" in outs[2] and "quest solution" in outs[2]
    code, out = quest("hint")
    assert code == 0 and "모두 봤습니다" in out
    assert _row(game, "hints_used") == (3,)
    levels = [p for kind, p in _events(game) if kind == "hint_opened"]
    assert levels == ['{"level": 1}', '{"level": 2}', '{"level": 3}']


def test_hint_lowers_reward(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.append("y")
    quest("hint")
    (game / "hello.txt").write_text("hi", encoding="utf-8")
    code, out = quest("check")
    assert code == 0 and "+8 XP" in out


def test_solution_then_pass_gives_20_percent(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.append("y")
    code, out = quest("solution")
    assert "12 → 2 XP" in out and "📖 모범 답안\ntouch hello.txt" in out
    code, out = quest("solution")  # 이미 봤으면 다시 묻지 않는다
    assert "볼까요" not in out and "touch hello.txt" in out
    (game / "hello.txt").write_text("hi", encoding="utf-8")
    code, out = quest("check")
    assert code == 0 and "+2 XP" in out and "원샷" not in out
    assert _row(game, "how", "solution_seen", "xp_awarded") == ("solution", 1, 2)
    assert [k for k, _ in _events(game)].count("solution_viewed") == 1


def test_finished_mission_solution_is_free(game: Path, quest: Quest, answers: list[str]) -> None:
    (game / "hello.txt").write_text("hi", encoding="utf-8")
    quest("check")
    code, out = quest("solution", "0-1")
    assert "볼까요" not in out and "touch hello.txt" in out
    assert _row(game, "solution_seen", "xp_awarded") == (0, 12)
    code, out = quest("hint", "0-1")
    assert "이미 끝낸 미션" in out


def test_mission_without_solution(game: Path, quest: Quest, answers: list[str]) -> None:
    code, out = quest("solution", "0-2")
    assert code == 0 and "모범 답안이 없습니다" in out
