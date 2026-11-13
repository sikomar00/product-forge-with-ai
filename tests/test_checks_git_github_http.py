"""체크 프리미티브 git·github·http 시험(M1-01). git은 읽기 전용(NF-02)도 본다."""

import json
import subprocess
import threading
import urllib.error
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from quest import external
from quest.checks import git, github, http
from quest.core.mission import CheckEnvError, Ctx


def _ctx(workdir: Path, gh: object = None) -> Ctx:
    return Ctx(workdir=workdir, config={}, lab="", gh=gh, now=datetime.now(UTC))


def _run(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                          capture_output=True, text=True, check=True).stdout


# ───────────── git ─────────────


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _run(tmp_path, "init", "--quiet", "--initial-branch=main")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")
    _run(tmp_path, "add", ".")
    _run(tmp_path, "commit", "--quiet", "-m", "feat: 첫 화면")
    _run(tmp_path, "branch", "fix/login")
    _run(tmp_path, "remote", "add", "origin", "https://github.com/me/opsdesk.git")
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    return tmp_path


def _state(repo: Path) -> tuple[str, str, bytes]:
    return (_run(repo, "status", "--porcelain"), _run(repo, "rev-parse", "HEAD"),
            (repo / ".git" / "index").read_bytes())


def test_git_primitives_are_read_only(repo: Path) -> None:
    ctx = _ctx(repo)
    before = _state(repo)
    assert git.is_repo(ctx).ok and git.branch(ctx) == "main"
    assert git.branches(ctx) == ["fix/login", "main"]
    assert git.is_clean(ctx).ok  # .env는 무시된다
    assert git.subjects(ctx) == ["feat: 첫 화면"] and git.has_commit(ctx, r"^feat:").ok
    assert git.is_tracked(ctx, "app.py").ok and not git.is_tracked(ctx, ".env").ok
    assert git.is_ignored(ctx, ".env").ok and not git.is_ignored(ctx, "app.py").ok
    assert git.remote_url(ctx) == "https://github.com/me/opsdesk.git"
    assert git.remote_url(ctx, "upstream") is None
    assert _state(repo) == before  # 상태·HEAD·인덱스 파일까지 그대로


def test_git_on_dirty_and_non_repo(repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    (repo / "app.py").write_text("print(2)\n", encoding="utf-8")
    assert not git.is_clean(_ctx(repo)).ok
    empty = _ctx(tmp_path_factory.mktemp("empty"))
    assert not git.is_repo(empty).ok and git.branch(empty) is None and git.subjects(empty) == []


# ───────────── github ─────────────

RECORDS = {
    "repos/me/opsdesk": {"visibility": "public", "default_branch": "main"},
    "repos/me/opsdesk/branches/main/protection": {"__missing__": True},
    "repos/me/opsdesk/rulesets": [{"name": "main 보호", "enforcement": "active"}],
}


def test_github_replay() -> None:
    ctx = _ctx(Path("."), github.GhReplay(RECORDS))
    assert github.value(ctx, "repos/me/opsdesk", ("visibility",)) == "public"
    assert github.value(ctx, "repos/me/opsdesk/rulesets", (0, "enforcement")) == "active"
    assert github.value(ctx, "repos/me/opsdesk", ("nope",)) is github.MISSING
    assert github.exists(ctx, "repos/me/opsdesk").ok
    assert not github.exists(ctx, "repos/me/opsdesk/branches/main/protection").ok
    with pytest.raises(CheckEnvError, match="기록 재생에 없는"):
        github.value(ctx, "repos/other/x")


def test_github_recorder_saves_what_live_returned(tmp_path: Path) -> None:
    answers = {"repos/me/opsdesk": {"visibility": "private"}, "repos/me/gone": github.MISSING}
    recorder = github.GhRecorder(answers.__getitem__)
    ctx = _ctx(tmp_path, recorder)
    assert github.value(ctx, "repos/me/opsdesk", ("visibility",)) == "private"
    assert not github.exists(ctx, "repos/me/gone").ok
    recorder.save(tmp_path / "gh.json")
    replay = _ctx(tmp_path, github.GhReplay.load(tmp_path / "gh.json"))
    assert github.value(replay, "repos/me/opsdesk", ("visibility",)) == "private"
    assert not github.exists(replay, "repos/me/gone").ok


@pytest.mark.parametrize(
    ("code", "stdout", "stderr", "expected"),
    [(0, '{"a": 1}', "", {"a": 1}), (1, "", "gh: Not Found (HTTP 404)", github.MISSING)],
)
def test_github_live(monkeypatch: pytest.MonkeyPatch, code: int, stdout: str, stderr: str,
                     expected: object) -> None:
    monkeypatch.setattr(external, "run", lambda args, cwd=None:
                        subprocess.CompletedProcess(args, code, stdout, stderr))
    assert github.GhLive()("repos/me/x") == expected


def test_github_live_auth_problem_is_env_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(external, "run", lambda args, cwd=None:
                        subprocess.CompletedProcess(args, 1, "", "HTTP 401: Bad credentials"))
    with pytest.raises(CheckEnvError):
        github.GhLive()("repos/me/x")


def test_github_without_caller_is_env_error() -> None:
    with pytest.raises(CheckEnvError):
        github.exists(_ctx(Path(".")), "repos/me/x")


# ───────────── http ─────────────


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - http.server 규칙
        if self.path == "/health":
            body, status = json.dumps({"status": "ok", "db": {"up": True}}), 200
        else:
            body, status = json.dumps({"error": "not found"}), 404
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> str:
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_http_status_and_json(server: str) -> None:
    ctx = _ctx(Path("."))
    assert http.status_is(ctx, f"{server}/health", 200).ok
    assert http.status_is(ctx, f"{server}/nope", 404).ok
    assert http.json_value(ctx, f"{server}/health", ("db", "up")) is True
    assert http.json_value(ctx, f"{server}/health", ("nope",)) is http.MISSING


def test_http_unreachable_server_fails_not_env_error() -> None:
    result = http.status_is(_ctx(Path(".")), "http://127.0.0.1:9/health", 200)
    assert not result.ok and result.detail == "HTTP 응답 없음"


def test_http_certificate_problem_is_env_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import ssl

    def bad(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError(ssl.SSLError("CERTIFICATE_VERIFY_FAILED"))

    monkeypatch.setattr(http.urllib.request, "urlopen", bad)
    with pytest.raises(CheckEnvError, match="인증서"):
        http.get(_ctx(Path(".")), "https://example.com")
