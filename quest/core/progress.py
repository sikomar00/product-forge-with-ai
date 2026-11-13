"""진행 규칙: 현재 미션, 미션 시작, 채점 기록, 통과(Spec "진행 규칙", "채점", ERD v1.0).

쓰기 함수는 트랜잭션을 열지 않는다. 명령 하나가 state.transaction() 안에서 부른다.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import timedelta

from quest.core import rewards
from quest.core.mission import Mission
from quest.core.state import format_utc, parse_utc

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


def chapter_core(missions: tuple[Mission, ...], ch: int) -> list[Mission]:
    """장의 코어 미션(선택 미션 제외), 콘텐츠 순서."""
    return [m for m in missions if m.ch == ch and m.track == "core"]


def chapter_counts(
    missions: tuple[Mission, ...], status: dict[str, str], ch: int
) -> tuple[int, int]:
    """(통과·면제한 코어 미션 수, 장의 코어 미션 수)."""
    core = chapter_core(missions, ch)
    return sum(status.get(m.key) in DONE for m in core), len(core)


def progress_row(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM mission_progress WHERE mission_key = ?", (key,)).fetchone()


def mode(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT mode FROM game_state WHERE id = 1").fetchone()
    return row[0] if row else "normal"


def mode_mission(conn: sqlite3.Connection) -> str | None:
    """시험·복습 모드의 대상 미션 키. 일반 모드면 None."""
    row = conn.execute("SELECT mode_mission_key FROM game_state WHERE id = 1").fetchone()
    return row[0] if row else None


def mode_started(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT mode_started_at FROM game_state WHERE id = 1").fetchone()
    return row[0] if row else None


def set_mode(conn: sqlite3.Connection, new_mode: str, mission_key: str | None, at: str) -> None:
    started = None if new_mode == "normal" else at
    conn.execute(
        "INSERT INTO game_state (id, mode, mode_mission_key, mode_started_at, updated_at)"
        " VALUES (1, ?, ?, ?, ?) ON CONFLICT (id) DO UPDATE SET mode = excluded.mode,"
        " mode_mission_key = excluded.mode_mission_key,"
        " mode_started_at = excluded.mode_started_at, updated_at = excluded.updated_at",
        (new_mode, mission_key, started, at),
    )


def total_xp(conn: sqlite3.Connection) -> int:
    missions = conn.execute("SELECT coalesce(sum(xp_awarded), 0) FROM mission_progress")
    rebuilds = conn.execute(
        "SELECT coalesce(sum(json_extract(payload, '$.xp')), 0) FROM events"
        " WHERE kind = 'rebuild_passed'"  # ->>는 SQLite 3.38부터라 최소 버전 3.37에서 못 쓴다
    )
    return missions.fetchone()[0] + rebuilds.fetchone()[0]


def active_incident(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM incidents WHERE status = 'active'").fetchone() is not None


def event(conn: sqlite3.Connection, kind: str, mission_key: str | None, at: str,
          payload: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO events (at, kind, mission_key, payload) VALUES (?, ?, ?, ?)",
        (at, kind, mission_key, json.dumps(payload) if payload else None),
    )


def start(conn: sqlite3.Connection, m: Mission, at: str) -> bool:
    """미션을 처음 보여 줄 때 시작 기록을 만든다. 이미 시작했으면 False.

    면제된 미션은 시작 시각 없이 생긴다. 학습자가 직접 다시 하면 그때 시작 시각을 채운다.
    """
    row = progress_row(conn, m.key)
    if row is not None and row["started_at"] is not None:
        return False
    if row is not None:
        conn.execute("UPDATE mission_progress SET started_at = ? WHERE mission_key = ?",
                     (at, m.key))
        event(conn, "mission_started", m.key, at)
        return True
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


@dataclass(frozen=True)
class Attempt:
    """quest check 한 번의 결과. 내용(설명·정답)이 아니라 번호와 정오만 담는다."""

    checks: list[bool]  # 체크 번호 순서의 통과 여부. 문항형 미션은 빈 목록
    passed: bool
    at: str
    versions: tuple[str, str]  # (엔진, 콘텐츠)
    responses: list[tuple[str, int, bool, int | None]] = field(default_factory=list)
    # (context: mission·explain_gate, 문항 번호, 정답 여부, 확신도)


def record_attempt(conn: sqlite3.Connection, m: Mission, attempt: Attempt) -> int:
    """시도 한 번과 문항 응답을 남기고 attempt_id를 돌려준다. 실패는 진행 중일 때만 센다."""
    row = progress_row(conn, m.key)
    if row["first_check_at"] is None:
        conn.execute("UPDATE mission_progress SET first_check_at = ? WHERE mission_key = ?",
                     (attempt.at, m.key))
        event(conn, "first_check", m.key, attempt.at)
    if not attempt.passed and row["status"] == "in_progress":
        conn.execute("UPDATE mission_progress SET fails = fails + 1 WHERE mission_key = ?",
                     (m.key,))
    checks = [{"no": no, "ok": ok} for no, ok in enumerate(attempt.checks, 1)]
    cursor = conn.execute(
        "INSERT INTO attempts (mission_key, display_id, mode, at, outcome, check_results,"
        " engine_version, content_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (m.key, m.id, mode(conn), attempt.at, "pass" if attempt.passed else "fail",
         json.dumps(checks), *attempt.versions),
    )
    conn.executemany(
        "INSERT INTO responses (attempt_id, chapter, context, item_no, correct, confidence, at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(cursor.lastrowid, m.ch, context, no, int(ok), conf, attempt.at)
         for context, no, ok, conf in attempt.responses],
    )
    return cursor.lastrowid


def pass_mission(conn: sqlite3.Connection, m: Mission, xp: int, at: str) -> None:
    """최종 통과: 진행을 통과로 바꾸고, 카드를 1번 상자에 넣고(만기 다음 날), 이벤트를 남긴다."""
    if progress_row(conn, m.key)["solution_seen"]:
        how = "solution"
    else:
        how = "exam" if is_exam_target(conn, m.key) else "normal"
    conn.execute(
        "UPDATE mission_progress SET status = 'passed', how = ?, completed_at = ?, xp_awarded = ?"
        " WHERE mission_key = ?",
        (how, at, xp, m.key),
    )
    due = format_utc(parse_utc(at) + CARD_FIRST_DUE)
    conn.executemany(
        "INSERT OR IGNORE INTO cards (card_key, mission_key, kind, added_at, due_at)"
        " VALUES (?, ?, ?, ?, ?)",
        [(c.key, m.key, c.kind, at, due) for c in m.cards],
    )
    event(conn, "mission_passed", m.key, at, {"xp": xp})


def is_exam_target(conn: sqlite3.Connection, key: str) -> bool:
    """시험 모드이고 그 대상(보스)이 이 미션인지."""
    return mode(conn) == "exam" and mode_mission(conn) == key


def is_rebuild_target(conn: sqlite3.Connection, key: str) -> bool:
    """재구성 복습 중이고 그 대상이 이 미션인지."""
    return mode(conn) == "review" and mode_mission(conn) == key


def complete_chapter_if_done(conn: sqlite3.Connection, chapter_core: list[Mission],
                             at: str) -> bool:
    """장의 보스를 통과했고 코어 미션이 모두 통과·면제면 장을 끝낸다. 끝냈으면 True.

    보스를 ID로 먼저 통과해도 남은 코어 미션이 있으면 장은 끝나지 않는다(지연 확인 퀴즈 시계도).
    완료 방식은 보스를 시험으로 통과했으면 exam, 아니면 boss다.
    """
    status = statuses(conn)
    boss = next((m for m in chapter_core if m.kind == "boss"), None)
    if boss is None or any(status.get(m.key) not in DONE for m in chapter_core):
        return False
    # how로 정하면 시험 중 모범 답안을 본 보스(how=solution)가 boss로 잘못 남는다
    by_exam = conn.execute(
        "SELECT 1 FROM events WHERE kind = 'exam_passed' AND mission_key = ?", (boss.key,)
    ).fetchone()
    via = "exam" if by_exam else "boss"
    cursor = conn.execute(
        "UPDATE chapter_progress SET completed_at = ?, completed_via = ?"
        " WHERE chapter = ? AND completed_at IS NULL",
        (at, via, boss.ch),
    )
    return cursor.rowcount == 1


def open_hint(conn: sqlite3.Connection, m: Mission, at: str) -> int:
    """다음 단계 힌트를 연 것으로 기록하고 그 단계(1~3)를 돌려준다."""
    conn.execute(
        "UPDATE mission_progress SET hints_used = hints_used + 1 WHERE mission_key = ?", (m.key,)
    )
    level = progress_row(conn, m.key)["hints_used"]
    event(conn, "hint_opened", m.key, at, {"level": level})
    return level


def view_solution(conn: sqlite3.Connection, m: Mission, at: str) -> None:
    """모범 답안을 본 것으로 기록한다. 이렇게 통과한 미션은 재구성 복습에 먼저 나온다."""
    conn.execute("UPDATE mission_progress SET solution_seen = 1 WHERE mission_key = ?", (m.key,))
    event(conn, "solution_viewed", m.key, at)


def exempt_rest_of_chapter(conn: sqlite3.Connection, missions: tuple[Mission, ...], boss: Mission,
                           at: str) -> list[tuple[Mission, int]]:
    """시험으로 보스를 통과한 뒤: 그 장의 남은 코어 미션(장애 포함)을 면제하고 각각 50%를 준다.

    선택 미션은 면제하지 않는다(Spec "승급 시험"). (미션, 받은 XP) 목록을 돌려준다.
    """
    status = statuses(conn)
    rest = [m for m in chapter_core(missions, boss.ch)
            if m.key != boss.key and status.get(m.key) not in DONE]
    exempted = []
    for m in rest:
        xp = rewards.exam_skip_xp(m.xp)
        conn.execute(
            "INSERT INTO mission_progress (mission_key, display_id, chapter, status, how,"
            " completed_at, xp_awarded, est_min, ai_tag)"
            " VALUES (?, ?, ?, 'exempted', 'exam_skip', ?, ?, ?, ?)"
            " ON CONFLICT (mission_key) DO UPDATE SET status = 'exempted', how = 'exam_skip',"
            " completed_at = excluded.completed_at, xp_awarded = excluded.xp_awarded",
            (m.key, m.id, m.ch, at, xp, m.est_min, m.ai),
        )
        event(conn, "mission_exempted", m.key, at, {"xp": xp})
        exempted.append((m, xp))
    return exempted
