"""복습(M0-12)과 복습 잠금(M0-13): Leitner 상자, 연속 복습일, 잠금 기록(Spec "복습").

쓰기 함수는 트랜잭션을 열지 않는다. 명령이 state.transaction() 안에서 부른다.
"""

import sqlite3
from datetime import date, timedelta

from quest.core.progress import event
from quest.core.state import KST, format_utc, parse_utc

INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}  # 📐 상자 → 다음 만기까지 날 수
MAX_CARDS = 15
DEFAULT_LOCK = 20
_NOW = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"


def next_box(box: int, correct: bool) -> int:
    """맞으면 한 칸 위(최대 5), 틀리면 1번. 상자 규칙은 DB가 아니라 엔진이 지킨다(ERD 가정 8)."""
    return min(5, box + 1) if correct else 1


def due_cards(conn: sqlite3.Connection, limit: int = MAX_CARDS) -> list[sqlite3.Row]:
    """만기가 오래된 순서로 최대 limit장."""
    return conn.execute(
        f"SELECT card_key, box FROM cards WHERE due_at <= {_NOW} ORDER BY due_at LIMIT ?",
        (limit,),
    ).fetchall()


def record_review(conn: sqlite3.Connection, card: sqlite3.Row, answer: tuple[bool, int | None],
                  at: str) -> int:
    """카드 복습 한 번을 남기고 새 상자를 돌려준다. answer는 (정답 여부, 확신도)."""
    correct, confidence = answer
    box = next_box(card["box"], correct)
    due = format_utc(parse_utc(at) + timedelta(days=INTERVAL_DAYS[box]))
    conn.execute(
        "UPDATE cards SET box = ?, due_at = ?, last_reviewed_at = ? WHERE card_key = ?",
        (box, due, at, card["card_key"]),
    )
    conn.execute(
        "INSERT INTO reviews (card_key, at, correct, confidence, box_before, box_after)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (card["card_key"], at, int(correct), confidence, card["box"], box),
    )
    return box


def streak(conn: sqlite3.Connection, today: date) -> int:
    """quest review를 끝낸 날(한국 날짜)이 오늘 또는 어제부터 거꾸로 이어진 날 수."""
    days = {
        parse_utc(row[0]).astimezone(KST).date()
        for row in conn.execute("SELECT at FROM events WHERE kind = 'review_finished'")
    }
    day = today if today in days else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


def lock_threshold(cfg: dict) -> int:
    return int(cfg.get("review", {}).get("lock_threshold", DEFAULT_LOCK))


def locked(conn: sqlite3.Connection, threshold: int) -> bool:
    return conn.execute("SELECT due FROM v_due_cards").fetchone()[0] >= threshold


def sync_lock(conn: sqlite3.Connection, threshold: int, at: str) -> bool:
    """잠금 상태가 바뀌었으면 review_lock_on·off를 남기고 지금 잠겼는지 돌려준다."""
    now_locked = locked(conn, threshold)
    last = conn.execute(
        "SELECT kind FROM events WHERE kind IN ('review_lock_on', 'review_lock_off')"
        " ORDER BY event_id DESC LIMIT 1"
    ).fetchone()
    was_locked = last is not None and last[0] == "review_lock_on"
    if now_locked != was_locked:
        event(conn, "review_lock_on" if now_locked else "review_lock_off", None, at,
              {"due": conn.execute("SELECT due FROM v_due_cards").fetchone()[0]})
    return now_locked
