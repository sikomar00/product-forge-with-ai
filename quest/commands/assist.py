"""IA-4 힌트, IA-5 모범 답안."""

import sqlite3

from quest.commands.common import OK, Game, confirm, target
from quest.core import progress, rewards, spoiler, state, ui
from quest.core.mission import Mission

NOT_STARTED = {"status": "in_progress", "hints_used": 0, "fails": 0, "solution_seen": 0}


def _open_row(game: Game, rest: list[str]) -> tuple[Mission | None, dict | sqlite3.Row, int]:
    """(미션, 진행 행, 종료 코드). 아직 시작 전이면 빈 진행 값을 준다.

    시작 기록은 학습자가 확인한 뒤에 남긴다. 묻기만 하고 안 열었으면 시작한 것이 아니다.
    """
    m, code = target(game, rest)
    if m is None:
        return None, NOT_STARTED, code
    return m, progress.progress_row(game.conn, m.key) or NOT_STARTED, OK


def cmd_hint(game: Game, rest: list[str]) -> int:
    m, row, code = _open_row(game, rest)
    if m is None:
        return code
    if row["status"] != "in_progress":
        print("이미 끝낸 미션입니다. quest solution으로 모범 답안을 감점 없이 볼 수 있습니다.")
        return OK
    used = row["hints_used"]
    if used >= len(m.hints):
        print("힌트 3단계를 모두 봤습니다. 그래도 막히면 quest solution")
        return OK
    before = rewards.mission_xp(m.xp, used, row["fails"], row["solution_seen"])
    after = rewards.mission_xp(m.xp, used + 1, row["fails"], row["solution_seen"])
    question = f"💡 힌트 {used + 1}단계를 열면 보상이 {before} → {after} XP가 됩니다. 열까요?"
    if not confirm(question):
        print("열지 않았습니다.")
        return OK
    at = state.now_utc()
    with state.transaction(game.conn):
        progress.start(game.conn, m, at)
        level = progress.open_hint(game.conn, m, at)
    print(ui.paint(f"💡 힌트 {level}/{len(m.hints)}", "yellow"))
    print(spoiler.reveal(m.hints[level - 1]))
    if level == len(m.hints):
        print(ui.paint("그래도 막히면 quest solution", "dim"))
    return OK


def cmd_solution(game: Game, rest: list[str]) -> int:
    m, row, code = _open_row(game, rest)
    if m is None:
        return code
    if m.solution is None:
        print("이 미션에는 모범 답안이 없습니다.")
        return OK
    if row["status"] == "in_progress" and not row["solution_seen"]:
        before = rewards.mission_xp(m.xp, row["hints_used"], row["fails"], False)
        after = rewards.mission_xp(m.xp, row["hints_used"], row["fails"], True)
        question = (f"📖 모범 답안을 보면 보상이 {before} → {after} XP가 되고, "
                    "재구성 복습에 먼저 나옵니다. 볼까요?")
        if not confirm(question):
            print("보지 않았습니다.")
            return OK
        at = state.now_utc()
        with state.transaction(game.conn):
            progress.start(game.conn, m, at)
            progress.view_solution(game.conn, m, at)
    print(ui.paint("📖 모범 답안", "bold"))
    print(spoiler.reveal(m.solution))
    return OK

