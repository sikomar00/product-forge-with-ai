"""IA-4 힌트, IA-5 모범 답안."""

import sqlite3
from dataclasses import replace

from quest.commands.ask import confirm
from quest.commands.common import OK, USAGE, Game, target
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
    if progress.is_rebuild_target(game.conn, m.key):  # 답을 베껴 재구성 보상을 받지 못하게
        print("재구성 복습 중에는 힌트와 모범 답안을 볼 수 없습니다. 그만두려면 quest back")
        return None, NOT_STARTED, USAGE
    row = progress.progress_row(game.conn, m.key)
    # 면제된 미션을 다시 하려는 것이면 새로 시작하는 미션처럼 본다(시작하면 기록이 새로 세진다)
    return m, NOT_STARTED if row is None or row["status"] == "exempted" else row, OK


def _reward_note(game: Game, m: Mission, xp_change: tuple[int, int]) -> str:
    if progress.was_exempted(game.conn, m.key):
        return "면제됐던 미션을 다시 하는 중이라 보상은 바뀌지 않습니다"
    return f"보상이 {xp_change[0]} → {xp_change[1]} XP가 됩니다"


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
    now = rewards.Help.of(row)
    before = rewards.mission_xp(m.xp, now)
    after = rewards.mission_xp(m.xp, replace(now, hints=used + 1))
    question = f"💡 힌트 {used + 1}단계를 엽니다. {_reward_note(game, m, (before, after))}. 열까요?"
    if not confirm(question):
        print("열지 않았습니다.")
        return OK
    with state.transaction(game.conn) as tx:
        progress.start(tx, m)
        level = progress.open_hint(tx, m)
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
        now = rewards.Help.of(row)
        before = rewards.mission_xp(m.xp, now)
        after = rewards.mission_xp(m.xp, replace(now, solution_seen=True))
        question = (f"📖 모범 답안을 봅니다. {_reward_note(game, m, (before, after))}. "
                    "재구성 복습에 먼저 나옵니다. 볼까요?")
        if not confirm(question):
            print("보지 않았습니다.")
            return OK
        with state.transaction(game.conn) as tx:
            progress.start(tx, m)
            progress.view_solution(tx, m)
    print(ui.paint("📖 모범 답안", "bold"))
    print(spoiler.reveal(m.solution))
    return OK

