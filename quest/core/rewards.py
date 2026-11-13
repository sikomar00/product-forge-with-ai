"""보상 계산(M0-08). S1 engine.py의 on_success와 같은 계산이다(Spec "보상")."""

from collections.abc import Mapping
from dataclasses import dataclass

SOLUTION_RATE = 0.2
ONE_SHOT_RATE = 0.2
HINT_PENALTY = 0.2
MIN_RATE = 0.4
EXAM_SKIP_RATE = 0.5
REBUILD_RATE = 0.15
REBUILD_MIN = 3


@dataclass(frozen=True)
class Help:
    """보상에 영향을 주는 것: 연 힌트 수, 실패 수, 모범 답안을 봤는지."""

    hints: int = 0
    fails: int = 0
    solution_seen: bool = False

    @classmethod
    def of(cls, row: Mapping) -> Help:
        """mission_progress 행(또는 같은 키를 가진 dict)에서."""
        return cls(row["hints_used"], row["fails"], bool(row["solution_seen"]))


def mission_xp(xp: int, used: Help) -> int:
    """반올림은 S1과 같게 Python round()(은행가 반올림)를 그대로 쓴다."""
    if used.solution_seen:
        return round(xp * SOLUTION_RATE)
    earned = round(xp * max(MIN_RATE, 1 - HINT_PENALTY * used.hints))
    if used.fails == 0 and used.hints == 0:
        earned += round(xp * ONE_SHOT_RATE)
    return earned


def exam_skip_xp(xp: int) -> int:
    """승급 시험으로 면제된 미션 하나의 보상(Spec "보상")."""
    return round(xp * EXAM_SKIP_RATE)


def rebuild_xp(xp: int) -> int:
    """재구성 복습 통과 보상. rebuild_passed 이벤트 값으로 남는다(Spec "보상")."""
    return max(REBUILD_MIN, round(xp * REBUILD_RATE))
