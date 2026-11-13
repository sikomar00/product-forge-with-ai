"""IA-3 채점: 체크형·문항형 미션, 설명 게이트, 보상(M0-07, M0-10, M0-11, Spec "채점")."""

from dataclasses import dataclass, field, replace

from quest.commands.ask import Answered, ask_items
from quest.commands.common import FAIL, OK, USAGE, Game, line, make_ctx, target, versions
from quest.core import progress, review, rewards, state, ui
from quest.core.mission import CHECK_KINDS, Ctx, Mission, Result
from quest.kinds import ops

# 실패한 체크의 설명이 결함·원인 위치를 알려 주므로 숨긴다(IA 결정 4)
HIDE_FAILED_DETAIL = ("audit", "incident")
GATE_AI = ("pair", "delegate")  # 🤝·🚀 미션은 통과하면 설명 게이트를 묻는다


def _show_results(m: Mission, results: list[Result], traps: list[str]) -> None:
    if m.kind in HIDE_FAILED_DETAIL:
        print(f"체크 {sum(r.ok for r in results)}/{len(results)} 통과")
        for check, r in zip(m.checks, results, strict=True):
            if not r.ok:
                print(f"   ↳ {check.hint}")
    else:
        for check, r in zip(m.checks, results, strict=True):
            mark = ui.paint("✅", "green") if r.ok else ui.paint("❌", "red")
            print(f"{mark} {check.no}. {check.desc}" + (f" — {r.detail}" if r.detail else ""))
            if not r.ok:
                print(f"   ↳ {check.hint}")
    for message in traps:
        print(ui.paint(f"💡 {message}", "yellow"))


def _responses(context: str, answered: list[Answered]) -> list[tuple[str, int, bool, int | None]]:
    return [(context, a.item.no, a.correct, a.confidence) for a in answered]


def _ctx_for(game: Game, m: Mission) -> Ctx:
    """재구성 복습 중이면 샌드박스를, 아니면 OpsDesk 리포를 채점한다."""
    ctx = make_ctx(game.cfg)
    if progress.is_rebuild_target(game.conn, m.key):
        return replace(ctx, workdir=review.sandbox_path(m.id, progress.mode_started(game.conn)))
    return ctx


def _grade(game: Game, m: Mission, done: bool) -> progress.Attempt | None:
    """채점해서 Attempt를 만든다. 문항 답을 끝까지 받지 못하면 None."""
    checks, responses = [], []
    if m.kind in CHECK_KINDS:
        results, traps = ops.grade(m, _ctx_for(game, m))  # 읽기 전용이라 트랜잭션 밖에서 돌린다
        _show_results(m, results, traps)
        checks = [r.ok for r in results]
        passed = all(checks)
    else:
        answered = ask_items(m.items)
        if answered is None:
            return None
        responses = _responses("mission", answered)
        passed = all(a.correct for a in answered)
    if passed and not done and m.ai in GATE_AI and m.explain:
        head = f"\n{ui.AI_TAGS[m.ai]} 설명 게이트: 만든 결과를 내가 설명할 수 있는지"
        print(ui.paint(head, "bold"))
        gate = ask_items(m.explain)
        if gate is None:
            return None
        responses += _responses("explain_gate", gate)
        passed = all(a.correct for a in gate)
        if not passed:
            print("설명 게이트에 틀린 문항이 있어 아직 통과가 아닙니다.")
    return progress.Attempt(checks, passed, state.now_utc(), versions(game.conn), responses)


def _finish_exam(game: Game, boss: Mission, at: str) -> list[tuple[Mission, int]]:
    """시험 모드에서 보스를 통과했다: 남은 코어 미션 면제, exam_passed, 일반 모드로."""
    exempted = progress.exempt_rest_of_chapter(game.conn, game.missions, boss, at)
    progress.event(game.conn, "exam_passed", boss.key, at, {"exempted": len(exempted)})
    progress.set_mode(game.conn, "normal", None, at)
    return exempted


