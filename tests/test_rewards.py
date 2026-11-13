"""보상 계산 시험(M0-08). S1 on_success와 같은 계산인지는 T0-8 S1 회귀에서 다시 본다."""

import pytest

from quest.core.rewards import Help, mission_xp


@pytest.mark.parametrize(
    ("xp", "hints", "fails", "solution", "expected"),
    [
        (10, 0, 0, False, 12),  # 원샷 보너스 +20%
        (10, 0, 1, False, 10),  # 실패가 있으면 보너스 없음
        (10, 1, 0, False, 8),  # 힌트 하나에 20% 감점, 보너스 없음
        (10, 2, 3, False, 6),
        (10, 3, 0, False, 4),  # 최대 60% 감점
        (10, 0, 0, True, 2),  # 모범 답안을 보면 20%만
        (12, 3, 0, False, 5),  # round(4.8)
        (13, 0, 0, True, 3),  # round(2.6)
    ],
)
def test_mission_xp(xp: int, hints: int, fails: int, solution: bool, expected: int) -> None:
    assert mission_xp(xp, Help(hints, fails, solution)) == expected
