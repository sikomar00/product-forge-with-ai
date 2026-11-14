"""quest selftest·report 시험(M1-04, M1-11, IA-19, IA-20): 내용 가림."""

import subprocess
from pathlib import Path

import pytest
from conftest import FAKE, Quest

from quest import external
from quest.commands import selftest

# 콘텐츠 테스트 흉내: 통과 1, 콘텐츠 쪽 실패 1(정답 글자를 담은 메시지), 엔진 안에서 터지는 실패 1
CONTENT_TESTS = '''
import pytest

from quest.core import spoiler


@pytest.mark.parametrize("screen", ["0-1"])
def test_passes(screen):
    assert True


@pytest.mark.parametrize("screen", ["0-2"])
def test_content_side_failure(screen):
    assert "정답은 SECRET_ANSWER" == "", "SECRET_ANSWER가 필요하다"


@pytest.mark.parametrize("screen", ["1-B"])
def test_engine_side_failure(screen):
    spoiler.reveal("평문은 obf1이 아니다")
'''


@pytest.fixture
def content_with_tests(game: Path, tmp_path: Path) -> Path:
    root = tmp_path / "content_repo"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_missions.py").write_text(CONTENT_TESTS, encoding="utf-8")
    cfg = game.parent / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(FAKE.as_posix(), root.as_posix()),
                   encoding="utf-8")
    return root


def test_selftest_shows_counts_and_engine_frames_only(
    content_with_tests: Path, quest: Quest
) -> None:
    code, out = quest("selftest")
    assert code == 1 and "selftest: 통과 1 · 실패 2" in out
    assert "❌ 0-2: 엔진 쪽 위치 없음" in out
    assert "❌ 1-B: quest/core/spoiler.py:" in out
    assert "SECRET_ANSWER" not in out and "test_missions.py" not in out  # 콘텐츠 쪽은 가린다


def test_engine_frames_ignore_other_paths() -> None:
    engine = str(selftest.ENGINE_DIR)
    text = (f"{engine}/core/state.py:40: in connect\n"
            "/Users/me/.local/share/quest/content/tests/test_x.py:3: AssertionError\n"
            f"{engine}\\core\\state.py:40: in connect\n"
            f'  File "{engine}/core/spoiler.py", line 19, in reveal\n'
            '  File "/Users/me/.local/share/quest/content/tests/test_x.py", line 3, in test_x\n'
            "..\\..\\elsewhere\\quest\\core\\ui.py:5: ValueError")
    assert selftest.engine_frames(text) == ["quest/core/state.py:40", "quest/core/spoiler.py:19"]


def test_selftest_without_tests_folder(game: Path, quest: Quest) -> None:
    code, out = quest("selftest")
    assert code == 3 and "tests 폴더가 없습니다" in out


# ───────────── report ─────────────


@pytest.fixture
def gh_calls(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []
    def fake_run(args: list[str], cwd: Path | None = None,
                 timeout: int = 60) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "https://github.com/me/c/issues/7\n", "")

    monkeypatch.setattr(external, "run", fake_run)
    monkeypatch.setattr(external, "version_of", lambda cmd: "1.0")
    return calls


def test_report_opens_issue_with_diagnosis_only(
    game: Path, quest: Quest, answers: list[str], gh_calls: list[list[str]]
) -> None:
    quest("check")  # hello.txt가 없어 실패 1회
    answers.extend(["체크 1이 이상해요", "y"])
    code, out = quest("report")
    assert code == 0 and "이슈를 열었습니다: https://github.com/me/c/issues/7" in out
    args = gh_calls[-1]
    assert args[:5] == ["gh", "issue", "create", "-R", "fake/fake"]
    title, body = args[args.index("--title") + 1], args[args.index("--body") + 1]
    assert title == "[오판 신고] 0-1 (m_f0000001)"
    assert "미션: m_f0000001 (0-1)" in body and "실패 · normal · 체크 1❌" in body
    assert "학습자 설명: 체크 1이 이상해요" in body
    secrets = ("hello.txt 파일이 있다", "hello.txt 파일을 만드세요", "touch hello.txt", "방향 1")
    assert not [s for s in secrets if s in body]  # 체크 설명·힌트·모범 답안은 담지 않는다


def test_report_can_be_declined(
    game: Path, quest: Quest, answers: list[str], gh_calls: list[list[str]]
) -> None:
    answers.extend(["", "n"])
    code, out = quest("report", "0-2")
    assert code == 0 and "열지 않았습니다" in out and "아직 채점 기록 없음" in out
    assert not any(c[:3] == ["gh", "issue", "create"] for c in gh_calls)
