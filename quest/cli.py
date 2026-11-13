"""quest 명령의 입구: 명령 해석, 도움말, 종료 코드(IA, Spec "화면과 종료 코드")."""

import sys
from collections.abc import Callable
from dataclasses import dataclass

from quest.commands.assist import cmd_hint, cmd_solution
from quest.commands.common import ENV, OK, USAGE, Game, open_game
from quest.commands.doctor import cmd_doctor
from quest.commands.grade import cmd_check
from quest.commands.modes import cmd_back, cmd_exam
from quest.commands.play import cmd_home, cmd_mission
from quest.commands.records import cmd_goals, cmd_map, cmd_stats
from quest.commands.report import cmd_report
from quest.commands.selftest import cmd_selftest
from quest.commands.study import cmd_review
from quest.commands.system import cmd_reset, cmd_status
from quest.commands.update import cmd_update
from quest.core import config, state, ui


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
        print(f"  {f'quest {name} {command.usage}'.strip():<28} {command.desc}")
    print()
    print("백업에서 되돌리기: 게임을 끈 상태에서 백업 파일을 상태 DB 자리에 복사합니다.")
    print(f"  백업 폴더: {config.home() / 'backups'}")
    print(f"  상태 DB:   {state.db_path()}")
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
    "map": Command(cmd_map, "[장]", "장 지도. 장 번호를 주면 그 장의 미션 목록", max_args=1),
    "goals": Command(cmd_goals, "", "졸업 기준 13개 영역의 충족 상태"),
    "stats": Command(cmd_stats, '[--sql "SELECT…"]', "기록: 시간·힌트·확신·복구, SQL", max_args=2),
    "status": Command(cmd_status, "--json", "기계가 읽는 현재 상태(AI 튜터용)", max_args=1),
    "reset": Command(cmd_reset, "", "진행 초기화(백업을 남긴다)"),
    "doctor": Command(cmd_doctor, "", "장비 점검: 도구 설치와 허용 버전", needs_game=False),
    "update": Command(cmd_update, "", "콘텐츠 받기·갱신", needs_game=False),
    "selftest": Command(cmd_selftest, "", "받은 콘텐츠의 테스트를 이 엔진으로", needs_game=False),
    "report": Command(cmd_report, "[ID]", "미션 오판 신고(콘텐츠 리포 이슈)", max_args=1),
    "help": Command(cmd_help, "", "명령 목록", needs_game=False),
}


def _utf8_console() -> None:
    if sys.platform == "win32":  # Windows 기본 코드 페이지로는 이모지·한글이 깨진다
        for stream in (sys.stdin, sys.stdout, sys.stderr):  # 파이프로 넣은 한글 답도 UTF-8로
            if hasattr(stream, "reconfigure"):  # 시험 중 pytest가 바꿔 끼운 stdin에는 없다
                stream.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    args = sys.argv[1:] if argv is None else argv
    name, rest = (args[0], args[1:]) if args else ("", [])
    command = COMMANDS.get(name)
    if command is None or len(rest) > command.max_args:
        cmd_help()
        return USAGE
    game = None
    try:
        if command.needs_game:
            game = open_game()
        return command.fn(game, rest)
    except config.EnvError as exc:
        print(ui.paint(f"❌ {exc}", "red"), file=sys.stderr)
        return ENV
    finally:
        if game is not None:
            game.conn.close()
