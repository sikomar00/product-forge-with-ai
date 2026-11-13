"""git 체크. porcelain·format 출력만 읽고, 인덱스도 건드리지 않는다(--no-optional-locks)."""

import re

from quest import external
from quest.checks import verdict
from quest.checks.shell import Output
from quest.core.config import EnvError
from quest.core.mission import CheckEnvError, Ctx, Result


def _git(ctx: Ctx, args: list[str]) -> Output:
    try:
        done = external.run(["git", "--no-optional-locks", "-C", str(ctx.workdir), *args])
    except EnvError as exc:
        raise CheckEnvError(str(exc)) from exc
    return Output(done.returncode, done.stdout.strip())  # porcelain·format 출력


def _lines(ctx: Ctx, args: list[str]) -> list[str]:
    out = _git(ctx, args)
    return out.stdout.splitlines() if out.code == 0 and out.stdout else []


def is_repo(ctx: Ctx) -> Result:
    found = _git(ctx, ["rev-parse", "--is-inside-work-tree"]).stdout == "true"
    return verdict(found, "git 리포" if found else "git 리포가 아님")


def branch(ctx: Ctx) -> str | None:
    """지금 브랜치 이름. 커밋이 없어도 이름은 있다. 리포가 아니거나 분리된 HEAD면 None."""
    out = _git(ctx, ["symbolic-ref", "--short", "-q", "HEAD"])
    return out.stdout if out.code == 0 else None


def branches(ctx: Ctx) -> list[str]:
    return _lines(ctx, ["for-each-ref", "--format=%(refname:short)", "refs/heads"])


def is_clean(ctx: Ctx) -> Result:
    out = _git(ctx, ["status", "--porcelain=v1"])
    return verdict(out.code == 0 and out.stdout == "", "작업 트리 깨끗함")


def subjects(ctx: Ctx) -> list[str]:
    """HEAD에서 닿는 커밋 제목, 최신순. 커밋이 없으면 빈 목록."""
    return _lines(ctx, ["log", "--format=%s"])


def has_commit(ctx: Ctx, pattern: str) -> Result:
    return verdict(any(re.search(pattern, s) for s in subjects(ctx)), "커밋 제목")


def is_tracked(ctx: Ctx, path: str) -> Result:
    found = _git(ctx, ["ls-files", "--error-unmatch", "--", path]).code == 0
    return verdict(found, f"{path} {'추적됨' if found else '추적 안 됨'}")


def is_ignored(ctx: Ctx, path: str) -> Result:
    found = _git(ctx, ["check-ignore", "-q", "--", path]).code == 0
    return verdict(found, f"{path} {'무시됨' if found else '무시 안 됨'}")


def remote_url(ctx: Ctx, name: str = "origin") -> str | None:
    out = _git(ctx, ["remote", "get-url", name])
    return out.stdout if out.code == 0 else None
