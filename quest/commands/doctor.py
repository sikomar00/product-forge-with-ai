"""IA-12 장비 점검(M1-02, M0-19, Spec "quest doctor").

엔진이 직접 필요한 것(SQLite·Python·uv·git·gh와 로그인·OrbStack)과, 콘텐츠의 content.toml
[tools]에 적힌 0~4장 도구를 검사한다. 2026-11-13 결정: [tools] 형식은
    [tools.<이름>]
    cmd = ["<명령>", "--version"]  version = ">=N"  install = "<설치 명령>"  chapter = N
"""

import sqlite3
import sys
from dataclasses import dataclass

from quest import external
from quest.commands.common import ENV, OK
from quest.core import config, content, state, ui

DOCTOR_LAST_CHAPTER = 4  # M1은 0~4장. 장이 늘면 올린다


@dataclass(frozen=True)
class Tool:
    name: str
    cmd: list[str]
    version: str  # 허용 범위(requires_engine과 같은 형식). 비면 설치만 본다
    install: str


ENGINE_TOOLS = (
    Tool("uv", ["uv", "--version"], "", "brew install uv"),
    Tool("git", ["git", "--version"], "", "brew install git"),
    Tool("gh", ["gh", "--version"], "", "brew install gh"),
    Tool("orb", ["orb", "version"], "", "brew install --cask orbstack  (macOS 전용)"),
)


def _line(ok: bool, text: str) -> bool:
    print(f"{ui.paint('✅', 'green') if ok else ui.paint('❌', 'red')} {text}")
    return ok


def _check_runtime() -> list[bool]:
    sqlite_ok = tuple(map(int, sqlite3.sqlite_version.split("."))) >= state.MIN_SQLITE
    python_ok = sys.version_info >= (3, 14)
    return [
        _line(sqlite_ok, f"SQLite {sqlite3.sqlite_version} (3.37 이상 필요, STRICT 표)"),
        _line(python_ok, f"Python {sys.version.split()[0]} (3.14 이상 필요)"),
    ]


def _check_tool(tool: Tool) -> bool:
    found = external.version_of(tool.cmd)
    if found is None:
        return _line(False, f"{tool.name} 없음 — 설치: {tool.install}")
    if tool.version and not content.satisfies(tool.version, found):
        return _line(False, f"{tool.name} {found} (필요: {tool.version}) — 갱신: {tool.install}")
    return _line(True, f"{tool.name} {found}")


def _check_gh_login() -> bool:
    if external.version_of(["gh", "--version"]) is None:
        return _line(False, "gh 로그인 — gh가 없어 확인하지 못했습니다")
    done = external.run(["gh", "auth", "status"])
    return _line(done.returncode == 0, "gh 로그인" + ("" if done.returncode == 0 else
                                                       " 안 됨 — 실행: gh auth login"))


def content_tools(manifest: dict) -> tuple[list[Tool], list[str]]:
    """content.toml [tools]에서 0~4장 도구와, 형식이 틀린 항목의 오류를 돌려준다."""
    tools, errors = [], []
    for name, spec in manifest.get("tools", {}).items():
        try:
            tool = Tool(name, list(spec["cmd"]), spec.get("version", ""), spec["install"])
            chapter = int(spec["chapter"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"content.toml [tools.{name}] 형식 오류(cmd·install·chapter 필요)")
            continue
        if chapter <= DOCTOR_LAST_CHAPTER:
            tools.append(tool)
    return tools, errors


def _content_manifest() -> dict:
    """받아 둔 콘텐츠의 content.toml. 아직 없으면 빈 표(엔진 쪽만 검사한다)."""
    config.ensure_config()
    try:
        return content.read_manifest(content.content_root(config.load_config()))
    except config.EnvError:
        print(ui.paint("콘텐츠가 아직 없어 엔진 쪽만 검사합니다. 받으려면 quest update", "dim"))
        return {}


def cmd_doctor(game: None, rest: list[str]) -> int:
    results = _check_runtime() + [_check_tool(t) for t in ENGINE_TOOLS] + [_check_gh_login()]
    tools, errors = content_tools(_content_manifest())
    results += [_check_tool(t) for t in tools] + [_line(False, e) for e in errors]
    print(f"\n점검 {len(results)}개 중 {sum(results)}개 통과")
    return OK if all(results) else ENV
