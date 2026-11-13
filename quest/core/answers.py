"""문항 정답 확인(M0-11, Spec "채점" 2). 콘텐츠 검증과 채점이 같은 규칙을 쓴다.

2026-11-13 결정: choice·multi·order의 정답은 보기 번호(1부터)다. choice "2", multi "1,3"
(순서 무관, 같은 집합), order "3,1,2"(모든 보기를 한 번씩). regex는 학습자 입력에서
정답 정규식을 찾는다(re.search). 처음·끝을 맞춰야 하면 콘텐츠가 ^·$를 쓴다.
"""

import re

from quest.core import spoiler
from quest.core.mission import Item

FORMAT_GUIDE = {
    "choice": "번호 하나",
    "multi": "번호 여러 개, 쉼표로(예: 1,3)",
    "order": "순서대로 번호를 모두(예: 3,1,2)",
    "regex": "답을 입력",
}


def _numbers(text: str) -> list[int] | None:
    parts = [p for p in re.split(r"[,\s]+", text.strip()) if p]
    if not parts or not all(p.isdigit() for p in parts):
        return None
    return [int(p) for p in parts]


def is_correct(item: Item, response: str) -> bool:
    answer = spoiler.reveal(item.answer)
    if item.kind == "regex":
        return re.search(answer, response.strip()) is not None
    got, want = _numbers(response), _numbers(answer)
    if got is None:
        return False
    if item.kind == "multi":
        return sorted(set(got)) == sorted(want) and len(got) == len(set(got))
    return got == want


def answer_errors(item: Item) -> list[str]:
    """정답이 형식에 맞는지. 난독화가 풀리는 것은 먼저 확인했다고 본다."""
    answer = spoiler.reveal(item.answer)
    if item.kind == "regex":
        try:
            re.compile(answer)
        except re.error as exc:
            return [f"정답 정규식이 틀렸습니다: {exc}"]
        return []
    nums, size = _numbers(answer) or [], len(item.choices)
    in_range = bool(nums) and all(1 <= n <= size for n in nums)
    valid = {
        "choice": in_range and len(nums) == 1,
        "multi": in_range and len(set(nums)) == len(nums),
        "order": sorted(nums) == list(range(1, size + 1)),
    }
    return [] if valid.get(item.kind, True) else [f"{item.kind} 정답이 보기 번호와 맞지 않습니다"]