@dataclass
class Saved:
    """한 번의 채점이 남긴 결과(화면 표시용)."""

    xp: int | None = None  # 새로 통과해서 받은 보상
    exempted: list[tuple[Mission, int]] = field(default_factory=list)  # 시험으로 면제한 미션
    rebuilt: int | None = None  # 재구성 복습 보상
    redone: bool = False  # 면제됐던 미션을 직접 통과(보상 없음, 졸업 기준 인정)


def _pass_new(game: Game, m: Mission, at: str, saved: Saved) -> None:
    conn = game.conn
    row = progress.progress_row(conn, m.key)
    if progress.was_exempted(conn, m.key):  # 다시 하기: 보상은 면제 때 받은 그대로(Spec)
        progress.pass_mission(conn, m, row["xp_awarded"], at)
        saved.redone = True
        return
    saved.xp = rewards.mission_xp(m.xp, row["hints_used"], row["fails"], row["solution_seen"])
    in_exam = progress.is_exam_target(conn, m.key)
    progress.pass_mission(conn, m, saved.xp, at)
    if in_exam:
        saved.exempted = _finish_exam(game, m, at)
    progress.complete_chapter_if_done(conn, progress.chapter_core(game.missions, m.ch), at)


def _save(game: Game, m: Mission, attempt: progress.Attempt) -> Saved:
    """시도를 한 트랜잭션으로 기록한다."""
    conn, saved = game.conn, Saved()
    rebuilding = progress.is_rebuild_target(conn, m.key)
    with state.transaction(conn):
        progress.start(conn, m, attempt.at)
        progress.record_attempt(conn, m, attempt)
        if attempt.passed and progress.progress_row(conn, m.key)["status"] == "in_progress":
            _pass_new(game, m, attempt.at, saved)
        if attempt.passed and rebuilding:
            saved.rebuilt = rewards.rebuild_xp(m.xp)
            progress.event(conn, "rebuild_passed", m.key, attempt.at, {"xp": saved.rebuilt})
            progress.set_mode(conn, "normal", None, attempt.at)
    return saved


def cmd_check(game: Game, rest: list[str]) -> int:
    m, code = target(game, rest)
    if m is None:
        return code
    row = progress.progress_row(game.conn, m.key)
    # 면제된 미션을 직접 다시 할 때는 설명 게이트도 다시 본다
    attempt = _grade(game, m, done=row is not None and row["status"] == "passed")
    if attempt is None:
        print("답을 끝까지 받지 못해 채점을 기록하지 않았습니다.")
        return USAGE
    saved = _save(game, m, attempt)
    if not attempt.passed:
        print(ui.paint("다시 quest check로 처음부터 다시 봅니다. 막히면 quest hint", "dim"))
        return FAIL
    if saved.rebuilt is not None:
        print(ui.paint(f"🔁 재구성 복습 통과! +{saved.rebuilt} XP", "green"))
        return OK
    if saved.redone:
        print(ui.paint("✅ 면제됐던 미션을 직접 통과했습니다. 졸업 기준에 인정됩니다.", "green"))
        return OK
    if saved.xp is None:
        print("✅ 이미 끝낸 미션입니다. 보상은 다시 주지 않습니다.")
        return OK
    xp, exempted = saved.xp, saved.exempted
    row = progress.progress_row(game.conn, m.key)
    one_shot = row["fails"] == 0 and row["hints_used"] == 0 and not row["solution_seen"]
    print(ui.paint(f"🎉 통과! +{xp} XP" + (" (원샷 보너스)" if one_shot else ""), "green"))
    if m.cards:
        print(f"🃏 카드 {len(m.cards)}장이 복습 덱에 들어갔습니다.")
    if exempted:
        total = sum(x for _, x in exempted)
        print(f"🏁 승급 시험 통과! 남은 미션 {len(exempted)}개를 면제하고 +{total} XP")
    nxt = progress.current(game.missions, progress.statuses(game.conn))
    print(f"다음 미션: {line(nxt)} → quest mission" if nxt else "🎉 모든 코어 미션을 마쳤습니다.")
    return OK
