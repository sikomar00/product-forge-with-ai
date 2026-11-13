"""배지(Spec "채점" 6, "보상", design.md 3.6절, S1 award_badges).

엔진이 직접 판단하는 배지 4개와, 콘텐츠가 미션마다 정하는 배지(Mission.badge)가 있다.
DB에는 배지 키와 얻은 시각만 남긴다(콘텐츠 텍스트를 저장하지 않는다, ERD 가정 3).
"""

import sqlite3

from quest.core import review
from quest.core.mission import Mission
from quest.core.state import KST, Tx, parse_utc

ENGINE_BADGES = {
    "first_pass": "🎫 첫 미션 통과",
    "oneshot5": "🎯 원샷 5연속",
    "exam_skip": "🚀 월반(승급 시험 통과)",
    "steady14": "📅 꾸준함(연속 복습 14일)",
}
ONE_SHOT_RUN = 5
STEADY_DAYS = 14


def name(key: str) -> str:
    """화면 이름. 콘텐츠 배지는 키를 그대로 보여 준다."""
    return ENGINE_BADGES.get(key, f"🏅 {key}")


def _one_shot_run(conn: sqlite3.Connection) -> int:
    """가장 최근 통과부터 거꾸로 이어진 원샷(실패·힌트·모범 답안 없음) 통과 수. S1과 같은 규칙."""
    rows = conn.execute(
        "SELECT fails = 0 AND hints_used = 0 AND solution_seen = 0 FROM mission_progress"
        " WHERE status = 'passed' ORDER BY completed_at DESC, rowid DESC"
    ).fetchall()
    run = 0
    for (one_shot,) in rows:
        if not one_shot:
            break
        run += 1
    return run


def _due(conn: sqlite3.Connection, at: str) -> list[str]:
    """지금 조건을 만족하는 엔진 배지 키."""
    rules = {
        "first_pass": conn.execute(
            "SELECT 1 FROM mission_progress WHERE status = 'passed'").fetchone() is not None,
        "oneshot5": _one_shot_run(conn) >= ONE_SHOT_RUN,
        "exam_skip": conn.execute(
            "SELECT 1 FROM events WHERE kind = 'exam_passed'").fetchone() is not None,
        "steady14": review.streak(conn, parse_utc(at).astimezone(KST).date()) >= STEADY_DAYS,
    }
    return [key for key, met in rules.items() if met]


def award(tx: Tx, passed: Mission | None) -> list[str]:
    """조건을 만족한 배지를 주고, 이번에 새로 얻은 키를 돌려준다. passed는 방금 통과한 미션."""
    keys = _due(tx.conn, tx.at) + ([passed.badge] if passed and passed.badge else [])
    new = []
    for key in keys:
        cursor = tx.conn.execute(
            "INSERT OR IGNORE INTO badges (badge_key, earned_at) VALUES (?, ?)", (key, tx.at)
        )
        if cursor.rowcount:
            new.append(key)
    return new


def earned(conn: sqlite3.Connection) -> list[str]:
    return [row[0] for row in conn.execute("SELECT badge_key FROM badges ORDER BY earned_at")]
