"""리포 규칙 점검: 코드 파일은 500줄을 넘지 않는다(rules/code.md, M0 게이트)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE_DIRS = ("quest", "tests", "docs")
CODE_SUFFIXES = {".py", ".sql"}
MAX_LINES = 500


def test_no_code_file_over_500_lines() -> None:
    too_long = [
        f"{path.relative_to(ROOT)}: {count}줄"
        for folder in CODE_DIRS
        for path in (ROOT / folder).rglob("*")
        if path.suffix in CODE_SUFFIXES
        and (count := len(path.read_text(encoding="utf-8").splitlines())) > MAX_LINES
    ]
    assert too_long == []
