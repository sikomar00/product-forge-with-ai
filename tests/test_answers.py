"""문항 정답 확인 시험(M0-11): 보기 번호와 정규식, 콘텐츠 검증."""

import pytest

from quest.core.answers import answer_errors, is_correct
from quest.core.mission import Item
from quest.core.spoiler import obfuscate as obf

ABC = ("가", "나", "다")


@pytest.mark.parametrize(
    ("kind", "answer", "response", "expected"),
    [
        ("choice", "2", "2", True),
        ("choice", "2", " 2 ", True),
        ("choice", "2", "3", False),
        ("choice", "2", "나", False),  # 보기 글자가 아니라 번호로 답한다
        ("multi", "1,3", "3, 1", True),  # 순서 무관
        ("multi", "1,3", "1 3", True),
        ("multi", "1,3", "1", False),
        ("multi", "1,3", "1,3,3", False),
        ("order", "3,1,2", "3,1,2", True),
        ("order", "3,1,2", "1,2,3", False),
        ("regex", r"^git\s+log\b", "git  log --oneline", True),
        ("regex", r"^git\s+log\b", "git logs", False),
        ("regex", "3", "결과는 3줄", True),  # 앵커가 없으면 어디든 찾는다
    ],
)
def test_is_correct(kind: str, answer: str, response: str, expected: bool) -> None:
    assert is_correct(Item(1, "문항", kind, obf(answer), ABC), response) is expected


@pytest.mark.parametrize(
    ("kind", "answer", "valid"),
    [
        ("choice", "2", True),
        ("choice", "4", False),
        ("choice", "1,2", False),
        ("choice", "나", False),
        ("multi", "1,3", True),
        ("multi", "1,1", False),
        ("order", "3,1,2", True),
        ("order", "1,2", False),  # 보기를 모두 써야 한다
        ("regex", r"^git\s", True),
        ("regex", "(", False),
    ],
)
def test_answer_errors(kind: str, answer: str, valid: bool) -> None:
    assert (answer_errors(Item(1, "문항", kind, obf(answer), ABC)) == []) is valid
