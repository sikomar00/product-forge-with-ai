"""IA-1 홈, IA-2 미션 보기, IA-3 채점."""

from quest.commands.common import FAIL, OK, USAGE, Game, line, make_ctx, target, versions
from quest.core import progress, rewards, state, ui
from quest.core.mission import CHECK_KINDS, Mission
from quest.kinds import ops

# 실패한 체크의 설명이 결함·원인 위치를 알려 주므로 숨긴다(IA 결정 4)
HIDE_FAILED_DETAIL = ("audit", "incident")


# ───────────── IA-1 홈 ─────────────


def cmd_home(game: Game, rest: list[str]) -> int:
    conn = game.conn
    status = progress.statuses(conn)
    m = progress.current(game.missions, status)
    if progress.active_incident(conn):
        print(ui.paint("🚨 진행 중인 장애가 있습니다. quest incident status", "red"))
    ch = m.ch if m else game.missions[-1].ch
    head = f"🔨 Product Forge · {progress.rank(ch)} · {progress.total_xp(conn)} XP"
    print(ui.paint(head, "bold"))
    done, total = progress.chapter_counts(game.missions, status, ch)
    print(f"{ch}장 {progress.CHAPTERS[ch]}  {ui.bar(done, total)}")
    print(f"오늘 복습할 카드: {progress.due_cards(conn)}장")
    if m is None:
        print("🎉 모든 코어 미션을 마쳤습니다.")
        return OK
    mode = ui.MODES[progress.mode(conn)]
    print(f"현재 미션: {line(m)}" + (f" [{mode}]" if mode else ""))
    started = status.get(m.key) == "in_progress"
    print(ui.paint(f"다음: quest {'check' if started else 'mission'}", "dim"))
    return OK


# ───────────── IA-2 미션 보기 ─────────────


def _where(m: Mission, cfg: dict) -> str:
    if m.requires_lab:
        return f"랩 VM ({cfg.get('lab', {}).get('vm_name', '?')})"
    if m.kind in CHECK_KINDS:
        return f"OpsDesk 리포 ({cfg.get('product', {}).get('repo_path', '?')})"
    return "이 터미널에서 답합니다"


def cmd_mission(game: Game, rest: list[str]) -> int:
    m, code = target(game, rest)
    if m is None:
        return code
    with state.transaction(game.conn):
        progress.start(game.conn, m, state.now_utc())
    track = "코어" if m.track == "core" else "➕선택"
    print(ui.paint(f"{line(m)} · {track} · {ui.SCAFFOLDS[m.scaffold]}", "bold"))
    print(f"\n📨 {m.frm}\n{m.msg}")
    for card in sorted(m.cards, key=lambda c: c.kind != "tool_map"):  # 도구 지도 카드 먼저
        print(f"\n{'🗺️' if card.kind == 'tool_map' else '🃏'} {card.front}\n   {card.back}")
    print(f"\n작업 위치: {_where(m, game.cfg)}")
    print(ui.paint("다음: quest check", "dim"))
    return OK


# ───────────── IA-3 채점 ─────────────


def _show_results(m: Mission, results: list, traps: list[str]) -> None:
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


def cmd_check(game: Game, rest: list[str]) -> int:
    m, code = target(game, rest)
    if m is None:
        return code
    if m.kind not in CHECK_KINDS:
        print(f"{ui.KIND_ICONS[m.kind]} 이 유형의 채점은 아직 준비 중입니다.")
        return USAGE
    results, traps = ops.grade(m, make_ctx(game.cfg))  # 체크는 읽기 전용이라 트랜잭션 밖에서 돌린다
    conn, at, xp = game.conn, state.now_utc(), None
    with state.transaction(conn):
        progress.start(conn, m, at)
        outcome = progress.record_attempt(conn, m, [r.ok for r in results], at, versions(conn))
        row = progress.progress_row(conn, m.key)
        if outcome == "pass" and row["status"] == "in_progress":
            xp = rewards.mission_xp(m.xp, row["hints_used"], row["fails"], row["solution_seen"])
            progress.pass_mission(conn, m, xp, at)
    _show_results(m, results, traps)
    if outcome == "fail":
        print(ui.paint("고친 뒤 다시 quest check. 막히면 quest hint", "dim"))
        return FAIL
    if xp is None:
        print("✅ 이미 끝낸 미션입니다. 보상은 다시 주지 않습니다.")
        return OK
    one_shot = row["fails"] == 0 and row["hints_used"] == 0 and not row["solution_seen"]
    print(ui.paint(f"🎉 통과! +{xp} XP" + (" (원샷 보너스)" if one_shot else ""), "green"))
    if m.cards:
        print(f"🃏 카드 {len(m.cards)}장이 복습 덱에 들어갔습니다.")
    nxt = progress.current(game.missions, progress.statuses(conn))
    print(f"다음 미션: {line(nxt)} → quest mission" if nxt else "🎉 모든 코어 미션을 마쳤습니다.")
    return OK

