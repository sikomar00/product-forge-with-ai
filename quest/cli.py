"""quest 명령의 입구: 명령 해석, 화면, 종료 코드(IA, Spec "화면과 종료 코드")."""

import sqlite3
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from quest.core import config, content, progress, rewards, spoiler, state, ui
from quest.core.mission import CHECK_KINDS, Ctx, Mission
from quest.kinds import ops

OK, FAIL, USAGE, ENV = 0, 1, 2, 3
# 실패한 체크의 설명이 결함·원인 위치를 알려 주므로 숨긴다(IA 결정 4)
HIDE_FAILED_DETAIL = ("audit", "incident")


@dataclass(frozen=True)
class Game:
    conn: sqlite3.Connection
    missions: tuple[Mission, ...]
    cfg: dict


@dataclass(frozen=True)
class Command:
    fn: Callable[[Game | None, list[str]], int]
    usage: str
    desc: str
    max_args: int = 0
    needs_game: bool = True


def _open() -> Game:
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


def _versions(conn: sqlite3.Connection) -> tuple[str, str]:
    row = conn.execute("SELECT value FROM meta WHERE key = 'content_version'").fetchone()
    return version("quest"), row[0] if row else "none"


def _ctx(cfg: dict) -> Ctx:
    try:
        workdir = Path(cfg["product"]["repo_path"]).expanduser()
        lab = cfg["lab"]["vm_name"]
    except KeyError as exc:
        raise config.EnvError(f"설정 파일에 {exc} 항목이 없습니다.") from exc
    return Ctx(workdir=workdir, config=cfg, lab=lab, gh=None, now=datetime.now(UTC))


def _target(game: Game, rest: list[str]) -> tuple[Mission | None, int]:
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


def _line(m: Mission) -> str:
    return ui.mission_line(m.id, m.kind, m.title, m.ai, m.est_min)


# ───────────── IA-1 홈 ─────────────


def cmd_home(game: Game, rest: list[str]) -> int:
    conn = game.conn
    status = progress.statuses(conn)
    m = progress.current(game.missions, status)
    if progress.active_incident(conn):
        print(ui.paint("🚨 진행 중인 장애가 있습니다. quest incident status", "red"))
    ch = m.ch if m else game.missions[-1].ch
    head = f"🔨 Product Forge · {progress.rank(ch)} · {progress.total_xp(conn)} XP"
    print(ui.paint(head, "bold"))
    done, total = progress.chapter_counts(game.missions, status, ch)
    print(f"{ch}장 {progress.CHAPTERS[ch]}  {ui.bar(done, total)}")
    print(f"오늘 복습할 카드: {progress.due_cards(conn)}장")
    if m is None:
        print("🎉 모든 코어 미션을 마쳤습니다.")
        return OK
    mode = ui.MODES[progress.mode(conn)]
    print(f"현재 미션: {_line(m)}" + (f" [{mode}]" if mode else ""))
    started = status.get(m.key) == "in_progress"
    print(ui.paint(f"다음: quest {'check' if started else 'mission'}", "dim"))
    return OK


# ───────────── IA-2 미션 보기 ─────────────


def _where(m: Mission, cfg: dict) -> str:
    if m.requires_lab:
        return f"랩 VM ({cfg.get('lab', {}).get('vm_name', '?')})"
    if m.kind in CHECK_KINDS:
        return f"OpsDesk 리포 ({cfg.get('product', {}).get('repo_path', '?')})"
    return "이 터미널에서 답합니다"


def cmd_mission(game: Game, rest: list[str]) -> int:
    m, code = _target(game, rest)
    if m is None:
        return code
    with state.transaction(game.conn):
        progress.start(game.conn, m, state.now_utc())
    track = "코어" if m.track == "core" else "➕선택"
    print(ui.paint(f"{_line(m)} · {track} · {ui.SCAFFOLDS[m.scaffold]}", "bold"))
    print(f"\n📨 {m.frm}\n{m.msg}")
    for card in sorted(m.cards, key=lambda c: c.kind != "tool_map"):  # 도구 지도 카드 먼저
        print(f"\n{'🗺️' if card.kind == 'tool_map' else '🃏'} {card.front}\n   {card.back}")
    print(f"\n작업 위치: {_where(m, game.cfg)}")
    print(ui.paint("다음: quest check", "dim"))
    return OK


# ───────────── IA-3 채점 ─────────────


def _show_results(m: Mission, results: list, traps: list[str]) -> None:
    if m.kind in HIDE_FAILED_DETAIL:
        print(f"체크 {sum(r.ok for r in results)}/{len(results)} 통과")
        for check, r in zip(m.checks, results, strict=True):
            if not r.ok:
                print(f"   ↳ {check.hint}")
    else:
        for check, r in zip(m.checks, results, strict=True):
            mark = ui.paint("✅", "green") if r.ok else ui.paint("❌", "red")
            print(f"{mark} {check.no}. {check.desc}" + (f" — {r.detail}" if r.detail else ""))
            if not r.ok:
                print(f"   ↳ {check.hint}")
    for message in traps:
        print(ui.paint(f"💡 {message}", "yellow"))


