"""IA-3 채점: 체크형·문항형 미션, 설명 게이트, 보상(M0-07, M0-10, M0-11, Spec "채점")."""

import shutil
from dataclasses import dataclass, field, replace

from quest.commands.ask import Answered, ask_items
from quest.commands.common import ENV, FAIL, OK, USAGE, Game, line, make_ctx, target, versions
from quest.commands.incident import snapshot_folder
from quest.core import badges, progress, review, rewards, state, ui
from quest.core.config import EnvError
from quest.core.mission import CHECK_KINDS, CheckEnvError, Ctx, Mission, Result
from quest.kinds import ops
from quest.labs import reviewbot

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


def _show_error(exc: Exception) -> None:
    # 콘텐츠 예외의 메시지에는 체크가 보는 경로 같은 힌트가 들어 있을 수 있어 종류만 보인다
    reason = str(exc) if isinstance(exc, CheckEnvError) else type(exc).__name__
    print(ui.paint(f"⚠️ 채점을 끝내지 못했습니다: {reason}", "yellow"))
    print("실패로 세지 않습니다. 도구·파일·네트워크를 확인하고 다시 quest check."
          " 계속되면 quest report로 알려 주세요.")


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
        try:
            results, traps = ops.grade(m, _ctx_for(game, m))  # 읽기 전용이라 트랜잭션 밖에서
        except Exception as exc:  # 콘텐츠 체크가 끝나지 못함: 실패가 아니라 error(Spec 채점 1)
            _show_error(exc)
            return progress.Attempt([], False, versions(game.conn), error=True)
        _show_results(m, results, traps)
        checks = [r.ok for r in results]
        passed = all(checks)
    else:
        answered = ask_items(m.items)
        if answered is None:
            return None
        responses = _responses("mission", answered)
        passed = all(a.correct for a in answered)
    rca_correct = None
    for head, items, context, is_rca in _gates(m) if passed and not done else ():
        print(ui.paint(f"\n{head}", "bold"))
        answered = ask_items(items)
        if answered is None:
            return None
        responses += _responses(context, answered)
        passed = all(a.correct for a in answered)
        if is_rca:
            rca_correct = passed
        if not passed:
            print("틀린 문항이 있어 아직 통과가 아닙니다.")
            break
    return progress.Attempt(checks, passed, versions(game.conn), responses,
                            rca_correct=rca_correct)


def _gates(m: Mission) -> list[tuple[str, tuple, str, bool]]:
    """체크를 통과한 뒤 묻는 것: 장애의 근본 원인 퀴즈, 🤝·🚀의 설명 게이트.

    (제목, 문항, 응답 기록 맥락, 근본 원인 퀴즈인지) 목록이다.
    """
    gates = []
    if m.kind == "incident" and m.rca:
        gates.append(("🔎 근본 원인: 무엇이 왜 망가졌는지", m.rca, "mission", True))
    if m.ai in GATE_AI and m.explain:
        gates.append((f"{ui.AI_TAGS[m.ai]} 설명 게이트: 만든 결과를 내가 설명할 수 있는지",
                      m.explain, "explain_gate", False))
    return gates


def _finish_exam(tx: state.Tx, game: Game, boss: Mission) -> list[tuple[Mission, int]]:
    """시험 모드에서 보스를 통과했다: 남은 코어 미션 면제, exam_passed, 일반 모드로."""
    exempted = progress.exempt_rest_of_chapter(tx, game.missions, boss)
    progress.event(tx, "exam_passed", boss.key, {"exempted": len(exempted)})
    progress.set_mode(tx, "normal", None)
    return exempted


@dataclass
class Saved:
    """한 번의 채점이 남긴 결과(화면 표시용)."""

    xp: int | None = None  # 새로 통과해서 받은 보상
    exempted: list[tuple[Mission, int]] = field(default_factory=list)  # 시험으로 면제한 미션
    rebuilt: int | None = None  # 재구성 복습 보상
    redone: bool = False  # 면제됐던 미션을 직접 통과(보상 없음, 졸업 기준 인정)
    badges: list[str] = field(default_factory=list)  # 이번에 새로 얻은 배지 키
    recovered_ref: str | None = None  # 이번에 복구한 장애의 스냅샷(지운다)


