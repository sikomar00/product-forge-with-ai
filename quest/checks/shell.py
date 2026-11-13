"""셸 체크(subprocess). 상태를 바꾸지 않는 명령만 실행한다(Spec "체크 프리미티브").

허용 목록 밖의 명령은 콘텐츠 작성 오류라 ValueError다(그 시도는 error로 남는다).
"""

import re
from dataclasses import dataclass

from quest import external
from quest.checks import verdict
from quest.core.config import EnvError
from quest.core.mission import CheckEnvError, Ctx, Result

# 읽기만 하는 명령(앞부분이 맞으면 허용). find는 -delete·-exec가 있어 넣지 않는다.
READ_ONLY = (
    ("cat",), ("head",), ("tail",), ("ls",), ("stat",), ("wc",), ("grep",), ("which",),
    ("uname",), ("id",), ("whoami",), ("groups",), ("ps",), ("df",), ("du",), ("date",),
    ("hostname",), ("printenv",), ("file",), ("readlink",), ("realpath",), ("pwd",),
    ("test",), ("getent",), ("ss",), ("ip", "addr"), ("ip", "route"),
    ("systemctl", "is-active"), ("systemctl", "is-enabled"), ("systemctl", "status"),
    ("systemctl", "show"), ("journalctl",), ("crontab", "-l"), ("sudo", "-l"),
)
VERSION_FLAGS = ("--version", "-V", "version")


@dataclass(frozen=True)
class Output:
    code: int
    text: str  # 표준 출력과 표준 오류를 합친 것


def check_read_only(args: list[str]) -> None:
    if len(args) == 2 and args[1] in VERSION_FLAGS:
        return
    if any(tuple(args[: len(prefix)]) == prefix for prefix in READ_ONLY):
        return
    raise ValueError(f"체크는 읽기 전용 명령만 실행합니다: {' '.join(args[:2])}")


def run(ctx: Ctx, args: list[str]) -> Output:
    """작업 폴더에서 읽기 전용 명령을 실행한다. 프로그램이 없으면 CheckEnvError."""
    check_read_only(args)
    try:
        done = external.run(args, cwd=ctx.workdir if ctx.workdir.is_dir() else None)
    except EnvError as exc:
        raise CheckEnvError(str(exc)) from exc
    return Output(done.returncode, done.stdout + done.stderr)


def judge(output: Output, pattern: str | None) -> Result:
    """종료 코드 0이고, pattern이 있으면 출력에서 찾아져야 통과."""
    if output.code != 0:
        return verdict(False, f"종료 코드 {output.code}")
    return verdict(pattern is None or re.search(pattern, output.text, re.MULTILINE) is not None)


def succeeds(ctx: Ctx, args: list[str]) -> Result:
    return judge(run(ctx, args), None)


def output_matches(ctx: Ctx, args: list[str], pattern: str) -> Result:
    return judge(run(ctx, args), pattern)
