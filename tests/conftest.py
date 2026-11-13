"""CLI 시험 공용 준비: 가짜 콘텐츠로 설정한 게임과 quest 실행기."""

from collections.abc import Callable
from pathlib import Path

import pytest

from quest import cli

FAKE = Path(__file__).parent / "fixtures" / "fake_content"
Quest = Callable[..., tuple[int, str]]


@pytest.fixture
def game(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """가짜 콘텐츠와 빈 작업 폴더로 설정한 게임. 작업 폴더 경로를 돌려준다.

    상태 DB는 작업 폴더 옆 home/state.db에 생긴다.
    """
    work = tmp_path / "opsdesk"
    work.mkdir()
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        f'[product]\nrepo_path = "{work.as_posix()}"\ngithub_owner = "fake"\n'
        f'[content]\nrepo = "fake/fake"\npath = "{FAKE.as_posix()}"\n'
        '[lab]\nvm_name = "pf-lab"\n[review]\nlock_threshold = 20\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("QUEST_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("QUEST_CONFIG", str(cfg))
    monkeypatch.setenv("NO_COLOR", "1")
    for name in ("HOME", "USERPROFILE"):  # 샌드박스(~/forge-sandbox)가 진짜 홈에 생기지 않게
        monkeypatch.setenv(name, str(tmp_path / "userhome"))
    return work


def lock_with_one_due_card(game: Path) -> None:
    """만기 카드 1장(0-3의 카드)과 잠금 기준 1로 복습 잠금을 건다."""
    import sqlite3

    from quest.core import state

    state.connect(game.parent / "home" / "state.db").close()
    conn = sqlite3.connect(game.parent / "home" / "state.db", isolation_level=None)
    conn.execute(
        "INSERT OR IGNORE INTO mission_progress (mission_key, display_id, chapter, status, how,"
        " started_at, completed_at, est_min, ai_tag) VALUES ('m_f0000003', '0-3', 0, 'passed',"
        " 'normal', '2026-01-01T00:00:00Z', '2026-01-01T00:10:00Z', 5, 'solo')"
    )
    conn.execute(
        "INSERT INTO cards (card_key, mission_key, kind, added_at, due_at) VALUES"
        " ('c_f0000003', 'm_f0000003', 'usage', '2026-01-01T00:00:00Z', '2020-01-01T00:00:00Z')"
    )
    conn.close()
    cfg = game.parent / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("= 20", "= 1"), encoding="utf-8")


@pytest.fixture
def quest(capsys: pytest.CaptureFixture[str]) -> Quest:
    """quest 명령을 실행하고 (종료 코드, 화면 출력)을 돌려준다."""

    def run(*args: str) -> tuple[int, str]:
        code = cli.main(list(args))
        captured = capsys.readouterr()
        return code, captured.out + captured.err

    return run


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """[y/N] 같은 질문에 차례로 줄 답. 비어 있으면 입력 끝(EOF)으로 본다."""
    queue: list[str] = []

    def fake_input(prompt: str = "") -> str:
        print(prompt)
        if not queue:
            raise EOFError
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", fake_input)
    return queue
