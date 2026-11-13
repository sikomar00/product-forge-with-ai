"""그 자리에서 묻기: 문항 답, 확신도(IA 결정 1 "답이 필요한 순간에만 묻는다")."""

from dataclasses import dataclass

from quest.core import answers, ui
from quest.core.mission import Item

CONFIDENCE = "확신도 1(찍음) 2(반반) 3(확신)"


@dataclass(frozen=True)
class Answered:
    item: Item
    correct: bool
    confidence: int | None


def read(prompt: str) -> str | None:
    """한 줄 입력. 입력이 끝났으면(EOF) None."""
    try:
        return input(prompt)
    except EOFError:
        return None


def ask_confidence() -> int | None:
    while (text := read(f"{CONFIDENCE}: ")) is not None:
        if text.strip() in ("1", "2", "3"):
            return int(text)
        print("1, 2, 3 가운데 하나를 입력하세요.")
    return None


def ask_items(items: tuple[Item, ...]) -> list[Answered] | None:
    """문항을 차례로 묻고 바로 채점한다. 중간에 입력이 끝나면 None(기록하지 않는다).

    정답은 보여 주지 않는다. 다시 풀 때 그대로 답이 되기 때문이다.
    """
    result = []
    for item in items:
        print(f"\n{item.no}. {item.prompt}")
        for number, choice in enumerate(item.choices, 1):
            print(f"   {number}) {choice}")
        response = read(f"{answers.FORMAT_GUIDE[item.kind]}: ")
        if response is None:
            return None
        confidence = ask_confidence() if item.ask_confidence else None
        if item.ask_confidence and confidence is None:
            return None
        correct = answers.is_correct(item, response)
        print(ui.paint("✅ 맞았습니다", "green") if correct else ui.paint("❌ 틀렸습니다", "red"))
        result.append(Answered(item, correct, confidence))
    return result
