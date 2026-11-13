"""가짜 1장: 감사·장애·보스 미션과 선택 미션."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # 같은 폴더의 _fake를 불러오려고

from _fake import HINTS, choice_item, file_exists, obf  # noqa: E402

from quest.core.mission import Mission  # noqa: E402

MISSIONS = (
    Mission(
        key="m_f0000011", id="1-1", ch=1, kind="audit", title="가짜 감사", frm="가짜 팀장",
        xp=15, ai="delegate", msg="결함을 고치세요", hints=HINTS, solution=obf("fixed.txt"),
        checks=(file_exists("fixed.txt"),), explain=(choice_item(1),),
    ),
    Mission(
        key="m_f0000012", id="1-2", ch=1, kind="incident", title="가짜 장애", frm="가짜 팀장",
        xp=20, ai="solo", msg="복구하세요", hints=HINTS, checks=(file_exists("recovered.txt"),),
    ),
    Mission(
        key="m_f0000013", id="1-3", ch=1, kind="ops", title="가짜 선택 실습", frm="가짜 팀장",
        xp=10, ai="solo", msg="선택 미션", hints=HINTS, track="elective",
        checks=(file_exists("extra.txt"),),
    ),
    Mission(
        key="m_f0000014", id="1-B", ch=1, kind="boss", title="가짜 보스", frm="가짜 팀장",
        xp=30, ai="solo", msg="모두 하세요", hints=HINTS, checks=(file_exists("boss.txt"),),
    ),
)
