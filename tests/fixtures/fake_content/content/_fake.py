"""가짜 콘텐츠 공용 도구. ch*.py 패턴이 아니라서 장 파일로 불러오지 않는다."""

from quest.core.mission import Card, Check, Ctx, Item, Result
from quest.core.spoiler import obfuscate as obf

HINTS = (obf("방향 1"), obf("방향 2"), obf("구체 명령"))


def file_exists(name: str) -> Check:
    """workdir에 name 파일이 있으면 통과하는 체크."""

    def fn(ctx: Ctx) -> Result:
        found = (ctx.workdir / name).exists()
        return Result(found, f"{name} {'있음' if found else '없음'}")

    return Check(1, f"{name} 파일이 있다", fn, f"{name} 파일을 만드세요")


def choice_item(no: int, answer: str = "2") -> Item:
    return Item(no, f"가짜 문항 {no}", "choice", obf(answer), ("A", "B", "C"))


def card(key: str) -> Card:
    return Card(key, "concept", "가짜 개념 앞면", "B", "choice", ("A", "B"))
