"""IA-7 승급 시험, IA-8 돌아가기(M0-14, Spec "승급 시험")."""

from quest.commands.common import OK, USAGE, Game, line, lock_state
from quest.core import progress, state, ui

NO_EXAM_CHAPTERS = (0, 17)  # 0장은 환경을 만들고, 17장은 처음부터 끝까지 해 보는 것이 목적이다


def _exam_refusal(game: Game, boss_status: str | None) -> str | None:
    if boss_status in progress.DONE:
        return "이 장의 보스는 이미 통과했습니다."
    if lock_state(game)[0]:
        return "🔒 복습 잠금 중에는 시험을 시작하지 않습니다. 먼저 quest review"
    return None


def cmd_exam(game: Game, rest: list[str]) -> int:
    conn = game.conn
    if progress.mode(conn) != "normal":
        print(f"이미 {ui.MODES[progress.mode(conn)]}입니다. quest back으로 먼저 나오세요.")
        return USAGE
    status = progress.statuses(conn)
    current = progress.current(game.missions, status)
    if current is None:
        print("🎉 모든 코어 미션을 마쳤습니다.")
        return USAGE
    if current.ch in NO_EXAM_CHAPTERS:
        print(f"{current.ch}장에는 승급 시험이 없습니다.")
        return USAGE
    boss = next((m for m in game.missions if m.ch == current.ch and m.kind == "boss"), None)
    if boss is None:
        print("이 장에는 보스가 없습니다.")
        return USAGE
    if refusal := _exam_refusal(game, status.get(boss.key)):
        print(refusal)
        return USAGE
    with state.transaction(conn) as tx:
        progress.start(tx, boss)
        progress.set_mode(tx, "exam", boss.key)
        progress.event(tx, "exam_started", boss.key)
    left = [m for m in game.missions if m.ch == boss.ch and m.track == "core"
            and m.key != boss.key and status.get(m.key) not in progress.DONE]
    print(ui.paint(f"🏁 승급 시험: {line(boss)}", "bold"))
    print(f"통과하면 남은 코어 미션 {len(left)}개를 면제하고 각각 보상의 50%를 받습니다.")
    print(ui.paint("quest mission으로 보스를 보고 quest check로 도전. 그만두면 quest back", "dim"))
    return OK


def cmd_back(game: Game, rest: list[str]) -> int:
    conn = game.conn
    current_mode = progress.mode(conn)
    if current_mode == "normal":
        print("이미 일반 진행입니다.")
        return OK
    with state.transaction(conn) as tx:
        kind = "exam_left" if current_mode == "exam" else "rebuild_left"
        progress.event(tx, kind, progress.mode_mission(conn))
        progress.set_mode(tx, "normal", None)
    print(f"{ui.MODES[current_mode]}를 끝내고 일반 진행으로 돌아왔습니다.")
    return OK
