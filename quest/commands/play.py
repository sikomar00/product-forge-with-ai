"""IA-1 홈, IA-2 미션 보기."""

from datetime import datetime

from quest.commands.common import OK, Game, line, target
from quest.core import progress, review, state, ui
from quest.core.mission import CHECK_KINDS, Mission

# ───────────── IA-1 홈 ─────────────


def cmd_home(game: Game, rest: list[str]) -> int:
    conn = game.conn
    status = progress.statuses(conn)
    m = progress.current(game.missions, status)
    if progress.active_incident(conn):
        print(ui.paint("🚨 진행 중인 장애가 있습니다. quest incident status", "red"))
    ch = m.ch if m else game.missions[-1].ch
    threshold = review.lock_threshold(game.cfg)
    if review.locked(conn, threshold):
        print(ui.paint(f"🔒 복습 잠금: 만기 카드 {progress.due_cards(conn)}장. "
                       f"quest review로 {threshold}장 아래로 줄이면 풀립니다.", "yellow"))
    today = datetime.now(state.KST).date()
    head = (f"🔨 Product Forge · {progress.rank(ch)} · {progress.total_xp(conn)} XP"
            f" · 연속 복습 {review.streak(conn, today)}일")
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
