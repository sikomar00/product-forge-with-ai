"""진행 규칙: 현재 미션, 미션 시작, 채점 기록, 통과(Spec "진행 규칙", "채점", ERD v1.0).

쓰기 함수는 트랜잭션을 열지 않는다. 명령 하나가 state.transaction() 안에서 부른다.
"""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from quest.core.mission import Mission

# 장 이름은 design.md 5절에 공개돼 있다.
CHAPTERS = (
    "작업장", "터미널·Linux", "Git·GitHub 협업", "기획", "설계", "백엔드",
    "비동기·외부 연동", "프론트엔드", "테스트·품질", "컨테이너", "배포·인프라 선택", "CI/CD",
    "쿠버네티스 비교", "클라우드·IaC", "운영·관측", "제품 안의 AI", "분석·개선·런칭", "Forge Run",
)
RANKS = ((4, "견습"), (8, "주니어"), (13, "미들"), (17, "시니어 후보"))  # (마지막 장, 등급)
DONE = ("passed", "exempted")
CARD_FIRST_DUE = timedelta(days=1)  # 1번 상자 간격


def rank(chapter: int) -> str:
    return next(name for last, name in RANKS if chapter <= last)


def find(missions: tuple[Mission, ...], mission_id: str) -> Mission | None:
    return next((m for m in missions if m.id == mission_id), None)


def statuses(conn: sqlite3.Connection) -> dict[str, str]:
    return dict(conn.execute("SELECT mission_key, status FROM mission_progress"))


def current(missions: tuple[Mission, ...], status: dict[str, str]) -> Mission | None:
    """콘텐츠 순서에서 통과·면제가 아닌 첫 코어 미션. 저장하지 않고 계산한다(ERD 가정 5)."""
    return next(
        (m for m in missions if m.track == "core" and status.get(m.key) not in DONE), None
    )


def chapter_counts(
    missions: tuple[Mission, ...], status: dict[str, str], ch: int
) -> tuple[int, int]:
    """(통과·면제한 코어 미션 수, 장의 코어 미션 수)."""
    core = [m for m in missions if m.ch == ch and m.track == "core"]
    return sum(status.get(m.key) in DONE for m in core), len(core)


def progress_row(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM mission_progress WHERE mission_key = ?", (key,)).fetchone()


def mode(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT mode FROM game_state WHERE id = 1").fetchone()
    return row[0] if row else "normal"


def total_xp(conn: sqlite3.Connection) -> int:
    missions = conn.execute("SELECT coalesce(sum(xp_awarded), 0) FROM mission_progress")
    rebuilds = conn.execute(
        "SELECT coalesce(sum(json_extract(payload, '$.xp')), 0) FROM events"
        " WHERE kind = 'rebuild_passed'"  # ->>는 SQLite 3.38부터라 최소 버전 3.37에서 못 쓴다
    )
    return missions.fetchone()[0] + rebuilds.fetchone()[0]


def due_cards(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT due FROM v_due_cards").fetchone()[0]


def active_incident(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM incidents WHERE status = 'active'").fetchone() is not None


def event(conn: sqlite3.Connection, kind: str, mission_key: str | None, at: str,
          payload: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO events (at, kind, mission_key, payload) VALUES (?, ?, ?, ?)",
        (at, kind, mission_key, json.dumps(payload) if payload else None),
    )


def start(conn: sqlite3.Connection, m: Mission, at: str) -> bool:
    """미션을 처음 보여 줄 때 시작 기록을 만든다. 이미 있으면 False."""
    if progress_row(conn, m.key) is not None:
        return False
    conn.execute(
        "INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at,"
        " est_min, ai_tag) VALUES (?, ?, ?, 'in_progress', ?, ?, ?)",
        (m.key, m.id, m.ch, at, m.est_min, m.ai),
    )
    conn.execute(
        "INSERT OR IGNORE INTO chapter_progress (chapter, started_at) VALUES (?, ?)", (m.ch, at)
    )
    event(conn, "mission_started", m.key, at)
    return True


def record_attempt(conn: sqlite3.Connection, m: Mission, results: list[bool], at: str,
                   versions: tuple[str, str]) -> str:
    """quest check 한 번을 남기고 결과(pass·fail)를 돌려준다. 체크는 번호와 통과 여부만 쓴다."""
    outcome = "pass" if all(results) else "fail"
    row = progress_row(conn, m.key)
    if row["first_check_at"] is None:
        conn.execute("UPDATE mission_progress SET first_check_at = ? WHERE mission_key = ?",
                     (at, m.key))
        event(conn, "first_check", m.key, at)
    if outcome == "fail" and row["status"] == "in_progress":
        conn.execute("UPDATE mission_progress SET fails = fails + 1 WHERE mission_key = ?",
                     (m.key,))
    checks = [{"no": no, "ok": ok} for no, ok in enumerate(results, 1)]
    conn.execute(
        "INSERT INTO attempts (mission_key, display_id, mode, at, outcome, check_results,"
        " engine_version, content_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (m.key, m.id, mode(conn), at, outcome, json.dumps(checks), *versions),
    )
    return outcome


def pass_mission(conn: sqlite3.Connection, m: Mission, xp: int, at: str) -> None:
    """최종 통과: 진행을 통과로 바꾸고, 카드를 1번 상자에 넣고(만기 다음 날), 이벤트를 남긴다."""
    how = "solution" if progress_row(conn, m.key)["solution_seen"] else "normal"
    conn.execute(
        "UPDATE mission_progress SET status = 'passed', how = ?, completed_at = ?, xp_awarded = ?"
        " WHERE mission_key = ?",
        (how, at, xp, m.key),
    )
    due = datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) + CARD_FIRST_DUE
    conn.executemany(
        "INSERT OR IGNORE INTO cards (card_key, mission_key, kind, added_at, due_at)"
        " VALUES (?, ?, ?, ?, ?)",
        [(c.key, m.key, c.kind, at, due.strftime("%Y-%m-%dT%H:%M:%SZ")) for c in m.cards],
    )
    event(conn, "mission_passed", m.key, at, {"xp": xp})
