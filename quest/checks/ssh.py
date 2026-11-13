"""랩 VM 체크. 맥 호스트에서 OrbStack 머신(ctx.lab) 안의 읽기 전용 명령을 실행한다.

판정 규칙은 shell과 같다(종료 코드, 형식을 지정한 출력의 완전 일치, JSON).

shortcut: 'orb -m <머신> <명령>' 형식은 맥에서 아직 확인하지 못했다(Plan T1-4 미확인 3건).
T1-4에서 확인하고 다르면 _command만 고친다.
"""

from quest import external
from quest.checks.shell import Output, check_read_only, judge, parse_json
from quest.core.config import EnvError
from quest.core.mission import CheckEnvError, Ctx, Result


def _command(ctx: Ctx, args: list[str]) -> list[str]:
    return ["orb", "-m", ctx.lab, *args]


def run(ctx: Ctx, args: list[str]) -> Output:
    check_read_only(args)
    try:
        done = external.run(_command(ctx, args))
    except EnvError as exc:
        raise CheckEnvError(f"랩 VM에 접속하지 못했습니다: {exc}") from exc
    return Output(done.returncode, done.stdout)


def succeeds(ctx: Ctx, args: list[str]) -> Result:
    return judge(run(ctx, args), None)


def output_equals(ctx: Ctx, args: list[str], expected: str) -> Result:
    return judge(run(ctx, args), expected)


def json_value(ctx: Ctx, args: list[str], keys: tuple[str | int, ...] = ()) -> object:
    return parse_json(run(ctx, args), keys)
