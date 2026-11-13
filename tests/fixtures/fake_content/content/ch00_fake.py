"""가짜 0장: 실습·퀴즈·예측·드릴·결정 미션과 지연 확인 퀴즈."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # 같은 폴더의 _fake를 불러오려고

from _fake import HINTS, card, choice_item, file_exists, obf  # noqa: E402

from quest.core.mission import Card, Item, Mission  # noqa: E402

MISSIONS = (
    Mission(
        key="m_f0000001", id="0-1", ch=0, kind="ops", title="가짜 실습", frm="가짜 팀장",
        xp=10, ai="pair", msg="hello.txt를 만드세요", hints=HINTS, solution=obf("touch hello.txt"),
        cards=(card("c_f0000001"),), checks=(file_exists("hello.txt"),),
        explain=(choice_item(1), choice_item(2)), est_min=5, badge="fake_first_file",
    ),
    Mission(
        key="m_f0000002", id="0-2", ch=0, kind="quiz", title="가짜 퀴즈", frm="가짜 팀장",
        xp=5, ai="solo", msg="고르세요", hints=HINTS,
        items=(Item(1, "가짜 문항", "choice", obf("1"), ("A", "B"), ask_confidence=True),),
    ),
    Mission(
        key="m_f0000003", id="0-3", ch=0, kind="predict", title="가짜 예측", frm="가짜 팀장",
        xp=5, ai="solo", msg="결과를 예측하세요", hints=HINTS,
        items=(Item(1, "몇 줄이 나올까", "regex", obf(r"^3$"), ask_confidence=True),),
        cards=(
            Card("c_f0000003", "usage", "가짜 자가 채점 앞면", "가짜 뒷면", "self"),
            Card("c_f0000004", "usage", "로그 보는 명령", "git log", "regex", (r"^git\s+log\b",)),
        ),
    ),
    Mission(
        key="m_f0000004", id="0-4", ch=0, kind="drill", title="가짜 드릴", frm="가짜 팀장",
        xp=5, ai="solo", msg="명령을 입력하세요", hints=HINTS,
        items=(Item(1, "로그 보기", "regex", obf(r"^git\s+log\b")),),
    ),
    Mission(
        key="m_f0000005", id="0-5", ch=0, kind="decision", title="가짜 결정", frm="가짜 팀장",
        xp=10, ai="solo", msg="도구를 고르고 근거를 체크하세요", hints=HINTS,
        items=(
            Item(1, "도구", "choice", obf("1"), ("A", "B")),
            Item(2, "근거", "multi", obf("1,3"), ("비용", "유행", "운영 부담")),
            Item(3, "순서", "order", obf("2,1,3"), ("배포", "빌드", "확인")),
        ),
    ),
)

DELAYED_QUIZ = tuple(choice_item(no) for no in range(1, 11))