def cmd_check(game: Game, rest: list[str]) -> int:
    m, code = _target(game, rest)
    if m is None:
        return code
    if m.kind not in CHECK_KINDS:
        print(f"{ui.KIND_ICONS[m.kind]} 이 유형의 채점은 아직 준비 중입니다.")
        return USAGE
    results, traps = ops.grade(m, _ctx(game.cfg))  # 체크는 읽기 전용이라 트랜잭션 밖에서 돌린다
    conn, at, xp = game.conn, state.now_utc(), None
    with state.transaction(conn):
        progress.start(conn, m, at)
        outcome = progress.record_attempt(conn, m, [r.ok for r in results], at, _versions(conn))
        row = progress.progress_row(conn, m.key)
        if outcome == "pass" and row["status"] == "in_progress":
            xp = rewards.mission_xp(m.xp, row["hints_used"], row["fails"], row["solution_seen"])
            progress.pass_mission(conn, m, xp, at)
    _show_results(m, results, traps)
    if outcome == "fail":
        print(ui.paint("고친 뒤 다시 quest check. 막히면 quest hint", "dim"))
        return FAIL
    if xp is None:
        print("✅ 이미 끝낸 미션입니다. 보상은 다시 주지 않습니다.")
        return OK
    one_shot = row["fails"] == 0 and row["hints_used"] == 0 and not row["solution_seen"]
    print(ui.paint(f"🎉 통과! +{xp} XP" + (" (원샷 보너스)" if one_shot else ""), "green"))
    if m.cards:
        print(f"🃏 카드 {len(m.cards)}장이 복습 덱에 들어갔습니다.")
    nxt = progress.current(game.missions, progress.statuses(conn))
    print(f"다음 미션: {_line(nxt)} → quest mission" if nxt else "🎉 모든 코어 미션을 마쳤습니다.")
    return OK


# ───────────── IA-4 힌트 · IA-5 모범 답안 ─────────────


def _confirm(question: str) -> bool:
    try:
        answer = input(f"{question} [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes", "ㅛ")  # ㅛ: 한글 자판 상태에서 누른 y


def _open_row(game: Game, rest: list[str]) -> tuple[Mission | None, sqlite3.Row | None, int]:
    """대상 미션을 시작 상태로 만들고 (미션, 진행 행, 종료 코드)를 돌려준다."""
    m, code = _target(game, rest)
    if m is None:
        return None, None, code
    with state.transaction(game.conn):
        progress.start(game.conn, m, state.now_utc())
    return m, progress.progress_row(game.conn, m.key), OK


def cmd_hint(game: Game, rest: list[str]) -> int:
    m, row, code = _open_row(game, rest)
    if m is None:
        return code
    if row["status"] != "in_progress":
        print("이미 끝낸 미션입니다. quest solution으로 모범 답안을 감점 없이 볼 수 있습니다.")
        return OK
    used = row["hints_used"]
    if used >= len(m.hints):
        print("힌트 3단계를 모두 봤습니다. 그래도 막히면 quest solution")
        return OK
    before = rewards.mission_xp(m.xp, used, row["fails"], row["solution_seen"])
    after = rewards.mission_xp(m.xp, used + 1, row["fails"], row["solution_seen"])
    question = f"💡 힌트 {used + 1}단계를 열면 보상이 {before} → {after} XP가 됩니다. 열까요?"
    if not _confirm(question):
        print("열지 않았습니다.")
        return OK
    with state.transaction(game.conn):
        level = progress.open_hint(game.conn, m, state.now_utc())
    print(ui.paint(f"💡 힌트 {level}/{len(m.hints)}", "yellow"))
    print(spoiler.reveal(m.hints[level - 1]))
    if level == len(m.hints):
        print(ui.paint("그래도 막히면 quest solution", "dim"))
    return OK


def cmd_solution(game: Game, rest: list[str]) -> int:
    m, row, code = _open_row(game, rest)
    if m is None:
        return code
    if m.solution is None:
        print("이 미션에는 모범 답안이 없습니다.")
        return OK
    if row["status"] == "in_progress" and not row["solution_seen"]:
        before = rewards.mission_xp(m.xp, row["hints_used"], row["fails"], False)
        after = rewards.mission_xp(m.xp, row["hints_used"], row["fails"], True)
        question = (f"📖 모범 답안을 보면 보상이 {before} → {after} XP가 되고, "
                    "재구성 복습에 먼저 나옵니다. 볼까요?")
        if not _confirm(question):
            print("보지 않았습니다.")
            return OK
        with state.transaction(game.conn):
            progress.view_solution(game.conn, m, state.now_utc())
    print(ui.paint("📖 모범 답안", "bold"))
    print(spoiler.reveal(m.solution))
    return OK


# ───────────── IA-16 도움말 ─────────────


def cmd_help(game: Game | None = None, rest: list[str] | None = None) -> int:
    print("quest — Product Forge With AI\n")
    for name, command in COMMANDS.items():
        print(f"  {f'quest {name} {command.usage}'.strip():<22} {command.desc}")
    return OK


COMMANDS = {
    "": Command(cmd_home, "", "홈: 등급·XP·진행·현재 미션"),
    "mission": Command(cmd_mission, "[ID]", "미션 보기. ID를 빼면 현재 미션", max_args=1),
    "check": Command(cmd_check, "[ID]", "채점", max_args=1),
    "hint": Command(cmd_hint, "[ID]", "다음 단계 힌트(감점)", max_args=1),
    "solution": Command(cmd_solution, "[ID]", "모범 답안(보상 20%만)", max_args=1),
    "help": Command(cmd_help, "", "명령 목록", needs_game=False),
}


def _utf8_console() -> None:
    if sys.platform == "win32":  # Windows 기본 코드 페이지로는 이모지·한글이 깨진다
        for stream in (sys.stdout, sys.stderr):
            stream.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    args = sys.argv[1:] if argv is None else argv
    name, rest = (args[0], args[1:]) if args else ("", [])
    command = COMMANDS.get(name)
    if command is None or len(rest) > command.max_args:
        cmd_help()
        return USAGE
    if not command.needs_game:
        return command.fn(None, rest)
    game = None
    try:
        game = _open()
        return command.fn(game, rest)
    except config.EnvError as exc:
        print(ui.paint(f"❌ {exc}", "red"), file=sys.stderr)
        return ENV
    finally:
        if game is not None:
            game.conn.close()
