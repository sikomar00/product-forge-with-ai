"""맥 준비 점검 스크립트(scripts/check-mac.sh) 시험: 가짜 명령으로 맥을 흉내 낸다."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check-mac.sh"


def _bash() -> str | None:
    """Windows에서는 WSL bash가 아니라 Git의 bash를 쓴다(임시 폴더 경로가 통해야 한다)."""
    if sys.platform == "win32":
        git = shutil.which("git")
        # Git\bin\bash.exe는 PATH 앞에 /usr/bin을 끼워 가짜 uname을 가린다.
        # 그 안의 진짜 bash(Git\usr\bin\bash.exe)를 쓴다.
        for folder in Path(git).resolve().parents if git else ():  # Git\cmd 또는 Git\mingw64\bin
            if (folder / "usr" / "bin" / "bash.exe").exists():
                return str(folder / "usr" / "bin" / "bash.exe")
        return None
    return shutil.which("bash")


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="bash가 없다")

STUBS = {
    "uname": 'case "$1" in -s) echo Darwin;; -m) echo arm64;; *) echo Darwin;; esac',
    "xcode-select": "echo /Library/Developer/CommandLineTools",
    "brew": "echo Homebrew 4.5.0",
    "gh": 'case "$1" in --version) echo "gh version 2.80.0";;'
          ' auth) exit "${GH_AUTH_EXIT:-0}";; esac',
    "uv": 'case "$1" in --version) echo "uv ${UV_VERSION:-0.13.6}";; python) exit 0;; esac',
    "orb": "echo Version: 1.10.0",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                   check=True, capture_output=True)


@pytest.fixture
def mac(tmp_path: Path) -> dict:
    """가짜 명령 폴더, 엔진 리포, 빈 홈. 바꾸지 않는지 보려고 엔진 리포 상태도 돌려준다."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in STUBS.items():
        (stubs / name).write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8", newline="\n")
        (stubs / name).chmod(0o755)
    repo = tmp_path / "product-forge-with-ai"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (repo / ".venv").mkdir()
    _git(repo, "init", "-q", "--initial-branch=engine/windows-setup")
    home = tmp_path / "home"
    home.mkdir()
    return {"stubs": stubs, "repo": repo, "home": home}


def _run(mac: dict, **env: str) -> subprocess.CompletedProcess[str]:
    git_dir = str(Path(shutil.which("git")).parent)
    path = os.pathsep.join([str(mac["stubs"]), git_dir, os.environ.get("PATH", "")])
    full_env = {**os.environ, "PATH": path, "HOME": str(mac["home"]), **env}
    if "QUEST_S1_REPO" not in env:  # 개발자 컴퓨터의 S1 설정이 시험에 새지 않게
        full_env.pop("QUEST_S1_REPO", None)
    script = SCRIPT.as_posix()
    return subprocess.run([BASH, script, mac["repo"].as_posix()], env=full_env,
                          capture_output=True, text=True, encoding="utf-8", check=False)


def test_ready_mac_passes(mac: dict) -> None:
    s1 = os.environ.get("QUEST_S1_REPO")
    if not s1:
        pytest.skip("S1 리포(QUEST_S1_REPO)가 있어야 '모두 준비' 경우를 볼 수 있다")
    done = _run(mac, QUEST_S1_REPO=Path(s1).as_posix())
    assert done.returncode == 0, done.stdout
    assert "✅ macOS" in done.stdout and "✅ uv 0.13.6" in done.stdout
    assert "✅ OrbStack(orb) 1.10.0" in done.stdout and "✅ S1 리포(고정 커밋)" in done.stdout
    assert "모두 준비됐습니다" in done.stdout


def test_missing_items_are_listed_with_install_commands(mac: dict) -> None:
    (mac["stubs"] / "orb").unlink()
    shutil.rmtree(mac["repo"] / ".venv")
    done = _run(mac, GH_AUTH_EXIT="1", UV_VERSION="0.12.0")
    out = done.stdout
    assert done.returncode == 1
    assert "❌ OrbStack(orb) 없음" in out and "❌ gh 로그인 안 됨" in out
    assert "❌ uv 0.12.0 (필요: 0.13.6 이상)" in out and "❌ QUEST_S1_REPO 없음" in out
    todo = out[out.index("필요한 것"):]
    for step in ("brew install --cask orbstack", "gh auth login", "uv self update", "uv sync"):
        assert step in todo
    assert "ℹ️  게임 설정 파일은 아직 없다" in out  # 아직 없어도 되는 것은 ❌가 아니다


def test_missing_engine_repo_and_wrong_branch(mac: dict, tmp_path: Path) -> None:
    _git(mac["repo"], "checkout", "-q", "-b", "feature/x")
    done = _run(mac)
    assert "❌ 브랜치가 feature/x" in done.stdout
    mac["repo"] = tmp_path / "nowhere"
    done = _run(mac)
    assert "❌ 엔진 리포 없음" in done.stdout and "git clone" in done.stdout


def test_check_changes_nothing(mac: dict) -> None:
    before = sorted(p.relative_to(mac["repo"]) for p in mac["repo"].rglob("*"))
    _run(mac)
    after = sorted(p.relative_to(mac["repo"]) for p in mac["repo"].rglob("*"))
    assert before == after and list(mac["home"].iterdir()) == []


def test_without_xcode_tools_git_stub_is_not_run(mac: dict, tmp_path: Path) -> None:
    """CLT가 없는 맥의 /usr/bin/git은 실행만 해도 설치 창을 띄운다. 이 스크립트는 부르지 않는다."""
    (mac["stubs"] / "xcode-select").write_text("#!/usr/bin/env bash\nexit 2\n", encoding="utf-8",
                                              newline="\n")
    done = _run(mac)
    assert "❌ Xcode Command Line Tools 없음" in done.stdout
    # 시험 환경의 git은 /usr/bin/git이 아니라서 그대로 점검된다(가짜로 /usr/bin을 바꿀 수 없다)
    assert "✅ git" in done.stdout or "git은 Xcode" in done.stdout
