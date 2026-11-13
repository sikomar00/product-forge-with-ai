"""외부 프로그램(git·gh·도구 버전) 실행의 경계(rules/code.md "외부 호출은 경계 한 곳에").

core는 이 모듈을 모른다. commands·checks·chaos·labs가 쓴다.
"""

import re
import shutil
import subprocess
from pathlib import Path

from quest.core.config import EnvError

TIMEOUT_SEC = 60
_VERSION = re.compile(r"\d+(?:\.\d+)+")


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """명령을 실행하고 결과를 돌려준다. 프로그램이 없거나 시간이 넘으면 EnvError."""
    exe = shutil.which(args[0])
    if exe is None:
        raise EnvError(f"{args[0]} 명령을 찾지 못했습니다. quest doctor로 설치 여부를 확인하세요.")
    try:
        return subprocess.run(
            [exe, *args[1:]], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=TIMEOUT_SEC, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise EnvError(f"{args[0]} 명령이 {TIMEOUT_SEC}초 안에 끝나지 않았습니다.") from exc


def version_of(cmd: list[str]) -> str | None:
    """버전 출력에서 첫 번째 'N.N(.N…)'을 찾는다. 프로그램이 없으면 None."""
    if shutil.which(cmd[0]) is None:
        return None
    done = run(cmd)
    found = _VERSION.search(done.stdout + done.stderr)
    return found[0] if found else None
