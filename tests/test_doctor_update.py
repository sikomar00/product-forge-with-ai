"""quest doctor·update 시험(M1-02, M1-03, IA-12, IA-18).

update는 로컬 git 리포를 콘텐츠 리포로 써서 처음부터 끝까지 돌린다(Plan T1-0).
"""

import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest
from conftest import FAKE, Quest

from quest import external
from quest.commands import doctor

# ───────────── doctor ─────────────


def test_content_tools_reads_chapters_zero_to_four() -> None:
    manifest = {"tools": {
        "jq": {"cmd": ["jq", "--version"], "version": ">=1.7", "install": "brew install jq",
               "chapter": 1},
        "docker": {"cmd": ["docker", "--version"], "install": "brew install docker", "chapter": 9},
        "bad": {"cmd": ["x"]},
    }}
    tools, errors = doctor.content_tools(manifest)
    assert [t.name for t in tools] == ["jq"] and tools[0].version == ">=1.7"
    assert len(errors) == 1 and "tools.bad" in errors[0]


def test_doctor_reports_each_tool(
    game: Path, quest: Quest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(doctor.sys, "platform", "darwin")  # 맥에서는 orb도 검사한다
    found = {"uv": "0.13.6", "git": "2.55.0", "gh": "2.102.0", "orb": None, "jq": "1.6"}
    monkeypatch.setattr(external, "version_of", lambda cmd: found.get(cmd[0]))
    monkeypatch.setattr(
        external, "run", lambda args, cwd=None: subprocess.CompletedProcess(args, 0, "", "")
    )
    monkeypatch.setattr(doctor, "_content_manifest", lambda: {"tools": {"jq": {
        "cmd": ["jq", "--version"], "version": ">=1.7", "install": "brew install jq",
        "chapter": 1}}})
    code, out = quest("doctor")
    assert code == 3
    assert "✅ git 2.55.0" in out and "❌ orb 없음 — 설치: brew install --cask orbstack" in out
    assert "❌ jq 1.6 (필요: >=1.7) — 갱신: brew install jq" in out and "✅ gh 로그인" in out
    assert "점검 8개 중 6개 통과" in out


def test_doctor_all_green_exits_zero(
    game: Path, quest: Quest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(external, "version_of", lambda cmd: "9.9.9")
    monkeypatch.setattr(
        external, "run", lambda args, cwd=None: subprocess.CompletedProcess(args, 0, "", "")
    )
    monkeypatch.setattr(doctor, "_content_manifest", lambda: {})
    assert quest("doctor")[0] == 0


# ───────────── update ─────────────


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture
def origin(tmp_path: Path) -> Path:
    """가짜 콘텐츠로 만든 '원격' 콘텐츠 리포(0장만 있는 상태로 시작)."""
    repo = tmp_path / "origin"
    shutil.copytree(FAKE, repo)
    (repo / "content" / "ch01_fake.py").unlink()
    manifest = repo / "content.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        'testing = ["m_f0000011"]', 'testing = ["m_f0000011"]  # 1장은 다음 커밋에서'),
        encoding="utf-8")
    _git(repo, "init", "--quiet", "--initial-branch=main")
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "0장")
    return repo


@pytest.fixture
def setup(game: Path, origin: Path, tmp_path: Path) -> Path:
    """설정의 콘텐츠 리포를 origin, 받을 위치를 home/content로 바꾼다. 받을 위치를 돌려준다."""
    target = tmp_path / "home" / "content"
    cfg = game.parent / "config.toml"
    text = cfg.read_text(encoding="utf-8")
    text = text.replace('repo = "fake/fake"', f'repo = "{origin.as_posix()}"')
    text = text.replace(f'path = "{FAKE.as_posix()}"', f'path = "{target.as_posix()}"')
    cfg.write_text(text, encoding="utf-8")
    return target


def _events(game: Path) -> list[tuple]:
    conn = sqlite3.connect(game.parent / "home" / "state.db")
    rows = conn.execute("SELECT kind, payload FROM events WHERE kind = 'content_updated'")
    return rows.fetchall()


def test_update_clones_then_reports_new_missions(
    game: Path, quest: Quest, origin: Path, setup: Path
) -> None:
    code, out = quest("update")
    assert code == 0 and "바뀐 장: 0장 · 새 미션 5개" in out
    assert (setup / "content" / "ch00_fake.py").exists()
    head = _git(origin, "rev-parse", "--short", "HEAD")
    assert _events(game)[0][1] == f'{{"from": null, "to": "{head}", "new_missions": 5}}'
    assert "현재 미션: 0-1" in quest()[1]  # 받은 콘텐츠로 게임이 돈다

    assert quest("update")[1].strip() == "이미 최신 콘텐츠입니다."

    shutil.copy(FAKE / "content" / "ch01_fake.py", origin / "content" / "ch01_fake.py")
    _git(origin, "add", ".")
    _git(origin, "commit", "--quiet", "-m", "1장")
    code, out = quest("update")
    assert code == 0 and "바뀐 장: 1장 · 새 미션 4개" in out
    assert "가짜 감사" not in out and "결함을 고치세요" not in out  # 콘텐츠 글은 내보내지 않는다


