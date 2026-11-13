"""체크로 채점하는 유형(실습·감사·장애·보스)의 채점(Spec "채점" 1·3)."""

from quest.core.mission import Ctx, Mission, Result


def grade(m: Mission, ctx: Ctx) -> tuple[list[Result], list[str]]:
    """체크를 번호 순서대로 모두 돌리고, 실패하면 걸린 트랩의 메시지를 돌려준다."""
    results = [check.fn(ctx) for check in m.checks]
    if all(r.ok for r in results):
        return results, []
    return results, [trap.msg for trap in m.traps if trap.fn(ctx)]
