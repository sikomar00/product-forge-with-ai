"""명령들이 함께 쓰는 것: 게임 열기, 대상 미션 고르기, 종료 코드, 확인 질문."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from quest.core import config, content, progress, state, ui
from quest.core.mission import Ctx, Mission

OK, FAIL, USAGE, ENV = 0, 1, 2, 3  # Spec "화면과 종료 코드"


@dataclass(frozen=True)
class Game:
    conn: sqlite3.Connection
    missions: tuple[Mission, ...]
    cfg: dict


def open_game() -> Game:
    if config.ensure_config():
        print(f"설정 파일을 만들었습니다: {config.config_path()}")
        print("[product]의 repo_path와 github_owner를 내 값으로 바꾸세요.")
    cfg = config.load_config()
    loaded = content.load_content(content.content_root(cfg))
    if not loaded.missions:
        raise config.EnvError("콘텐츠에 미션이 없습니다. quest update로 받으세요.")
    conn = state.connect()
    with state.transaction(conn):
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('engine_version', ?)"
            " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (version("quest"),),
        )
    return Game(conn, loaded.missions, cfg)


def versions(conn: sqlite3.Connection) -> tuple[str, str]:
    row = conn.execute("SELECT value FROM meta WHERE key = 'content_version'").fetchone()
    return version("quest"), row[0] if row else "none"


def make_ctx(cfg: dict) -> Ctx:
    try:
        workdir = Path(cfg["product"]["repo_path"]).expanduser()
        lab = cfg["lab"]["vm_name"]
    except KeyError as exc:
        raise config.EnvError(f"설정 파일에 {exc} 항목이 없습니다.") from exc
    return Ctx(workdir=workdir, config=cfg, lab=lab, gh=None, now=datetime.now(UTC))


def target(game: Game, rest: list[str]) -> tuple[Mission | None, int]:
    """명령이 다룰 미션. ID가 없으면 현재 미션. 못 고르면 (None, 종료 코드)."""
    if rest:
        found = progress.find(game.missions, rest[0])
        if found is None:
            print(f"❌ 그런 미션이 없습니다: {rest[0]}  (quest 로 현재 미션을 보세요)")
            return None, USAGE
        return found, OK
    found = progress.current(game.missions, progress.statuses(game.conn))
    if found is None:
        print("🎉 모든 코어 미션을 마쳤습니다.")
    return found, OK


def line(m: Mission) -> str:
    return ui.mission_line(m.id, m.kind, m.title, m.ai, m.est_min)


def confirm(question: str) -> bool:
    try:
        answer = input(f"{question} [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes", "ㅛ")  # ㅛ: 한글 자판 상태에서 누른 y

