"""보상 계산(M0-08). S1 engine.py의 on_success와 같은 계산이다(Spec "보상")."""

SOLUTION_RATE = 0.2
ONE_SHOT_RATE = 0.2
HINT_PENALTY = 0.2
MIN_RATE = 0.4
EXAM_SKIP_RATE = 0.5


def mission_xp(xp: int, hints: int, fails: int, solution_seen: bool) -> int:
    """반올림은 S1과 같게 Python round()(은행가 반올림)를 그대로 쓴다."""
    if solution_seen:
        return round(xp * SOLUTION_RATE)
    earned = round(xp * max(MIN_RATE, 1 - HINT_PENALTY * hints))
    if fails == 0 and hints == 0:
        earned += round(xp * ONE_SHOT_RATE)
    return earned


def exam_skip_xp(xp: int) -> int:
    """승급 시험으로 면제된 미션 하나의 보상(Spec "보상")."""
    return round(xp * EXAM_SKIP_RATE)
