"""문항형 미션·확신도·설명 게이트 시험(M0-07, M0-11, IA-3)."""

import sqlite3
from pathlib import Path

from conftest import Quest


def _db(game: Path) -> sqlite3.Connection:
    return sqlite3.connect(game.parent / "home" / "state.db")


def _responses(game: Path) -> list[tuple]:
    conn = _db(game)
    rows = conn.execute(
        "SELECT context, item_no, correct, confidence FROM responses ORDER BY response_id"
    ).fetchall()
    conn.close()
    return rows


def test_quiz_asks_confidence_and_records_response(
    game: Path, quest: Quest, answers: list[str]
) -> None:
    answers.extend(["1", "3"])  # 답, 확신도
    code, out = quest("check", "0-2")
    assert code == 0 and "확신도 1(찍음)" in out and "✅ 맞았습니다" in out and "+6 XP" in out
    assert _responses(game) == [("mission", 1, 1, 3)]


def test_wrong_quiz_answer_fails_and_counts(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.extend(["2", "3"])
    code, out = quest("check", "0-2")
    assert code == 1 and "❌ 틀렸습니다" in out
    assert _responses(game) == [("mission", 1, 0, 3)]
    conn = _db(game)
    assert conn.execute("SELECT fails FROM mission_progress").fetchone() == (1,)
    assert conn.execute("SELECT outcome, check_results FROM attempts").fetchone() == ("fail", "[]")


def test_confidence_must_be_one_to_three(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.extend(["1", "5", "2"])
    code, out = quest("check", "0-2")
    assert code == 0 and "1, 2, 3 가운데 하나" in out
    assert _responses(game) == [("mission", 1, 1, 2)]


def test_drill_regex_and_decision_formats(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.append("git log --oneline")
    assert quest("check", "0-4")[0] == 0
    answers.extend(["1", "3,1", "2,1,3"])
    code, out = quest("check", "0-5")
    assert code == 0 and "번호 여러 개" in out and "순서대로 번호" in out


def test_unfinished_answers_are_not_recorded(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.append("1")  # 확신도 전에 입력이 끝난다
    code, out = quest("check", "0-2")
    assert code == 2 and "기록하지 않았습니다" in out
    conn = _db(game)
    assert conn.execute("SELECT count(*) FROM attempts").fetchone() == (0,)


def test_wrong_explain_gate_blocks_pass(game: Path, quest: Quest, answers: list[str]) -> None:
    (game / "hello.txt").write_text("hi", encoding="utf-8")
    answers.extend(["2", "1"])  # 게이트 2번 문항을 틀린다
    code, out = quest("check")
    assert code == 1 and "설명 게이트" in out and "아직 통과가 아닙니다" in out
    answers.extend(["2", "2"])
    code, out = quest("check")  # 체크와 게이트를 처음부터 다시 본다
    assert code == 0 and "+10 XP" in out  # 게이트 실패도 실패 1번이라 원샷이 아니다
    contexts = [(c, n, ok) for c, n, ok, _ in _responses(game)]
    assert contexts == [
        ("explain_gate", 1, 1), ("explain_gate", 2, 0),
        ("explain_gate", 1, 1), ("explain_gate", 2, 1),
    ]


def test_solo_mission_has_no_gate(game: Path, quest: Quest, answers: list[str]) -> None:
    (game / "boss.txt").write_text("x", encoding="utf-8")
    code, out = quest("check", "1-B")
    assert code == 0 and "설명 게이트" not in out
