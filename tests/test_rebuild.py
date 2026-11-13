"""재구성 복습·지연 확인 퀴즈 시험(M0-12): 샌드박스 채점, 보상, 주 1회, 장 완료 14일 뒤."""

import sqlite3
from pathlib import Path

from conftest import Quest

from quest.core import review


def _db(game: Path) -> sqlite3.Connection:
    return sqlite3.connect(game.parent / "home" / "state.db", isolation_level=None)


def _pass_first(game: Path, quest: Quest, answers: list[str]) -> None:
    (game / "hello.txt").write_text("hi", encoding="utf-8")
    answers.extend(["2", "2"])  # 설명 게이트
    assert quest("check")[0] == 0  # 원샷 12 XP


def test_rebuild_in_sandbox(game: Path, quest: Quest, answers: list[str]) -> None:
    _pass_first(game, quest, answers)
    answers.append("y")
    code, out = quest("review")
    assert code == 0 and "재구성 복습: 0-1" in out and "forge-sandbox" in out
    sandboxes = list((game.parent / "userhome" / "forge-sandbox").iterdir())
    assert [p.name[:4] for p in sandboxes] == ["0-1-"]
    assert "현재 미션: 0-1" in quest()[1] and "[복습 모드]" in quest()[1]

    code, out = quest("solution")  # 답을 베끼지 못하게
    assert code == 2 and "볼 수 없습니다" in out
    assert quest("hint")[0] == 2
    code, out = quest("check")  # 리포에는 hello.txt가 있지만 샌드박스는 비어 있다
    assert code == 1 and "hello.txt 없음" in out
    (sandboxes[0] / "hello.txt").write_text("again", encoding="utf-8")
    code, out = quest("check")
    assert code == 0 and "재구성 복습 통과! +3 XP" in out  # max(3, round(10 × 0.15))
    assert "12 XP" not in quest()[1] and "15 XP" in quest()[1]

    conn = _db(game)
    assert conn.execute("SELECT fails FROM mission_progress").fetchone() == (0,)  # 이미 통과
    modes = [m for (m,) in conn.execute("SELECT mode FROM attempts ORDER BY attempt_id")]
    assert modes == ["normal", "review", "review"]
    assert quest("review")[0] == 0 and "재구성 복습:" not in quest("review")[1]  # 주 1회


def test_back_leaves_rebuild(game: Path, quest: Quest, answers: list[str]) -> None:
    _pass_first(game, quest, answers)
    answers.append("y")
    quest("review")
    code, out = quest("back")
    assert code == 0 and "복습 모드를 끝내고" in out
    kinds = [k for (k,) in _db(game).execute("SELECT kind FROM events ORDER BY event_id")]
    assert kinds[-2:] == ["rebuild_started", "rebuild_left"]


def test_declining_rebuild_changes_nothing(game: Path, quest: Quest, answers: list[str]) -> None:
    _pass_first(game, quest, answers)
    answers.append("n")
    quest("review")
    assert "복습 모드" not in quest()[1]


def test_rebuild_target_order(game: Path, quest: Quest) -> None:
    quest()
    conn = _db(game)
    conn.executemany(
        "INSERT INTO mission_progress (mission_key, display_id, chapter, status, how, started_at,"
        " completed_at, solution_seen, est_min, ai_tag)"
        " VALUES (?, ?, ?, 'passed', ?, '2026-01-01T00:00:00Z', ?, ?, 5, 'solo')",
        [
            ("m_f0000001", "0-1", 0, "normal", "2026-01-02T00:00:00Z", 0),
            ("m_f0000011", "1-1", 1, "solution", "2026-03-01T00:00:00Z", 1),
            ("m_f0000014", "1-B", 1, "normal", "2026-01-01T00:00:00Z", 0),
        ],
    )
    keys = ["m_f0000001", "m_f0000011", "m_f0000014"]
    assert review.rebuild_target(conn, keys) == "m_f0000011"  # 모범 답안을 본 미션 먼저
    conn.execute("INSERT INTO events (at, kind, mission_key) VALUES"
                 " ('2026-04-01T00:00:00Z', 'rebuild_passed', 'm_f0000011')")
    assert review.rebuild_target(conn, keys) == "m_f0000014"  # 다음은 가장 오래전에 통과한 미션
    assert review.rebuild_target(conn, ["m_f0000002"]) is None


def _chapter_zero_done_long_ago(game: Path, quest: Quest) -> None:
    quest()
    _db(game).execute(
        "INSERT INTO chapter_progress (chapter, started_at, completed_at, completed_via)"
        " VALUES (0, '2026-01-01T00:00:00Z', '2026-01-02T00:00:00Z', 'boss')"
    )


def test_delayed_quiz_once(game: Path, quest: Quest, answers: list[str]) -> None:
    _chapter_zero_done_long_ago(game, quest)
    answers.extend(["2"] * 9 + ["1"])  # 마지막 문항만 틀린다
    code, out = quest("review")
    assert code == 0 and "0장 지연 확인 퀴즈: 9/10" in out
    conn = _db(game)
    rows = conn.execute("SELECT attempt_id, context, count(*), sum(correct) FROM responses")
    assert rows.fetchone() == (None, "delayed_quiz", 10, 9)
    assert conn.execute("SELECT delayed_quiz_done_at FROM chapter_progress").fetchone()[0]
    assert "지연 확인 퀴즈" not in quest("review")[1]


def test_unfinished_delayed_quiz_is_asked_again(
    game: Path, quest: Quest, answers: list[str]
) -> None:
    _chapter_zero_done_long_ago(game, quest)
    answers.extend(["2"] * 3)
    code, out = quest("review")
    assert code == 2 and "처음부터 다시" in out
    conn = _db(game)
    assert conn.execute("SELECT count(*) FROM responses").fetchone() == (0,)
    assert conn.execute("SELECT delayed_quiz_done_at FROM chapter_progress").fetchone() == (None,)
