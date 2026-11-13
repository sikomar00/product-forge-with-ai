"""M0 전체 코드 리뷰(2026-11-13) 지적의 회귀 시험."""

import shutil
import sqlite3
from pathlib import Path

import pytest
from conftest import FAKE, Quest, lock_with_one_due_card

from quest.core import content
from quest.core.config import EnvError


def _db(game: Path) -> sqlite3.Connection:
    return sqlite3.connect(game.parent / "home" / "state.db", isolation_level=None)


def test_stats_sql_with_relative_quest_home(
    game: Path, quest: Quest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(game.parent)
    monkeypatch.setenv("QUEST_HOME", "home")  # 상대 경로
    code, out = quest("stats", "--sql", "SELECT 1 AS one")
    assert code == 0 and "one\n1" in out


def test_corrupted_state_db_is_env_error(game: Path, quest: Quest) -> None:
    home = game.parent / "home"
    home.mkdir()
    (home / "state.db").write_bytes(b"this is not a sqlite file" * 100)
    code, out = quest()
    assert code == 3 and "상태 DB를 읽지 못했습니다" in out and "백업에서 되돌리기" in out


def test_lock_threshold_zero_turns_lock_off(game: Path, quest: Quest) -> None:
    lock_with_one_due_card(game)
    assert "복습 잠금" in quest()[1]
    cfg = game.parent / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("= 1", "= 0"), encoding="utf-8")
    assert "복습 잠금" not in quest()[1]
    assert quest("mission")[0] == 0


@pytest.mark.parametrize(("engine", "ok"), [("0.1.0.dev1", True), ("0.1.0rc1", True),
                                            ("0.2.0.dev0", False)])
def test_engine_version_with_suffix(engine: str, ok: bool) -> None:
    assert content.satisfies(">=0.1,<0.2", engine) is ok


def test_unreadable_version_is_env_error() -> None:
    with pytest.raises(EnvError, match="버전 형식"):
        content.satisfies(">=0.1", "dev")


def test_review_without_due_cards_does_not_count_as_review_day(game: Path, quest: Quest) -> None:
    quest("review")
    kinds = [k for (k,) in _db(game).execute("SELECT kind FROM events")]
    assert "review_finished" not in kinds and "review_started" not in kinds


ERROR_CHAPTER = '''
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _fake import HINTS  # noqa: E402

from quest.core.mission import Check, CheckEnvError, Mission  # noqa: E402


def broken(ctx):
    raise FileNotFoundError("secret/answer/path.txt")


def offline(ctx):
    raise CheckEnvError("네트워크에 연결할 수 없습니다")


MISSIONS = (
    Mission(key="m_e0000001", id="2-1", ch=2, kind="ops", title="오류 체크", frm="가짜",
            xp=10, ai="solo", msg="m", hints=HINTS, checks=(Check(1, "d", broken, "h"),)),
    Mission(key="m_e0000002", id="2-2", ch=2, kind="ops", title="환경 오류", frm="가짜",
            xp=10, ai="solo", msg="m", hints=HINTS, checks=(Check(1, "d", offline, "h"),)),
)
'''


@pytest.fixture
def error_game(game: Path, tmp_path: Path) -> Path:
    root = Path(shutil.copytree(FAKE, tmp_path / "content_copy"))
    (root / "content" / "ch02_errors.py").write_text(ERROR_CHAPTER, encoding="utf-8")
    cfg = game.parent / "config.toml"
    text = cfg.read_text(encoding="utf-8").replace(FAKE.as_posix(), root.as_posix())
    cfg.write_text(text, encoding="utf-8")
    return game


def test_crashing_check_is_recorded_as_error_not_failure(error_game: Path, quest: Quest) -> None:
    code, out = quest("check", "2-1")
    assert code == 3 and "채점을 끝내지 못했습니다: FileNotFoundError" in out
    assert "secret/answer" not in out  # 콘텐츠 예외 메시지는 보여 주지 않는다
    row = _db(error_game).execute("SELECT outcome FROM attempts").fetchone()
    assert row == ("error",)
    assert _db(error_game).execute("SELECT fails FROM mission_progress").fetchone() == (0,)


def test_check_env_error_message_is_shown(error_game: Path, quest: Quest) -> None:
    code, out = quest("check", "2-2")
    assert code == 3 and "네트워크에 연결할 수 없습니다" in out
