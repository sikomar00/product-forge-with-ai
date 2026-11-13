"""셸 체크(subprocess). 상태를 바꾸지 않는 명령만 실행한다(Spec "체크 프리미티브").

허용 목록 밖의 명령은 콘텐츠 작성 오류라 ValueError다(그 시도는 error로 남는다).
판정은 종료 코드, 형식을 지정한 출력의 완전 일치, JSON 출력으로 한다(화면 문자열 매칭 금지).
"""

import json
from dataclasses import dataclass

from quest import external
from quest.checks import MISSING, dig, verdict
from quest.core.config import EnvError
from quest.core.mission import CheckEnvError, Ctx, Result

# 읽기만 하는 명령(앞부분이 맞으면 허용). find는 -delete·-exec가 있어 넣지 않는다.
READ_ONLY = (
    ("cat",), ("head",), ("tail",), ("ls",), ("stat",), ("wc",), ("grep",), ("which",),
    ("uname",), ("id",), ("whoami",), ("groups",), ("ps",), ("df",), ("du",), ("printenv",),
    ("file",), ("readlink",), ("realpath",), ("pwd",), ("test",), ("getent",), ("ss",),
    ("ip", "-j", "addr", "show"), ("ip", "-j", "route", "show"), ("lsblk", "-J"),
    ("findmnt", "-J"), ("systemctl", "is-active"), ("systemctl", "is-enabled"),
    ("systemctl", "is-failed"), ("systemctl", "show"), ("journalctl",), ("crontab", "-l"),
    ("sudo", "-l"),
)
# 허용한 명령이라도 이 인자로 시작하면 상태를 바꾼다
FORBIDDEN_ARGS = {
    "journalctl": ("--vacuum", "--rotate", "--flush", "--sync", "--relinquish",
                   "--smart-relinquish", "--setup-keys", "--update-catalog"),
    "ss": ("-K", "--kill"),
}
# 인자에 따라 바꾸는 명령이 되는 것: 허용하는 인자만 받는다
ARG_RULES = {
    "date": lambda rest: all(a.startswith("+") or a in ("-u", "--utc") for a in rest),
    "hostname": lambda rest: all(a in ("-f", "-s", "-d", "-i", "-I", "--fqdn") for a in rest),
}
VERSION_FLAGS = ("--version", "-V", "version")


@dataclass(frozen=True)
class Output:
    code: int
    stdout: str


def is_read_only(args: list[str]) -> bool:
    if len(args) == 2 and args[1] in VERSION_FLAGS:
        return True
    if args[0] in ARG_RULES:
        return ARG_RULES[args[0]](args[1:])
    forbidden = FORBIDDEN_ARGS.get(args[0], ())
    if any(a.startswith(f) for a in args[1:] for f in forbidden):
        return False
    return any(tuple(args[: len(prefix)]) == prefix for prefix in READ_ONLY)


def check_read_only(args: list[str]) -> None:
    if not is_read_only(args):
        raise ValueError(f"체크는 읽기 전용 명령만 실행합니다: {' '.join(args[:3])}")


def run(ctx: Ctx, args: list[str]) -> Output:
    """작업 폴더에서 읽기 전용 명령을 실행한다. 폴더·프로그램이 없으면 CheckEnvError."""
    check_read_only(args)
    if not ctx.workdir.is_dir():  # 다른 폴더에서 돌아 엉뚱하게 통과하지 않게
        raise CheckEnvError(f"작업 폴더가 없습니다: {ctx.workdir}. 설정의 repo_path를 확인하세요.")
    try:
        done = external.run(args, cwd=ctx.workdir)
    except EnvError as exc:
        raise CheckEnvError(str(exc)) from exc
    return Output(done.returncode, done.stdout)


def judge(output: Output, expected: str | None) -> Result:
    """종료 코드 0이고, expected가 있으면 표준 출력(앞뒤 공백 제외)이 정확히 같아야 통과."""
    if output.code != 0:
        return verdict(False, f"종료 코드 {output.code}")
    return verdict(expected is None or output.stdout.strip() == expected)


def parse_json(output: Output, keys: tuple[str | int, ...]) -> object:
    if output.code != 0:
        return MISSING
    try:
        return dig(json.loads(output.stdout), keys)
    except ValueError:
        return MISSING


def succeeds(ctx: Ctx, args: list[str]) -> Result:
    return judge(run(ctx, args), None)


def output_equals(ctx: Ctx, args: list[str], expected: str) -> Result:
    """형식을 지정한 출력(예: stat -c %a, date +%Y)이 expected와 같은지."""
    return judge(run(ctx, args), expected)


def json_value(ctx: Ctx, args: list[str], keys: tuple[str | int, ...] = ()) -> object:
    """JSON을 내는 명령(ip -j, lsblk -J 등)의 출력에서 keys 경로의 값. 없으면 MISSING."""
    return parse_json(run(ctx, args), keys)
