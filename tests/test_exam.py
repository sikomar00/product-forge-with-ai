"""승급 시험·돌아가기 시험(M0-14, IA-7, IA-8): 면제, 보상 50%, 장 완료 방식."""

import sqlite3
from pathlib import Path

import pytest
from conftest import Quest

CH0_CORE = ("m_f0000001", "m_f0000002", "m_f0000003", "m_f0000004", "m_f0000005")


def _db(game: Path) -> sqlite3.Connection:
    return sqlite3.connect(game.parent / "home" / "state.db", isolation_level=None)


def _completed_via(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT completed_via FROM chapter_progress WHERE chapter = 1").fetchone()
    return row[0]


@pytest.fixture
def ch1(game: Path, quest: Quest) -> Path:
    """0장 코어 미션을 모두 통과한 상태(현재 미션은 1-1)."""
    quest()
    _db(game).executemany(
        "INSERT INTO mission_progress (mission_key, display_id, chapter, status, how, started_at,"
        " completed_at, est_min, ai_tag) VALUES (?, ?, 0, 'passed', 'normal',"
        " '2026-01-01T00:00:00Z', '2026-01-01T00:10:00Z', 5, 'solo')",
        [(key, f"0-{n}") for n, key in enumerate(CH0_CORE, 1)],
    )
    return game


def test_no_exam_in_chapter_zero(game: Path, quest: Quest) -> None:
    code, out = quest("exam")
    assert code == 2 and "0장에는 승급 시험이 없습니다" in out


def test_exam_pass_exempts_rest_with_half_reward(ch1: Path, quest: Quest) -> None:
    code, out = quest("exam")
    assert code == 0 and "1-B 🏁 가짜 보스" in out and "남은 코어 미션 2개" in out
    code, out = quest()
    assert "현재 미션: 1-B" in out and "[시험 모드]" in out
    code, out = quest("check")  # 대상은 보스
    assert code == 1 and "boss.txt" in out
    (ch1 / "boss.txt").write_text("x", encoding="utf-8")
    code, out = quest("check")
    assert code == 0 and "+30 XP" in out and "남은 미션 2개를 면제하고 +18 XP" in out

    conn = _db(ch1)
    rows = conn.execute(
        "SELECT display_id, status, how, xp_awarded FROM mission_progress WHERE chapter = 1"
        " ORDER BY display_id"
    ).fetchall()
    assert rows == [
        ("1-1", "exempted", "exam_skip", 8),  # round(15 × 0.5) = round(7.5) = 8
        ("1-2", "exempted", "exam_skip", 10),
        ("1-B", "passed", "exam", 30),
    ]  # 1-3은 선택 미션이라 면제하지 않는다
    assert _completed_via(conn) == "exam"
    assert conn.execute("SELECT mode FROM game_state").fetchone() == ("normal",)
    kinds = [k for (k,) in conn.execute("SELECT kind FROM events ORDER BY event_id")]
    assert kinds[-4:] == ["mission_passed", "mission_exempted", "mission_exempted", "exam_passed"]


def test_back_leaves_exam(ch1: Path, quest: Quest) -> None:
    quest("exam")
    code, out = quest("back")
    assert code == 0 and "시험 모드를 끝내고" in out
    code, out = quest()
    assert "현재 미션: 1-1" in out and "시험 모드" not in out
    kinds = [k for (k,) in _db(ch1).execute("SELECT kind FROM events ORDER BY event_id")]
    assert kinds[-2:] == ["exam_started", "exam_left"]
    assert quest("back")[1].strip() == "이미 일반 진행입니다."


def test_exam_refusals(ch1: Path, quest: Quest) -> None:
    quest("exam")
    assert "이미 시험 모드" in quest("exam")[1]
    quest("back")
    (ch1 / "boss.txt").write_text("x", encoding="utf-8")
    assert quest("check", "1-B")[0] == 0  # 시험 없이 보스를 먼저 통과
    code, out = quest("exam")
    assert code == 2 and "이미 통과" in out


def test_chapter_completes_only_when_core_missions_are_done(
    ch1: Path, quest: Quest, answers: list[str]
) -> None:
    (ch1 / "boss.txt").write_text("x", encoding="utf-8")
    quest("check", "1-B")  # 보스를 ID로 먼저 통과해도
    conn = _db(ch1)
    assert _completed_via(conn) is None  # 남은 코어 미션(1-1, 1-2)이 있어 장은 안 끝난다
    (ch1 / "fixed.txt").write_text("x", encoding="utf-8")
    answers.append("2")  # 1-1 🚀 설명 게이트
    quest("check", "1-1")
    assert _completed_via(conn) is None
    (ch1 / "recovered.txt").write_text("x", encoding="utf-8")
    quest("check", "1-2")
    assert _completed_via(conn) == "boss"  # 선택 미션 1-3은 상관없다


def test_no_exam_during_review_lock(ch1: Path, quest: Quest) -> None:
    cfg = ch1.parent / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("= 20", "= 0"), encoding="utf-8")
    code, out = quest("exam")
    assert code == 2 and "복습 잠금 중에는 시험을" in out