def _pass_new(tx: state.Tx, game: Game, m: Mission) -> Saved:
    row = progress.progress_row(tx.conn, m.key)
    if progress.was_exempted(tx.conn, m.key):  # 다시 하기: 보상은 면제 때 받은 그대로(Spec)
        progress.pass_mission(tx, m, row["xp_awarded"])
        return Saved(redone=True)
    saved = Saved(xp=rewards.mission_xp(m.xp, rewards.Help.of(row)))
    in_exam = progress.is_exam_target(tx.conn, m.key)
    progress.pass_mission(tx, m, saved.xp)
    if in_exam:
        saved.exempted = _finish_exam(tx, game, m)
    progress.complete_chapter_if_done(tx, progress.chapter_core(game.missions, m.ch))
    return saved


def _save(game: Game, m: Mission, attempt: progress.Attempt) -> Saved:
    """시도를 한 트랜잭션으로 기록한다."""
    saved = Saved()
    rebuilding = progress.is_rebuild_target(game.conn, m.key)
    incident = progress.incident_row(game.conn)
    # 복구 체크를 모두 통과하면 복구다. 근본 원인 퀴즈는 따로 센다.
    recovered = (incident is not None and incident["mission_key"] == m.key
                 and bool(attempt.checks) and all(attempt.checks))
    with state.transaction(game.conn) as tx:
        progress.start(tx, m)
        progress.record_attempt(tx, m, attempt)
        if recovered:
            progress.close_incident(tx, incident, "recovered")
            saved.recovered_ref = incident["snapshot_ref"]
        if attempt.rca_correct is not None:
            progress.record_rca(tx, m.key, attempt.rca_correct)
        if attempt.passed and progress.progress_row(tx.conn, m.key)["status"] == "in_progress":
            saved = replace(_pass_new(tx, game, m), recovered_ref=saved.recovered_ref)
            saved.badges = badges.award(tx, m)
        if attempt.passed and rebuilding:
            saved.rebuilt = rewards.rebuild_xp(m.xp)
            progress.event(tx, "rebuild_passed", m.key, {"xp": saved.rebuilt})
            progress.set_mode(tx, "normal", None)
    return saved


def _run_reviewbot(game: Game, m: Mission) -> None:
    """채점 직전에 리뷰봇을 한 번 돌린다. 리뷰봇이 실패해도 채점은 한다."""
    try:
        message = reviewbot.run_once(make_ctx(game.cfg).workdir, m.review)
    except EnvError as exc:
        print(ui.paint(f"⚠️ 리뷰봇을 돌리지 못했습니다: {exc}", "yellow"))
        return
    if message:
        print(ui.paint(message, "bold"))


def cmd_check(game: Game, rest: list[str]) -> int:
    m, code = target(game, rest)
    if m is None:
        return code
    row = progress.progress_row(game.conn, m.key)
    if m.kind == "incident" and not progress.incident_started(game.conn, m.key):
        print("장애가 아직 시작되지 않았습니다. quest mission으로 장애를 시작하세요.")
        return USAGE
    if m.review and (row is None or row["status"] != "passed"):
        _run_reviewbot(game, m)
    # 면제된 미션을 직접 다시 할 때는 설명 게이트도 다시 본다
    attempt = _grade(game, m, done=row is not None and row["status"] == "passed")
    if attempt is None:
        print("답을 끝까지 받지 못해 채점을 기록하지 않았습니다.")
        return USAGE
    saved = _save(game, m, attempt)
    if saved.recovered_ref:
        shutil.rmtree(snapshot_folder(saved.recovered_ref), ignore_errors=True)
        print(ui.paint("✅ 장애를 복구했습니다.", "green"))
    if attempt.error:
        return ENV
    if not attempt.passed:
        print(ui.paint("다시 quest check로 처음부터 다시 봅니다. 막히면 quest hint", "dim"))
        return FAIL
    _show_pass(game, m, saved)
    return OK


def _show_pass(game: Game, m: Mission, saved: Saved) -> None:
    """통과 화면: 재구성 보상, 배지, 다시 하기, 보상·카드·시험 면제, 다음 미션."""
    if saved.rebuilt is not None:
        print(ui.paint(f"🔁 재구성 복습 통과! +{saved.rebuilt} XP", "green"))
        return
    for key in saved.badges:
        print(ui.paint(f"🏅 배지 획득: {badges.name(key)}", "yellow"))
    if saved.redone:
        print(ui.paint("✅ 면제됐던 미션을 직접 통과했습니다. 졸업 기준에 인정됩니다.", "green"))
        return
    if saved.xp is None:
        print("✅ 이미 끝낸 미션입니다. 보상은 다시 주지 않습니다.")
        return
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
