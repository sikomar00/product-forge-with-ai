"""복습(M0-12)과 복습 잠금(M0-13): Leitner 상자, 연속 복습일, 잠금 기록,
재구성 복습, 지연 확인 퀴즈(Spec "복습").

쓰기 함수는 트랜잭션을 열지 않는다. 명령이 state.transaction() 안에서 부른다.
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from quest.core.config import EnvError
from quest.core.progress import event
from quest.core.state import KST, Tx, format_utc, parse_utc

INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}  # 📐 상자 → 다음 만기까지 날 수
MAX_CARDS = 15
DEFAULT_LOCK = 20
_NOW = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"


def next_box(box: int, correct: bool) -> int:
    """맞으면 한 칸 위(최대 5), 틀리면 1번. 상자 규칙은 DB가 아니라 엔진이 지킨다(ERD 가정 8)."""
    return min(5, box + 1) if correct else 1


def due_cards(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """만기가 된 카드 전부, 만기가 오래된 순서. 콘텐츠에 있는 카드만 고르는 것은 명령이 한다.

    지운 미션의 카드는 DB에 남는다. 그 카드까지 세면 복습 잠금이 영영 풀리지 않는다.
    """
    return conn.execute(
        f"SELECT card_key, box FROM cards WHERE due_at <= {_NOW} ORDER BY due_at"
    ).fetchall()


def record_review(tx: Tx, card: sqlite3.Row, answer: tuple[bool, int | None]) -> int:
    """카드 복습 한 번을 남기고 새 상자를 돌려준다. answer는 (정답 여부, 확신도)."""
    correct, confidence = answer
    box = next_box(card["box"], correct)
    due = format_utc(parse_utc(tx.at) + timedelta(days=INTERVAL_DAYS[box]))
    tx.conn.execute(
        "UPDATE cards SET box = ?, due_at = ?, last_reviewed_at = ? WHERE card_key = ?",
        (box, due, tx.at, card["card_key"]),
    )
    tx.conn.execute(
        "INSERT INTO reviews (card_key, at, correct, confidence, box_before, box_after)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (card["card_key"], tx.at, int(correct), confidence, card["box"], box),
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
    value = cfg.get("review", {}).get("lock_threshold", DEFAULT_LOCK)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise EnvError(f"설정 파일의 [review] lock_threshold는 0 이상의 정수여야 합니다: {value!r}")
    return value


def sync_lock(tx: Tx, due: int, threshold: int) -> None:
    """잠금 상태가 바뀌었으면 review_lock_on·off를 남긴다. 값은 그때의 만기 카드 수다."""
    now_locked = due >= threshold
    last = tx.conn.execute(
        "SELECT kind FROM events WHERE kind IN ('review_lock_on', 'review_lock_off')"
        " ORDER BY event_id DESC LIMIT 1"
    ).fetchone()
    was_locked = last is not None and last[0] == "review_lock_on"
    if now_locked != was_locked:
        event(tx, "review_lock_on" if now_locked else "review_lock_off", None, {"due": due})


# ───────────── 재구성 복습 ─────────────

REBUILD_EVERY = timedelta(days=7)


def rebuild_due(conn: sqlite3.Connection, at: str) -> bool:
    """마지막 재구성 복습 시작에서 7일이 지났거나 한 번도 안 했으면 True."""
    last = conn.execute("SELECT max(at) FROM events WHERE kind = 'rebuild_started'").fetchone()[0]
    return last is None or parse_utc(at) - parse_utc(last) >= REBUILD_EVERY


def rebuild_target(conn: sqlite3.Connection, candidates: list[str]) -> str | None:
    """재구성할 미션 키. 모범 답안을 보고 통과한 미션 → 오래전에 통과한 미션 순서다.

    이미 재구성을 통과한 미션은 뒤로 보낸다. 같은 미션만 매주 나오지 않게 하려는 것이다.
    candidates는 콘텐츠에서 고른 체크형·랩 불필요 미션 키다.
    """
    marks = ",".join("?" * len(candidates))
    row = conn.execute(
        f"SELECT mission_key FROM mission_progress mp WHERE status = 'passed'"
        f" AND mission_key IN ({marks}) ORDER BY EXISTS (SELECT 1 FROM events e"
        " WHERE e.kind = 'rebuild_passed' AND e.mission_key = mp.mission_key),"
        " solution_seen DESC, completed_at LIMIT 1",
        candidates,
    ).fetchone()
    return row[0] if row else None


def sandbox_path(display_id: str, started_at: str) -> Path:
    """~/forge-sandbox/<화면 번호>-<YYYYMMDD 한국 날짜>/ (Spec "파일 위치")."""
    day = parse_utc(started_at).astimezone(KST).strftime("%Y%m%d")
    return Path.home() / "forge-sandbox" / f"{display_id}-{day}"


# ───────────── 지연 확인 퀴즈 ─────────────


def delayed_quiz_chapters(conn: sqlite3.Connection) -> list[int]:
    """장 완료 14일 뒤 만기가 됐고 아직 풀지 않은 장."""
    rows = conn.execute(f"SELECT chapter FROM v_delayed_quiz_due WHERE due_at <= {_NOW}")
    return [row[0] for row in rows]


def record_delayed_quiz(tx: Tx, chapter: int,
                        answered: list[tuple[int, bool, int | None]]) -> None:
    """(문항 번호, 정답 여부, 확신도) 목록을 남기고 그 장의 지연 확인 퀴즈를 끝낸다."""
    tx.conn.executemany(
        "INSERT INTO responses (attempt_id, chapter, context, item_no, correct, confidence, at)"
        " VALUES (NULL, ?, 'delayed_quiz', ?, ?, ?, ?)",
        [(chapter, no, int(ok), conf, tx.at) for no, ok, conf in answered],
    )
    tx.conn.execute(
        "UPDATE chapter_progress SET delayed_quiz_done_at = ? WHERE chapter = ?", (tx.at, chapter)
    )
