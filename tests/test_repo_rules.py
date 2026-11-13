"""리포 규칙 점검(M0 게이트): 500줄 넘는 코드 파일 0개, 엔진 리포의 콘텐츠 파일 0개."""

import subprocess
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


def test_no_content_files_outside_fake_fixture() -> None:
    """실제 콘텐츠는 비공개 콘텐츠 리포에만 둔다(ADR-0009). 가짜 픽스처만 예외다."""
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    found = [
        name
        for name in tracked
        if "content" in Path(name).parts[:-1]
        and not name.startswith("tests/fixtures/fake_content/")
    ]
    assert found == []
