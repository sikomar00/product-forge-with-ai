"""명령들이 함께 쓰는 것: 게임 열기, 대상 미션 고르기, 종료 코드, 확인 질문."""

import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from quest.core import config, content, progress, review, state, ui
from quest.core.mission import Ctx, Item, Mission

OK, FAIL, USAGE, ENV = 0, 1, 2, 3  # Spec "화면과 종료 코드"


@dataclass(frozen=True)
class Game:
    conn: sqlite3.Connection
    missions: tuple[Mission, ...]
    cfg: dict
    quizzes: dict[int, tuple[Item, ...]] = field(default_factory=dict)  # 장 → 지연 확인 퀴즈
    goals: dict[str, tuple[str, ...]] = field(default_factory=dict)  # 졸업 기준 영역 → 미션 키


def open_game() -> Game:
    if config.ensure_config():
        # stderr로 낸다. status --json의 표준 출력에 섞이면 안 된다.
        print(f"설정 파일을 만들었습니다: {config.config_path()}", file=sys.stderr)
        print("[product]의 repo_path와 github_owner를 내 값으로 바꾸세요.", file=sys.stderr)
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
    return Game(conn, loaded.missions, cfg, loaded.delayed_quiz, loaded.goals)


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
    """명령이 다룰 미션. ID가 없으면 현재 미션. 못 고르거나 복습 잠금이면 (None, 종료 코드)."""
    found, code = _pick(game, rest)
    if found is not None and blocked_by_lock(game, found):
        return None, USAGE
    return found, code


def _pick(game: Game, rest: list[str]) -> tuple[Mission | None, int]:
    if rest:
        found = progress.find(game.missions, rest[0])
        if found is None:
            print(f"❌ 그런 미션이 없습니다: {rest[0]}  (quest 로 현재 미션을 보세요)")
            return None, USAGE
        return found, OK
    found = mode_target(game) or progress.current(game.missions, progress.statuses(game.conn))
    if found is None:
        print("🎉 모든 코어 미션을 마쳤습니다.")
    return found, OK


def mode_target(game: Game) -> Mission | None:
    """시험·복습 모드면 그 대상 미션. 일반 모드면 None."""
    key = progress.mode_mission(game.conn)
    return next((m for m in game.missions if m.key == key), None) if key else None


def due_now(game: Game) -> list[sqlite3.Row]:
    """지금 만기인 카드 가운데 콘텐츠에 있는 것(만기가 오래된 순서)."""
    known = {card.key for m in game.missions for card in m.cards}
    return [row for row in review.due_cards(game.conn) if row["card_key"] in known]


def lock_view(game: Game) -> tuple[bool, int, int]:
    """(잠겼는지, 만기 카드 수, 기준). 읽기만 한다(홈·status --json용)."""
    due, threshold = len(due_now(game)), review.lock_threshold(game.cfg)
    return due >= threshold, due, threshold


def lock_state(game: Game) -> tuple[bool, int, int]:
    """lock_view와 같고, 잠금 on·off 변화를 기록한다. 새 미션 시작·시험·복습 끝에서 쓴다(M0-13)."""
    is_locked, due, threshold = lock_view(game)
    with state.transaction(game.conn) as tx:
        review.sync_lock(tx, due, threshold)
    return is_locked, due, threshold


def blocked_by_lock(game: Game, m: Mission) -> bool:
    """새 미션을 시작하려는데 복습 잠금이면 안내하고 True. 진행 중·끝낸 미션은 막지 않는다.

    면제된 미션을 다시 시작하는 것도 새 작업이라 막는다.
    """
    row = progress.progress_row(game.conn, m.key)
    if row is not None and row["status"] != "exempted":
        return False
    is_locked, due, threshold = lock_state(game)
    if is_locked:
        print(f"🔒 복습 잠금: 만기 카드가 {due}장이라 새 미션을 열지 않습니다.")
        print(f"quest review로 {threshold}장 아래로 줄이면 바로 풀립니다.")
    return is_locked


line = ui.mission_line  # 미션 한 줄: ID, 유형 아이콘, 제목, AI 태그, 예상 시간

