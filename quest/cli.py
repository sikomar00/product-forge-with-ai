"""quest 명령의 입구: 명령 해석, 도움말, 종료 코드(IA, Spec "화면과 종료 코드")."""

import sys
from collections.abc import Callable
from dataclasses import dataclass

from quest.commands.assist import cmd_hint, cmd_solution
from quest.commands.common import ENV, OK, USAGE, Game, open_game
from quest.commands.grade import cmd_check
from quest.commands.modes import cmd_back, cmd_exam
from quest.commands.play import cmd_home, cmd_mission
from quest.commands.study import cmd_review
from quest.core import config, ui


@dataclass(frozen=True)
class Command:
    fn: Callable[[Game | None, list[str]], int]
    usage: str
    desc: str
    max_args: int = 0
    needs_game: bool = True


# ───────────── IA-16 도움말 ─────────────


def cmd_help(game: Game | None = None, rest: list[str] | None = None) -> int:
    print("quest — Product Forge With AI\n")
    for name, command in COMMANDS.items():
        print(f"  {f'quest {name} {command.usage}'.strip():<22} {command.desc}")
    return OK


COMMANDS = {
    "": Command(cmd_home, "", "홈: 등급·XP·진행·현재 미션"),
    "mission": Command(cmd_mission, "[ID]", "미션 보기. ID를 빼면 현재 미션", max_args=1),
    "check": Command(cmd_check, "[ID]", "채점", max_args=1),
    "hint": Command(cmd_hint, "[ID]", "다음 단계 힌트(감점)", max_args=1),
    "solution": Command(cmd_solution, "[ID]", "모범 답안(보상 20%만)", max_args=1),
    "review": Command(cmd_review, "", "복습: 만기 카드(최대 15장)"),
    "exam": Command(cmd_exam, "", "승급 시험: 현재 장 보스에 먼저 도전"),
    "back": Command(cmd_back, "", "시험·복습 모드를 끝내고 돌아가기"),
    "help": Command(cmd_help, "", "명령 목록", needs_game=False),
}


def _utf8_console() -> None:
    if sys.platform == "win32":  # Windows 기본 코드 페이지로는 이모지·한글이 깨진다
        for stream in (sys.stdout, sys.stderr):
            stream.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    args = sys.argv[1:] if argv is None else argv
    name, rest = (args[0], args[1:]) if args else ("", [])
    command = COMMANDS.get(name)
    if command is None or len(rest) > command.max_args:
        cmd_help()
        return USAGE
    if not command.needs_game:
        return command.fn(None, rest)
    game = None
    try:
        game = open_game()
        return command.fn(game, rest)
    except config.EnvError as exc:
        print(ui.paint(f"❌ {exc}", "red"), file=sys.stderr)
        return ENV
    finally:
        if game is not None:
            game.conn.close()