def test_update_refuses_content_for_newer_engine(
    game: Path, quest: Quest, origin: Path, setup: Path
) -> None:
    quest("update")
    manifest = origin / "content.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        '">=0.1,<0.2"', '">=0.9"'), encoding="utf-8")
    _git(origin, "commit", "--quiet", "-am", "엔진 0.9 필요")
    code, out = quest("update")
    assert code == 3 and "엔진을 갱신하세요" in out
    local = (setup / "content.toml").read_text(encoding="utf-8")
    assert '">=0.1,<0.2"' in local  # 합치지 않았다
    assert len(_events(game)) == 1


def test_first_update_refuses_content_for_newer_engine(
    game: Path, quest: Quest, origin: Path, setup: Path
) -> None:
    manifest = origin / "content.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        '">=0.1,<0.2"', '">=0.9"'), encoding="utf-8")
    _git(origin, "commit", "--quiet", "-am", "엔진 0.9 필요")
    code, out = quest("update")
    assert code == 3 and "엔진을 갱신하세요" in out
    assert not setup.exists()  # 받다 만 것을 남기지 않아, 엔진을 갱신하면 다시 받을 수 있다


def test_first_update_of_empty_repo(game: Path, quest: Quest, setup: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    _git(tmp_path, "init", "--quiet", "--bare", str(empty))
    cfg = game.parent / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        (tmp_path / "origin").as_posix(), empty.as_posix()), encoding="utf-8")
    code, out = quest("update")
    assert code == 3 and "아직 비어 있습니다" in out
    assert not setup.exists()


def test_update_reports_unreachable_repo(game: Path, quest: Quest, setup: Path) -> None:
    cfg = game.parent / "config.toml"
    text = cfg.read_text(encoding="utf-8")
    start = text.index('repo = "') + len('repo = "')
    end = text.index('"', start)
    cfg.write_text(text[:start] + "file:///no/such/repo" + text[end:], encoding="utf-8")
    code, out = quest("update")
    assert code == 3 and "git clone이 실패했습니다" in out


def test_update_needs_repo_in_config(game: Path, quest: Quest) -> None:
    cfg = game.parent / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        'repo = "fake/fake"', 'repo = "<GitHub 사용자 이름>/product-forge-content"'),
        encoding="utf-8")
    code, out = quest("update")
    assert code == 3 and "[content] repo" in out


def test_doctor_skips_orb_off_macos(game: Path, quest: Quest,
                                    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor.sys, "platform", "win32")
    monkeypatch.setattr(external, "version_of", lambda cmd: "9.9.9")
    monkeypatch.setattr(
        external, "run", lambda args, cwd=None: subprocess.CompletedProcess(args, 0, "", "")
    )
    monkeypatch.setattr(doctor, "_content_manifest", lambda: {})
    code, out = quest("doctor")
    assert code == 0 and "macOS 전용이라" in out and "orb 없음" not in out


def test_doctor_bad_version_format_marks_only_that_tool(
    game: Path, quest: Quest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(external, "version_of", lambda cmd: "1.0")
    monkeypatch.setattr(
        external, "run", lambda args, cwd=None: subprocess.CompletedProcess(args, 0, "", "")
    )
    monkeypatch.setattr(doctor, "_content_manifest", lambda: {"tools": {"jq": {
        "cmd": ["jq", "--version"], "version": "최신", "install": "brew install jq",
        "chapter": 1}}})
    code, out = quest("doctor")
    assert code == 3 and "jq: 허용 버전 형식이 틀렸습니다" in out and "점검" in out


def test_update_refused_during_incident(game: Path, quest: Quest, setup: Path,
                                        answers: list[str]) -> None:
    quest("update")
    quest("mission")  # 0-1 시작(장애 행의 외래 키용)
    conn = sqlite3.connect(game.parent / "home" / "state.db", isolation_level=None)
    conn.execute("INSERT INTO incidents (mission_key, source, status, injected_at, snapshot_ref)"
                 " VALUES ('m_f0000001', 'mission', 'active', '2026-01-01T00:00:00Z', 's')")
    conn.close()
    code, out = quest("update")
    assert code == 3 and "진행 중인 장애" in out
