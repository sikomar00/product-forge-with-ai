"""가짜 1장: 감사·장애·보스 미션과 선택 미션."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # 같은 폴더의 _fake를 불러오려고

from _fake import HINTS, choice_item, file_exists, obf  # noqa: E402

from quest.checks import fs  # noqa: E402
from quest.core.mission import Chaos, Check, Ctx, Mission, Result, ReviewRule  # noqa: E402


def _conf_ok(ctx: Ctx) -> Result:
    return fs.contains(ctx, "service.conf", r"^mode=ok$")


def _break(ctx: Ctx) -> None:
    (ctx.workdir / "service.conf").write_text("mode=broken\n", encoding="utf-8")
    (ctx.workdir / "leftover.pid").write_text("1", encoding="utf-8")  # 띄운 프로세스 흉내


def _is_broken(ctx: Ctx) -> bool:
    return fs.contains(ctx, "service.conf", "broken").ok


def _stop_leftover(ctx: Ctx) -> None:
    """스냅샷 대상 밖에 남긴 것을 치운다. 복구·중단 어느 쪽에서 불러도, 여러 번 불러도 된다."""
    (ctx.workdir / "leftover.pid").unlink(missing_ok=True)

MISSIONS = (
    Mission(
        key="m_f0000011", id="1-1", ch=1, kind="audit", title="가짜 감사", frm="가짜 팀장",
        xp=15, ai="delegate", msg="결함을 고치세요", hints=HINTS, solution=obf("fixed.txt"),
        checks=(file_exists("fixed.txt"),), explain=(choice_item(1),),
        review=(ReviewRule("*.py", r"print\(", "디버그 print를 지우세요"),),
    ),
    Mission(
        key="m_f0000012", id="1-2", ch=1, kind="incident", title="가짜 장애", frm="가짜 팀장",
        xp=20, ai="solo", msg="복구하세요", hints=HINTS,
        checks=(Check(1, "service.conf가 정상", _conf_ok, "설정 파일을 보세요"),),
        chaos=Chaos(("service.conf",), _break, _is_broken, _stop_leftover),
        rca=(choice_item(1),),
    ),
    Mission(
        key="m_f0000013", id="1-3", ch=1, kind="ops", title="가짜 선택 실습", frm="가짜 팀장",
        xp=10, ai="solo", msg="선택 미션", hints=HINTS, track="elective",
        checks=(file_exists("extra.txt"),),
    ),
    Mission(
        key="m_f0000014", id="1-B", ch=1, kind="boss", title="가짜 보스", frm="가짜 팀장",
        xp=30, ai="solo", msg="모두 하세요", hints=HINTS, checks=(file_exists("boss.txt"),),
    ),
)
