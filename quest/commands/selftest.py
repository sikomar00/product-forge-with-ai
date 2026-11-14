"""IA-19 연동 확인(M1-04, UJ-10, Spec "quest selftest").

받아 둔 실제 콘텐츠의 미션 테스트를 이 엔진으로 돌린다. 보여 주는 것은 통과·실패 개수와,
실패한 미션의 화면 번호와 엔진 쪽 오류 위치(quest/ 패키지의 파일·줄)뿐이다.
콘텐츠 쪽 프레임과 오류 메시지는 정답이 섞일 수 있어 보여 주지 않는다(ADR-0006).

2026-11-13 결정: 콘텐츠 테스트는 화면 번호로 매개변수화해, 테스트 이름이 '…[5-8]'로 끝난다.
"""

import re
import sys
import tempfile

# 읽는 XML은 이 컴퓨터의 pytest가 임시 폴더에 막 쓴 파일이라 외부 입력이 아니다.
# 표준 ElementTree는 외부 엔터티를 가져오지 않으므로 defusedxml(새 라이브러리)을 더하지 않는다.
import xml.etree.ElementTree as ET  # noqa: S405
from pathlib import Path

import quest
from quest import external
from quest.commands.common import FAIL, OK
from quest.core import config, content, progress, state, ui

SELFTEST_TIMEOUT_SEC = 900
SCREEN_ID = re.compile(r"\[(\d{1,2}-[0-9A-Za-z]+)\]$")
ENGINE_DIR = Path(quest.__file__).resolve().parent


def engine_frames(text: str) -> list[str]:
    """실패 내용에서 엔진 패키지 안의 '파일:줄'만 뽑는다(엔진 리포 기준 상대 경로).

    pytest 기본 형식('경로:줄')과 파이썬 기본 형식('File "경로", line 줄')을 모두 읽는다.
    """
    prefix = re.escape(str(ENGINE_DIR).replace("\\", "/")) + r'/([^\s:"]+\.py)(?::|", line )(\d+)'
    found = re.findall(prefix, text.replace("\\", "/"))
    return list(dict.fromkeys(f"quest/{path}:{line}" for path, line in found))


def summarize(junit_xml: Path) -> tuple[int, list[tuple[str, list[str]]]]:
    """(통과 수, [(화면 번호, 엔진 쪽 위치들)])."""
    passed, failed = 0, []
    for case in ET.parse(junit_xml).getroot().iter("testcase"):
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is None:
            passed += case.find("skipped") is None
            continue
        screen = SCREEN_ID.search(case.get("name", ""))
        detail = (problem.text or "") + (problem.get("message") or "")
        failed.append((screen[1] if screen else "?", engine_frames(detail)))
    return passed, failed


def _run_content_tests(root: Path) -> tuple[int, list[tuple[str, list[str]]]]:
    tests = root / "tests"
    if not tests.is_dir():
        raise config.EnvError("받아 둔 콘텐츠에 tests 폴더가 없습니다. quest update로 받으세요.")
    with tempfile.TemporaryDirectory(prefix="quest-selftest-") as folder:
        report = Path(folder) / "junit.xml"
        # --tb=native: pytest 기본 형식은 실행 폴더 기준 상대 경로('..\..')로 줄일 때가 있어
        # 엔진 위치를 놓친다. 파이썬 기본 형식은 늘 절대 경로다.
        external.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                      "--tb=native", f"--junitxml={report}", str(tests)],
                     cwd=root, timeout=SELFTEST_TIMEOUT_SEC)
        if not report.exists():
            raise config.EnvError("콘텐츠 테스트를 실행하지 못했습니다(pytest 결과 파일 없음).")
        return summarize(report)


def cmd_selftest(game: None, rest: list[str]) -> int:
    config.ensure_config()
    root = content.content_root(config.load_config())
    passed, failed = _run_content_tests(root)
    print(f"selftest: 통과 {passed} · 실패 {len(failed)}")
    for screen, frames in failed:
        where = ", ".join(frames) if frames else "엔진 쪽 위치 없음(콘텐츠 쪽 문제일 수 있음)"
        print(ui.paint(f"  ❌ {screen}: {where}", "red"))
    conn = state.connect()
    try:
        with state.transaction(conn) as tx:
            progress.event(tx, "selftest_run", None, {"passed": passed, "failed": len(failed)})
    finally:
        conn.close()
    return FAIL if failed else OK