def test_exempted_mission_can_be_redone_for_goals(
    ch1: Path, quest: Quest, answers: list[str]
) -> None:
    quest("exam")
    (ch1 / "boss.txt").write_text("x", encoding="utf-8")
    quest("check")  # 1-1, 1-2 면제
    out = " ".join(quest("goals")[1].split())  # 칸 맞춤 공백은 보지 않는다
    assert "⬜ 테스트 0/1" in out and "1-1은 면제됨" in out
    code, out = quest("mission", "1-1")
    assert code == 0
    (ch1 / "fixed.txt").write_text("x", encoding="utf-8")
    answers.append("2")  # 🚀 설명 게이트를 다시 본다
    code, out = quest("check", "1-1")
    assert code == 0 and "졸업 기준에 인정됩니다" in out and "설명 게이트" in out
    row = _db(ch1).execute(
        "SELECT status, how, xp_awarded, started_at IS NOT NULL FROM mission_progress"
        " WHERE display_id = '1-1'"
    ).fetchone()
    assert row == ("passed", "normal", 8, 1)  # 보상은 면제 때 받은 50% 그대로
    assert "✅ 테스트 1/1" in " ".join(quest("goals")[1].split())


def test_exam_boss_with_solution_still_completes_by_exam(
    ch1: Path, quest: Quest, answers: list[str]
) -> None:
    quest("exam")
    answers.append("y")
    quest("solution")  # 보스 모범 답안(시험 중에도 볼 수 있다, 보상 20%)
    (ch1 / "boss.txt").write_text("x", encoding="utf-8")
    assert quest("check")[0] == 0
    assert _completed_via(_db(ch1)) == "exam"


def _exempt_chapter_one(ch1: Path, quest: Quest) -> None:
    quest("exam")
    (ch1 / "boss.txt").write_text("x", encoding="utf-8")
    quest("check")  # 1-1, 1-2 면제


def test_redo_counts_like_a_normal_mission(ch1: Path, quest: Quest, answers: list[str]) -> None:
    """면제된 미션 다시 하기: 실패·모범 답안·시작 시각을 새로 세고, 보상만 그대로 둔다."""
    _exempt_chapter_one(ch1, quest)
    assert quest("check", "1-1")[0] == 1  # fixed.txt가 아직 없다
    answers.append("y")
    code, out = quest("solution", "1-1")
    assert "보상은 바뀌지 않습니다" in out and "fixed.txt" in out
    (ch1 / "fixed.txt").write_text("x", encoding="utf-8")
    answers.append("2")
    assert quest("check", "1-1")[0] == 0
    row = _db(ch1).execute(
        "SELECT status, how, fails, solution_seen, xp_awarded FROM mission_progress"
        " WHERE display_id = '1-1'"
    ).fetchone()
    assert row == ("passed", "solution", 1, 1, 8)


def test_redo_does_not_take_over_current_mission(ch1: Path, quest: Quest) -> None:
    _exempt_chapter_one(ch1, quest)
    quest("mission", "1-1")  # 다시 하기 시작
    out = quest()[1]
    assert "현재 미션: 1-1" not in out  # 진행 흐름은 그대로(1장은 끝났다)
    assert "⬜ 테스트" in " ".join(quest("goals")[1].split())  # 통과 전에는 아직 면제


def test_redo_start_respects_review_lock(ch1: Path, quest: Quest) -> None:
    _exempt_chapter_one(ch1, quest)
    cfg = ch1.parent / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("= 20", "= 0"), encoding="utf-8")
    code, out = quest("mission", "1-1")
    assert code == 2 and "새 미션을 열지 않습니다" in out
