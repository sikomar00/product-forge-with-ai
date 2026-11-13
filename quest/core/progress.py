"""진행 규칙: 현재 미션, 미션 시작, 채점 기록, 통과(Spec "진행 규칙", "채점", ERD v1.0).

쓰기 함수는 트랜잭션을 열지 않는다. 명령 하나가 state.transaction() 안에서 부른다.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import timedelta

from quest.core import rewards
from quest.core.mission import Mission
from quest.core.state import Tx, format_utc, parse_utc

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
    """미션 키 → 상태. 면제됐던 미션을 다시 하는 중이면 통과 전까지 'exempted'로 본다.

    그래야 다시 하기가 현재 미션 흐름과 진행률을 가로채지 않고, 졸업 기준에도 아직 안 든다.
    """
    return dict(conn.execute(
        "SELECT mission_key, CASE WHEN status = 'in_progress' AND EXISTS (SELECT 1 FROM events e"
        " WHERE e.kind = 'mission_exempted' AND e.mission_key = mp.mission_key)"
        " THEN 'exempted' ELSE status END FROM mission_progress mp"
    ))


def was_exempted(conn: sqlite3.Connection, key: str) -> bool:
    """승급 시험으로 면제된 적이 있는 미션인지(다시 하기 판단용)."""
    return conn.execute(
        "SELECT 1 FROM events WHERE kind = 'mission_exempted' AND mission_key = ?", (key,)
    ).fetchone() is not None


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



def total_xp(conn: sqlite3.Connection) -> int:
    missions = conn.execute("SELECT coalesce(sum(xp_awarded), 0) FROM mission_progress")
    rebuilds = conn.execute(
        "SELECT coalesce(sum(json_extract(payload, '$.xp')), 0) FROM events"
        " WHERE kind = 'rebuild_passed'"  # ->>는 SQLite 3.38부터라 최소 버전 3.37에서 못 쓴다
    )
    return missions.fetchone()[0] + rebuilds.fetchone()[0]






def is_exam_target(conn: sqlite3.Connection, key: str) -> bool:
    """시험 모드이고 그 대상(보스)이 이 미션인지."""
    return mode(conn) == "exam" and mode_mission(conn) == key


def is_rebuild_target(conn: sqlite3.Connection, key: str) -> bool:
    """재구성 복습 중이고 그 대상이 이 미션인지."""
    return mode(conn) == "review" and mode_mission(conn) == key


# ───────────── 쓰기: 명령이 연 트랜잭션(Tx) 안에서 부른다 ─────────────


def event(  # noqa: PLR0913 - payload는 선택 값이라 필수 인자는 3개다
    tx: Tx, kind: str, mission_key: str | None, payload: dict | None = None
) -> None:
    tx.conn.execute(
        "INSERT INTO events (at, kind, mission_key, payload) VALUES (?, ?, ?, ?)",
        (tx.at, kind, mission_key, json.dumps(payload) if payload else None),
    )


def set_mode(tx: Tx, new_mode: str, mission_key: str | None) -> None:
    started = None if new_mode == "normal" else tx.at
    tx.conn.execute(
        "INSERT INTO game_state (id, mode, mode_mission_key, mode_started_at, updated_at)"
        " VALUES (1, ?, ?, ?, ?) ON CONFLICT (id) DO UPDATE SET mode = excluded.mode,"
        " mode_mission_key = excluded.mode_mission_key,"
        " mode_started_at = excluded.mode_started_at, updated_at = excluded.updated_at",
        (new_mode, mission_key, started, tx.at),
    )


def start(tx: Tx, m: Mission) -> bool:
    """미션을 처음 보여 줄 때 시작 기록을 만든다. 이미 시작했으면 False.

    면제된 미션을 학습자가 직접 다시 하면 보통 진행 중 미션으로 되돌린다. 시작 시각·실패·힌트·
    모범 답안을 새로 세고, 받은 보상(xp_awarded)만 그대로 둔다. 면제 이력은 이벤트에 남아 있다.
    """
    row = progress_row(tx.conn, m.key)
    if row is not None and row["status"] != "exempted":
        return False
    if row is not None:
        tx.conn.execute(
            "UPDATE mission_progress SET status = 'in_progress', how = NULL, completed_at = NULL,"
            " started_at = ?, first_check_at = NULL, fails = 0, hints_used = 0, solution_seen = 0"
            " WHERE mission_key = ?",
            (tx.at, m.key),
        )
        event(tx, "mission_started", m.key, {"redo": 1})
        return True
    tx.conn.execute(
        "INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at,"
        " est_min, ai_tag) VALUES (?, ?, ?, 'in_progress', ?, ?, ?)",
        (m.key, m.id, m.ch, tx.at, m.est_min, m.ai),
    )
    tx.conn.execute(
        "INSERT OR IGNORE INTO chapter_progress (chapter, started_at) VALUES (?, ?)", (m.ch, tx.at)
    )
    event(tx, "mission_started", m.key)
    return True


@dataclass(frozen=True)
class Attempt:
    """quest check 한 번의 결과. 내용(설명·정답)이 아니라 번호와 정오만 담는다."""

    checks: list[bool]  # 체크 번호 순서의 통과 여부. 문항형 미션은 빈 목록
    passed: bool
    versions: tuple[str, str]  # (엔진, 콘텐츠)
    responses: list[tuple[str, int, bool, int | None]] = field(default_factory=list)
    # (context: mission·explain_gate, 문항 번호, 정답 여부, 확신도)
    error: bool = False  # 체크가 끝나지 못함(환경 문제 등). 실패로 세지 않는다
    rca_correct: bool | None = None  # 장애 미션의 근본 원인 퀴즈를 맞혔는지(물었을 때만)


def _outcome(attempt: Attempt) -> str:
    if attempt.error:
        return "error"
    return "pass" if attempt.passed else "fail"


def record_attempt(tx: Tx, m: Mission, attempt: Attempt) -> int:
    """시도 한 번과 문항 응답을 남기고 attempt_id를 돌려준다. 실패는 진행 중일 때만 센다."""
    conn = tx.conn
    row = progress_row(conn, m.key)
    if row["first_check_at"] is None:
        conn.execute("UPDATE mission_progress SET first_check_at = ? WHERE mission_key = ?",
                     (tx.at, m.key))
        event(tx, "first_check", m.key)
    if not attempt.passed and not attempt.error and row["status"] == "in_progress":
        conn.execute("UPDATE mission_progress SET fails = fails + 1 WHERE mission_key = ?",
                     (m.key,))
    checks = [{"no": no, "ok": ok} for no, ok in enumerate(attempt.checks, 1)]
    cursor = conn.execute(
        "INSERT INTO attempts (mission_key, display_id, mode, at, outcome, check_results,"
        " engine_version, content_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (m.key, m.id, mode(conn), tx.at, _outcome(attempt),
         json.dumps(checks), *attempt.versions),
    )
    conn.executemany(
        "INSERT INTO responses (attempt_id, chapter, context, item_no, correct, confidence, at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(cursor.lastrowid, m.ch, context, no, int(ok), conf, tx.at)
         for context, no, ok, conf in attempt.responses],
    )
    return cursor.lastrowid


def pass_mission(tx: Tx, m: Mission, xp: int) -> None:
    """최종 통과: 진행을 통과로 바꾸고, 카드를 1번 상자에 넣고(만기 다음 날), 이벤트를 남긴다."""
    if progress_row(tx.conn, m.key)["solution_seen"]:
        how = "solution"
    else:
        how = "exam" if is_exam_target(tx.conn, m.key) else "normal"
    tx.conn.execute(
        "UPDATE mission_progress SET status = 'passed', how = ?, completed_at = ?, xp_awarded = ?"
        " WHERE mission_key = ?",
        (how, tx.at, xp, m.key),
    )
    due = format_utc(parse_utc(tx.at) + CARD_FIRST_DUE)
    tx.conn.executemany(
        "INSERT OR IGNORE INTO cards (card_key, mission_key, kind, added_at, due_at)"
        " VALUES (?, ?, ?, ?, ?)",
        [(c.key, m.key, c.kind, tx.at, due) for c in m.cards],
    )
    event(tx, "mission_passed", m.key, {"xp": xp})


def complete_chapter_if_done(tx: Tx, chapter_core: list[Mission]) -> bool:
    """장의 보스를 통과했고 코어 미션이 모두 통과·면제면 장을 끝낸다. 끝냈으면 True.

    보스를 ID로 먼저 통과해도 남은 코어 미션이 있으면 장은 끝나지 않는다(지연 확인 퀴즈 시계도).
    완료 방식은 보스를 시험으로 통과했으면 exam, 아니면 boss다.
    """
    status = statuses(tx.conn)
    boss = next((m for m in chapter_core if m.kind == "boss"), None)
    if boss is None or any(status.get(m.key) not in DONE for m in chapter_core):
        return False
    # how로 정하면 시험 중 모범 답안을 본 보스(how=solution)가 boss로 잘못 남는다
    by_exam = tx.conn.execute(
        "SELECT 1 FROM events WHERE kind = 'exam_passed' AND mission_key = ?", (boss.key,)
    ).fetchone()
    cursor = tx.conn.execute(
        "UPDATE chapter_progress SET completed_at = ?, completed_via = ?"
        " WHERE chapter = ? AND completed_at IS NULL",
        (tx.at, "exam" if by_exam else "boss", boss.ch),
    )
    return cursor.rowcount == 1


def open_hint(tx: Tx, m: Mission) -> int:
    """다음 단계 힌트를 연 것으로 기록하고 그 단계(1~3)를 돌려준다."""
    tx.conn.execute(
        "UPDATE mission_progress SET hints_used = hints_used + 1 WHERE mission_key = ?", (m.key,)
    )
    level = progress_row(tx.conn, m.key)["hints_used"]
    event(tx, "hint_opened", m.key, {"level": level})
    return level


def view_solution(tx: Tx, m: Mission) -> None:
    """모범 답안을 본 것으로 기록한다. 이렇게 통과한 미션은 재구성 복습에 먼저 나온다."""
    tx.conn.execute(
        "UPDATE mission_progress SET solution_seen = 1 WHERE mission_key = ?", (m.key,)
    )
    event(tx, "solution_viewed", m.key)


def exempt_rest_of_chapter(tx: Tx, missions: tuple[Mission, ...],
                           boss: Mission) -> list[tuple[Mission, int]]:
    """시험으로 보스를 통과한 뒤: 그 장의 남은 코어 미션(장애 포함)을 면제하고 각각 50%를 준다.

    선택 미션은 면제하지 않는다(Spec "승급 시험"). (미션, 받은 XP) 목록을 돌려준다.
    """
    status = statuses(tx.conn)
    rest = [m for m in chapter_core(missions, boss.ch)
            if m.key != boss.key and status.get(m.key) not in DONE]
    exempted = []
    for m in rest:
        xp = rewards.exam_skip_xp(m.xp)
        tx.conn.execute(
            "INSERT INTO mission_progress (mission_key, display_id, chapter, status, how,"
            " completed_at, xp_awarded, est_min, ai_tag)"
            " VALUES (?, ?, ?, 'exempted', 'exam_skip', ?, ?, ?, ?)"
            " ON CONFLICT (mission_key) DO UPDATE SET status = 'exempted', how = 'exam_skip',"
            " completed_at = excluded.completed_at, xp_awarded = excluded.xp_awarded",
            (m.key, m.id, m.ch, tx.at, xp, m.est_min, m.ai),
        )
        event(tx, "mission_exempted", m.key, {"xp": xp})
        exempted.append((m, xp))
    return exempted
