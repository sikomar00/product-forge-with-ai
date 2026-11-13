"""장애 기록(M1-05, ERD incidents, Spec "장애 주입"). progress.py에서 나눴다(500줄 규칙 여유).

쓰기 함수는 트랜잭션을 열지 않는다. 명령이 state.transaction() 안에서 부른다.
"""

import sqlite3

from quest.core.mission import Mission
from quest.core.progress import event
from quest.core.state import Tx


def active_incident(conn: sqlite3.Connection) -> bool:
    return incident_row(conn) is not None


def incident_row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """진행 중인 장애(하나뿐이다, ERD 부분 유일 인덱스)."""
    return conn.execute("SELECT * FROM incidents WHERE status = 'active'").fetchone()


def incident_started(conn: sqlite3.Connection, key: str) -> bool:
    """이 미션의 장애가 진행 중이거나 복구된 적이 있는지(장애 미션 채점의 전제)."""
    return conn.execute(
        "SELECT 1 FROM incidents WHERE mission_key = ? AND status IN ('active', 'recovered')",
        (key,),
    ).fetchone() is not None


def open_incident(tx: Tx, m: Mission, snapshot_ref: str) -> int:
    """장애 주입 직전에 active 행을 만든다. snapshot_ref는 스냅샷 폴더 이름(콘텐츠 글이 아니다)."""
    cursor = tx.conn.execute(
        "INSERT INTO incidents (mission_key, source, status, injected_at, snapshot_ref)"
        " VALUES (?, 'mission', 'active', ?, ?)",
        (m.key, tx.at, snapshot_ref),
    )
    event(tx, "incident_injected", m.key, {"incident": cursor.lastrowid})
    return cursor.lastrowid


def close_incident(tx: Tx, incident: sqlite3.Row, status: str) -> None:
    """recovered(복구 체크 통과) 또는 aborted(quest incident abort)로 끝낸다."""
    column = "recovered_at" if status == "recovered" else "aborted_at"
    tx.conn.execute(
        f"UPDATE incidents SET status = ?, {column} = ? WHERE incident_id = ?",
        (status, tx.at, incident["incident_id"]),
    )
    event(tx, f"incident_{status}", incident["mission_key"], {"incident": incident["incident_id"]})


def record_rca(tx: Tx, mission_key: str, correct: bool) -> None:
    """그 미션의 가장 최근 복구한 장애에 근본 원인 퀴즈 결과를 남긴다."""
    tx.conn.execute(
        "UPDATE incidents SET rca_correct = ? WHERE incident_id = (SELECT max(incident_id)"
        " FROM incidents WHERE mission_key = ? AND status = 'recovered')",
        (int(correct), mission_key),
    )
