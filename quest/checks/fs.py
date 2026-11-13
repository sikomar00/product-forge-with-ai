"""파일 체크(pathlib). 경로는 ctx.workdir 기준이고, ~는 홈으로 바꾼다."""

import json
import os
import re
from pathlib import Path

from quest.checks import MISSING, dig, fail, verdict
from quest.core.mission import Ctx, Result


def resolve(ctx: Ctx, path: str) -> Path:
    candidate = Path(path).expanduser()
    return candidate if candidate.is_absolute() else ctx.workdir / candidate


def exists(ctx: Ctx, path: str) -> Result:
    found = resolve(ctx, path).exists()
    return verdict(found, f"{path} {'있음' if found else '없음'}")


def is_dir(ctx: Ctx, path: str) -> Result:
    return verdict(resolve(ctx, path).is_dir(), f"{path} 폴더")


def contains(ctx: Ctx, path: str, pattern: str) -> Result:
    """파일 내용에서 정규식을 찾는다(여러 줄 모드)."""
    target = resolve(ctx, path)
    if not target.is_file():
        return fail(f"{path} 없음")
    text = target.read_text(encoding="utf-8", errors="replace")
    return verdict(re.search(pattern, text, re.MULTILINE) is not None, f"{path} 내용")


def is_executable(ctx: Ctx, path: str) -> Result:
    target = resolve(ctx, path)
    return verdict(target.is_file() and os.access(target, os.X_OK), f"{path} 실행 권한")


def json_value(ctx: Ctx, path: str, keys: tuple[str | int, ...]) -> object:
    """JSON 파일에서 keys 경로의 값. 파일·키가 없으면 MISSING. 비교는 콘텐츠가 verdict로 한다."""
    try:
        value = json.loads(resolve(ctx, path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return MISSING
    return dig(value, keys)


def count(ctx: Ctx, folder: str, glob: str) -> int:
    """폴더에서 glob에 맞는 파일 수(비교는 콘텐츠가 한다). 폴더가 없으면 0."""
    base = resolve(ctx, folder)
    return sum(1 for p in base.glob(glob) if p.is_file()) if base.is_dir() else 0
