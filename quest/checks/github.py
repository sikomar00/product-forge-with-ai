"""GitHub 체크. ctx.gh(호출기)로 REST API JSON을 읽는다(design.md 8.4절).

호출기는 셋이다: 실제 호출(GhLive, `gh api`), 기록 재생(GhReplay), 기록하며 호출(GhRecorder).
콘텐츠의 자동 플레이스루는 평소에 기록 재생으로 돈다(Spec "외부 서비스가 필요한 미션").
"""

import json
from collections.abc import Callable
from pathlib import Path

from quest import external
from quest.checks import MISSING, dig, verdict
from quest.core.config import EnvError
from quest.core.mission import CheckEnvError, Ctx, Result

Getter = Callable[[str], object]


class GhLive:
    """`gh api <경로>`로 GET만 한다.

    없는 리소스(404)는 MISSING, 인증·네트워크 문제는 CheckEnvError.
    """

    def __call__(self, path: str) -> object:
        try:
            done = external.run(["gh", "api", path])
        except EnvError as exc:
            raise CheckEnvError(str(exc)) from exc
        if done.returncode == 0:
            return json.loads(done.stdout) if done.stdout.strip() else None
        if "HTTP 404" in done.stderr:
            return MISSING
        raise CheckEnvError("GitHub API를 부르지 못했습니다. gh auth status·네트워크를 확인하세요.")


class GhReplay:
    """기록 파일({경로: JSON, 없던 리소스는 null 대신 {"__missing__": true}})에서 답한다."""

    def __init__(self, records: dict[str, object]) -> None:
        self.records = records

    @classmethod
    def load(cls, path: Path) -> GhReplay:
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def __call__(self, path: str) -> object:
        if path not in self.records:
            raise CheckEnvError(f"기록 재생에 없는 GitHub 요청입니다: {path}")
        value = self.records[path]
        return MISSING if value == {"__missing__": True} else value


class GhRecorder:
    """실제로 부르면서 답을 모은다. save()로 기록 파일을 쓴다(콘텐츠 리포 출시 점검용, T1-9)."""

    def __init__(self, live: Getter) -> None:
        self.live, self.records = live, {}

    def __call__(self, path: str) -> object:
        value = self.live(path)
        self.records[path] = {"__missing__": True} if value is MISSING else value
        return value

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8")


def _getter(ctx: Ctx) -> Getter:
    if ctx.gh is None:
        raise CheckEnvError("GitHub 호출기가 없습니다(엔진 설정 문제).")
    return ctx.gh


def value(ctx: Ctx, path: str, keys: tuple[str | int, ...] = ()) -> object:
    """API 경로의 JSON에서 keys 경로의 값. 리소스·키가 없으면 MISSING."""
    return dig(_getter(ctx)(path), keys)


def exists(ctx: Ctx, path: str) -> Result:
    found = _getter(ctx)(path) is not MISSING
    return verdict(found, "있음" if found else "없음")
