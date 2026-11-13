"""체크 프리미티브 fs·shell·ssh 시험(M1-01). 읽기 전용(NF-02)도 본다."""

import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from quest import external
from quest.checks import fs, shell, ssh
from quest.core.mission import CheckEnvError, Ctx


def _ctx(workdir: Path) -> Ctx:
    return Ctx(workdir=workdir, config={}, lab="pf-lab", gh=None, now=datetime.now(UTC))


def _snapshot(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture
def work(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("# 제목\n본문 v2\n", encoding="utf-8")
    (tmp_path / "docs" / "b.md").write_text("b", encoding="utf-8")
    (tmp_path / "conf.json").write_text('{"server": {"port": 8080, "tags": ["a"]}, "x": null}',
                                        encoding="utf-8")
    return tmp_path


def test_fs_primitives(work: Path) -> None:
    ctx = _ctx(work)
    before = _snapshot(work)
    assert fs.exists(ctx, "docs/a.md").ok and not fs.exists(ctx, "nope.txt").ok
    assert fs.exists(ctx, "nope.txt").detail == "nope.txt 없음"
    assert fs.is_dir(ctx, "docs").ok and not fs.is_dir(ctx, "conf.json").ok
    assert fs.contains(ctx, "docs/a.md", r"^본문 v\d$").ok
    assert not fs.contains(ctx, "docs/a.md", "없는 글").ok and not fs.contains(ctx, "x.md", ".").ok
    assert fs.json_value(ctx, "conf.json", ("server", "port")) == 8080
    assert fs.json_value(ctx, "conf.json", ("server", "tags", 0)) == "a"
    assert fs.json_value(ctx, "conf.json", ("x",)) is None  # JSON null
    assert fs.json_value(ctx, "conf.json", ("missing",)) is fs.MISSING
    assert fs.json_value(ctx, "nope.json", ()) is fs.MISSING
    assert fs.count(ctx, "docs", "*.md") == 2 and fs.count(ctx, "nope", "*") == 0
    assert not fs.is_executable(ctx, "nope.sh").ok
    assert _snapshot(work) == before  # 읽기 전용


def test_fs_absolute_and_home_paths(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(work / "docs")
    assert fs.exists(ctx, str(work / "conf.json")).ok
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(work))
    assert fs.exists(ctx, "~/conf.json").ok


def test_shell_runs_read_only_commands(work: Path) -> None:
    ctx = _ctx(work)
    assert shell.succeeds(ctx, ["git", "--version"]).ok
    assert shell.output_matches(ctx, ["git", "--version"], r"git version \d+").ok
    assert not shell.output_matches(ctx, ["git", "--version"], "mercurial").ok


@pytest.mark.parametrize("args", [["rm", "-rf", "."], ["find", ".", "-delete"],
                                  ["systemctl", "restart", "nginx"], ["git", "push"]])
def test_shell_refuses_commands_that_change_state(work: Path, args: list[str]) -> None:
    with pytest.raises(ValueError, match="읽기 전용"):
        shell.run(_ctx(work), args)


def test_shell_missing_program_is_env_error(work: Path) -> None:
    with pytest.raises(CheckEnvError):
        shell.run(_ctx(work), ["no-such-tool-xyz", "--version"])


def test_shell_nonzero_exit_fails(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(external, "run", lambda args, cwd=None:
                        subprocess.CompletedProcess(args, 3, "", "boom"))
    result = shell.succeeds(_ctx(work), ["systemctl", "is-active", "nginx"])
    assert not result.ok and result.detail == "종료 코드 3"


def test_ssh_runs_inside_lab_machine(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "active\n", "")

    monkeypatch.setattr(external, "run", fake)
    assert ssh.output_matches(_ctx(work), ["systemctl", "is-active", "sshd"], "^active$").ok
    assert calls == [["orb", "-m", "pf-lab", "systemctl", "is-active", "sshd"]]
    with pytest.raises(ValueError):
        ssh.run(_ctx(work), ["reboot"])


def test_ssh_without_orb_is_env_error(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(args: list[str], cwd: Path | None = None) -> None:
        raise external.EnvError("orb 명령을 찾지 못했습니다.")

    monkeypatch.setattr(external, "run", missing)
    with pytest.raises(CheckEnvError, match="랩 VM"):
        ssh.run(_ctx(work), ["uname", "-a"])
