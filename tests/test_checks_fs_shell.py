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
    assert shell.succeeds(_ctx(work), ["git", "--version"]).ok  # 실제 실행


def _fake_output(monkeypatch: pytest.MonkeyPatch, code: int, stdout: str) -> None:
    monkeypatch.setattr(external, "run", lambda args, cwd=None, timeout=60:
                        subprocess.CompletedProcess(args, code, stdout, ""))


def test_shell_output_equals_and_json(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(work)
    _fake_output(monkeypatch, 0, "644" + chr(10))  # 줄바꿈이 붙은 출력도 앞뒤 공백을 빼고 비교
    assert shell.output_equals(ctx, ["stat", "-c", "%a", "a.sh"], "644").ok
    assert not shell.output_equals(ctx, ["stat", "-c", "%a", "a.sh"], "755").ok
    _fake_output(monkeypatch, 0, '[{"ifname": "eth0", "mtu": 1500}]')
    assert shell.json_value(ctx, ["ip", "-j", "addr", "show"], (0, "mtu")) == 1500
    assert shell.json_value(ctx, ["ip", "-j", "addr", "show"], (1,)) is shell.MISSING
    _fake_output(monkeypatch, 0, "not json")
    assert shell.json_value(ctx, ["lsblk", "-J"], ()) is shell.MISSING


@pytest.mark.parametrize("args", [["date", "+%s"], ["date", "-u", "+%Y"], ["hostname"],
                                  ["hostname", "-f"], ["journalctl", "-u", "nginx", "-n", "5"],
                                  ["ss", "-tlnp"], ["systemctl", "is-active", "sshd"],
                                  ["git", "--version"], ["go", "version"]])
def test_allowed_read_only_forms(args: list[str]) -> None:
    assert shell.is_read_only(args)


@pytest.mark.parametrize("args", [["date", "-s", "2000-01-01"], ["hostname", "newname"],
                                  ["ip", "addr", "add", "1.2.3.4/24", "dev", "eth0"],
                                  ["ip", "-j", "route", "del", "default"],
                                  ["journalctl", "--vacuum-size=1K"], ["ss", "-K", "dst", "x"],
                                  ["rm", "version"], ["mkdir", "version"]])
def test_state_changing_forms_are_refused(args: list[str]) -> None:
    assert not shell.is_read_only(args)


def test_shell_without_workdir_runs_in_empty_folder(tmp_path: Path) -> None:
    """리포를 만들기 전에도 폴더와 상관없는 명령은 되고, 상대 경로는 엉뚱하게 통과하지 않는다."""
    ctx = _ctx(tmp_path / "not-cloned-yet")
    assert shell.succeeds(ctx, ["git", "--version"]).ok
    assert not shell.succeeds(ctx, ["ls", "pyproject.toml"]).ok


@pytest.mark.parametrize("args", [["ss", "-tK", "dst", "1.2.3.4"], ["ss", "-nKt"], []])
def test_more_refused_forms(args: list[str]) -> None:
    assert not shell.is_read_only(args)
    with pytest.raises(ValueError, match="읽기 전용"):
        shell.check_read_only(args)


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
    assert ssh.output_equals(_ctx(work), ["systemctl", "is-active", "sshd"], "active").ok
    assert calls == [["orb", "-m", "pf-lab", "systemctl", "is-active", "sshd"]]
    with pytest.raises(ValueError):
        ssh.run(_ctx(work), ["reboot"])


def test_ssh_without_orb_is_env_error(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(args: list[str], cwd: Path | None = None) -> None:
        raise external.EnvError("orb 명령을 찾지 못했습니다.")

    monkeypatch.setattr(external, "run", missing)
    with pytest.raises(CheckEnvError, match="랩 VM"):
        ssh.run(_ctx(work), ["uname", "-a"])
