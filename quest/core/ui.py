"""화면 출력 도구. 색은 보조이고 기호(✅❌💡)로도 구분된다(Spec "화면과 종료 코드")."""

import os
import sys
import unicodedata

KIND_ICONS = {
    "ops": "🎫", "quiz": "🧠", "predict": "🔮", "drill": "⌨️",
    "decision": "⚖️", "audit": "🔍", "incident": "🚨", "boss": "🏁",
}
AI_TAGS = {"solo": "🔒", "pair": "🤝", "delegate": "🚀"}
SCAFFOLDS = {"worked": "예제 따라 하기", "completion": "빈칸 채우기", "independent": "혼자 하기"}
MODES = {"normal": "", "exam": "시험 모드", "review": "복습 모드"}
_COLORS = {"green": "32", "red": "31", "yellow": "33", "bold": "1", "dim": "2"}


def paint(text: str, color: str) -> str:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return text
    return f"\033[{_COLORS[color]}m{text}\033[0m"


def bar(done: int, total: int, width: int = 20) -> str:
    filled = round(width * done / total) if total else 0
    return "█" * filled + "░" * (width - filled) + f" {done}/{total}"


def mission_line(m_id: str, kind: str, title: str, ai: str, est_min: int) -> str:
    return f"{m_id} {KIND_ICONS[kind]} {title} {AI_TAGS[ai]} · 약 {est_min}분"


def display_width(text: str) -> int:
    """터미널 화면 폭. 한글 같은 전각 글자는 2칸이다."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text: str, cells: int) -> str:
    """화면 폭 기준으로 오른쪽을 공백으로 채운다(str.ljust는 글자 수 기준이라 한글이 어긋난다)."""
    return text + " " * max(0, cells - display_width(text))
