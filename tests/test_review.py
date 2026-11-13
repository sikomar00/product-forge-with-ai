"""복습 시험(M0-12, M0-13): Leitner 상자, 연속 복습일, 카드 채점, 복습 잠금."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from conftest import Quest

from quest.core import review
from quest.core.answers import card_correct
from quest.core.mission import Card


@pytest.mark.parametrize(
    ("box", "correct", "expected"), [(1, True, 2), (4, True, 5), (5, True, 5), (3, False, 1)]
)
def test_next_box(box: int, correct: bool, expected: int) -> None:
    assert review.next_box(box, correct) == expected


@pytest.mark.parametrize(
    ("card", "response", "expected"),
    [
        (Card("c_00000001", "concept", "앞", "나", "choice", ("가", "나")), "2", True),
        (Card("c_00000001", "concept", "앞", "나", "choice", ("가", "나")), "1", False),
        (Card("c_00000001", "concept", "앞", "나", "choice", ("가", "나")), "나", False),
        (Card("c_00000001", "usage", "앞", "git log", "regex", (r"^git\s+log",)), "git log", True),
        (Card("c_00000001", "usage", "앞", "git log", "regex", (r"^git\s+log",)), "log", False),
    ],
)
def test_card_correct(card: Card, response: str, expected: bool) -> None:
    assert card_correct(card, response) is expected


def _db(game: Path) -> sqlite3.Connection:
    return sqlite3.connect(game.parent / "home" / "state.db", isolation_level=None)


def _finish_on(conn: sqlite3.Connection, *days: str) -> None:
    conn.executemany(
        "INSERT INTO events (at, kind) VALUES (?, 'review_finished')", [(d,) for d in days]
    )


def test_streak_counts_korean_days(game: Path, quest: Quest) -> None:
    quest()
    conn = _db(game)
    # UTC 16시 전후로 한국 날짜가 바뀐다: 각각 한국 11-11, 11-12, 11-13
    _finish_on(conn, "2026-11-10T16:00:00Z", "2026-11-11T16:00:00Z", "2026-11-12T15:30:00Z")
    assert review.streak(conn, date(2026, 11, 13)) == 3
    assert review.streak(conn, date(2026, 11, 14)) == 3  # 오늘 아직 안 했어도 어제까지 이어진다
    assert review.streak(conn, date(2026, 11, 15)) == 0


def _pass_first_mission_and_make_cards_due(game: Path, quest: Quest, answers: list[str]) -> None:
    (game / "hello.txt").write_text("hi", encoding="utf-8")
    answers.extend(["2", "2"])
    assert quest("check")[0] == 0
    _db(game).execute("UPDATE cards SET due_at = '2020-01-01T00:00:00Z'")


def test_review_moves_card_up_and_records(game: Path, quest: Quest, answers: list[str]) -> None:
    _pass_first_mission_and_make_cards_due(game, quest, answers)
    answers.extend(["2", "3"])  # 객관식 카드 답, 확신도
    code, out = quest("review")
    assert code == 0 and "오늘 복습할 카드: 1장" in out and "2번 상자, 2일 뒤" in out
    assert "1/1 맞힘 · 연속 복습 1일" in out
    conn = _db(game)
    assert conn.execute("SELECT box FROM cards").fetchone() == (2,)
    rows = conn.execute("SELECT correct, confidence, box_before, box_after FROM reviews")
    assert rows.fetchall() == [(1, 3, 1, 2)]
    code, out = quest("review")
    assert "오늘 복습할 카드: 0장" in out  # 만기가 이틀 뒤로 밀렸다


def test_self_and_regex_cards(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.extend(["3", "1"])  # 0-3 예측 미션 통과(답, 확신도)
    assert quest("check", "0-3")[0] == 0
    _db(game).execute("UPDATE cards SET due_at = '2020-01-01T00:00:00Z'")
    answers.extend(["", "y", "git log -3", "2"])  # 자가 채점: Enter, 맞음 / 정규식: 답, 확신도
    code, out = quest("review")
    assert code == 0 and "가짜 뒷면" in out and "2/2 맞힘" in out


def test_stopping_midway_keeps_answered_cards(
    game: Path, quest: Quest, answers: list[str]
) -> None:
    _pass_first_mission_and_make_cards_due(game, quest, answers)
    code, out = quest("review")  # 답이 없다(EOF)
    assert code == 2 and "멈췄습니다" in out
    kinds = [k for (k,) in _db(game).execute("SELECT kind FROM events")]
    assert "review_started" in kinds and "review_finished" not in kinds


def test_review_lock_blocks_only_new_missions(
    game: Path, quest: Quest, answers: list[str]
) -> None:
    _pass_first_mission_and_make_cards_due(game, quest, answers)
    cfg = game.parent / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("= 20", "= 1"), encoding="utf-8")

    code, out = quest()
    assert "🔒 복습 잠금: 만기 카드 1장" in out
    code, out = quest("mission")  # 0-2는 새 미션
    assert code == 2 and "새 미션을 열지 않습니다" in out
    code, out = quest("check", "0-1")  # 끝낸 미션은 막지 않는다
    assert code == 0

    answers.extend(["2", "3"])
    quest("review")
    code, out = quest("mission")
    assert code == 0 and "가짜 퀴즈" in out
    rows = _db(game).execute(
        "SELECT kind FROM events WHERE kind LIKE 'review_lock%' ORDER BY event_id"
    )
    kinds = [k for (k,) in rows]
    assert kinds == ["review_lock_on", "review_lock_off"]
