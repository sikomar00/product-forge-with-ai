"""IA-9 복습(M0-12·M0-13)."""

from quest.commands.ask import ask_card
from quest.commands.common import OK, USAGE, Game
from quest.core import progress, review, state, ui


def cmd_review(game: Game, rest: list[str]) -> int:
    conn = game.conn
    cards = {card.key: card for m in game.missions for card in m.cards}
    due = [row for row in review.due_cards(conn) if row["card_key"] in cards]
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
        still_locked = review.sync_lock(conn, review.lock_threshold(game.cfg), at)
    days = review.streak(conn, state.parse_utc(at).astimezone(state.KST).date())
    print(f"\n복습 끝: {correct}/{len(due)} 맞힘 · 연속 복습 {days}일")
    if still_locked:
        print("🔒 아직 만기 카드가 많아 새 미션이 잠겨 있습니다. 내일 다시 quest review")
    return OK
