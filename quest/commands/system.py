"""IA-15 기계용 상태, IA-17 초기화(M0-16, NF-06, Spec "quest status --json", "초기화와 백업")."""

import json
import sqlite3
from datetime import UTC, datetime

from quest.commands.ask import read
from quest.commands.common import OK, USAGE, Game, lock_state, mode_target
from quest.core import config, progress, state
from quest.core.mission import Mission

STATUS_SCHEMA = 1
RESET_PHRASE = "초기화"


# ───────────── IA-15 기계용 상태 ─────────────


def _remaining_checks(game: Game, m: Mission) -> list[int]:
    """마지막 시도에서 통과하지 못한 체크 번호. 아직 시도가 없으면 전부.

    시험·복습 모드면 그 모드를 시작한 뒤의 시도만 본다(재구성은 샌드박스를 새로 채점한다).
    """
    since = progress.mode_started(game.conn) if mode_target(game) is m else None
    row = game.conn.execute(
        "SELECT check_results FROM attempts WHERE mission_key = ? AND at >= ?"
        " ORDER BY attempt_id DESC LIMIT 1",
        (m.key, since or ""),
    ).fetchone()
    if row is None:
        return [c.no for c in m.checks]
    return [c["no"] for c in json.loads(row[0]) if not c["ok"]]


def _status(game: Game) -> dict:
    """AI 튜터가 읽는 값. 체크 설명·힌트·정답은 넣지 않는다(IA 결정 5)."""
    m = mode_target(game) or progress.current(game.missions, progress.statuses(game.conn))
    numbers = _remaining_checks(game, m) if m else []
    return {
        "schema": STATUS_SCHEMA,
        "mission": {"key": m.key, "id": m.id, "kind": m.kind, "ai": m.ai} if m else None,
        "mode": progress.mode(game.conn),
        "remaining_checks": {"numbers": numbers, "count": len(numbers)},
        "incident_active": progress.active_incident(game.conn),
        "review_lock": lock_state(game)[0],
    }


def cmd_status(game: Game, rest: list[str]) -> int:
    if rest != ["--json"]:
        print("사용법: quest status --json")
        return USAGE
    print(json.dumps(_status(game), ensure_ascii=False))
    return OK


# ───────────── IA-17 초기화 ─────────────


def cmd_reset(game: Game, rest: list[str]) -> int:
    print("진행 기록을 모두 지우고 처음부터 시작합니다. 지금 기록은 백업 파일로 남깁니다.")
    if read(f"계속하려면 '{RESET_PHRASE}'를 입력하세요: ") != RESET_PHRASE:
        print("초기화하지 않았습니다.")
        return OK
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = config.home() / "backups" / f"state-{stamp}.db"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(backup) as target:
        game.conn.backup(target)
    target.close()
    game.conn.close()  # Windows는 열린 파일을 지우지 못한다
    state.db_path().unlink()
    fresh = state.connect()
    with state.transaction(fresh):
        progress.event(fresh, "reset_backup", None, state.now_utc(), {"backup": backup.name})
    fresh.close()
    print(f"초기화했습니다. 백업: {backup}")
    print(f"되돌리려면 게임을 끈 상태에서 이 파일을 {state.db_path()}로 복사하세요.")
    return OK
