"""IA-9 복습: 카드, 지연 확인 퀴즈, 재구성 복습 제안(M0-12·M0-13, Spec "복습")."""

from quest.commands.ask import ask_card, ask_items, confirm
from quest.commands.common import OK, USAGE, Game, due_now, line, lock_state
from quest.core import badges, progress, review, state, ui
from quest.core.mission import CHECK_KINDS


def cmd_review(game: Game, rest: list[str]) -> int:
    conn = game.conn
    cards = {card.key: card for m in game.missions for card in m.cards}
    due = due_now(game)[: review.MAX_CARDS]
    with state.transaction(conn):
        progress.event(conn, "review_started", None, state.now_utc(), {"cards": len(due)})
    print(ui.paint(f"🃏 오늘 복습할 카드: {len(due)}장", "bold"))
    correct = 0
    for number, row in enumerate(due, 1):
        print(ui.paint(f"\n[{number}/{len(due)}]", "dim"))
        answer = ask_card(cards[row["card_key"]])
        if answer is None:
            print("복습을 멈췄습니다. 답한 카드까지는 저장했습니다.")
            return USAGE
        with state.transaction(conn):
            box = review.record_review(conn, row, answer, state.now_utc())
        correct += answer[0]
        print(ui.paint(f"   → {box}번 상자, {review.INTERVAL_DAYS[box]}일 뒤 다시", "dim"))
    at = state.now_utc()
    with state.transaction(conn):
        progress.event(conn, "review_finished", None, at, {"cards": len(due), "correct": correct})
    with state.transaction(conn):
        for key in badges.award(conn, None, at):
            print(ui.paint(f"🏅 배지 획득: {badges.name(key)}", "yellow"))
    still_locked = lock_state(game)[0]
    days = review.streak(conn, state.parse_utc(at).astimezone(state.KST).date())
    print(f"\n복습 끝: {correct}/{len(due)} 맞힘 · 연속 복습 {days}일")
    if still_locked:
        print("🔒 아직 만기 카드가 많아 새 미션이 잠겨 있습니다. 내일 다시 quest review")
    if not _delayed_quizzes(game):
        return USAGE
    _offer_rebuild(game)
    return OK


def _delayed_quizzes(game: Game) -> bool:
    """만기가 된 장마다 지연 확인 퀴즈 10문항을 한 번 낸다. 중간에 입력이 끝나면 False."""
    for chapter in review.delayed_quiz_chapters(game.conn):
        quiz = game.quizzes.get(chapter)
        if not quiz:
            continue
        print()
        print(ui.paint(f"🧠 {chapter}장 지연 확인 퀴즈: 장을 마치고 2주가 지났습니다", "bold"))
        answered = ask_items(quiz)
        if answered is None:
            print("퀴즈를 멈췄습니다. 다음 quest review에서 처음부터 다시 냅니다.")
            return False
        with state.transaction(game.conn):
            review.record_delayed_quiz(
                game.conn, chapter, [(a.item.no, a.correct, a.confidence) for a in answered],
                state.now_utc(),
            )
        print(f"{chapter}장 지연 확인 퀴즈: {sum(a.correct for a in answered)}/{len(answered)}")
    return True


def _offer_rebuild(game: Game) -> None:
    """주 1회 재구성 복습을 제안하고, 받아들이면 샌드박스를 만들고 복습 모드로 들어간다."""
    conn, at = game.conn, state.now_utc()
    if progress.mode(conn) != "normal" or not review.rebuild_due(conn, at):
        return
    candidates = [m.key for m in game.missions if m.kind in CHECK_KINDS and not m.requires_lab]
    key = review.rebuild_target(conn, candidates)
    m = next((m for m in game.missions if m.key == key), None)
    if m is None:
        return
    print()
    if not confirm(f"🔁 재구성 복습: {line(m)}를 빈 폴더에서 다시 만들어 볼까요?"):
        return
    sandbox = review.sandbox_path(m.id, at)
    sandbox.mkdir(parents=True, exist_ok=True)
    with state.transaction(conn):
        progress.set_mode(conn, "review", m.key, at)
        progress.event(conn, "rebuild_started", m.key, at)
    print(f"빈 폴더에서 처음부터 다시 만드세요: {sandbox}")
    print(ui.paint("다 되면 quest check(이 폴더를 채점), 그만두면 quest back", "dim"))
