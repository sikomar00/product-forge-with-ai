"""리뷰봇 시험(M1-07): diff 읽기, 지적 찾기, 리뷰 코멘트 달기(gh 호출은 가짜)."""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import Quest

from quest import external
from quest.core.config import EnvError
from quest.core.mission import ReviewRule
from quest.labs import reviewbot
from quest.labs.reviewbot import Finding

DIFF = """diff --git a/app/api.py b/app/api.py
index 1111111..2222222 100644
--- a/app/api.py
+++ b/app/api.py
@@ -10,3 +10,5 @@ def list_tickets():
     rows = db.all()
+    print(rows)
+    password = "1234"
     return rows
@@ -40,2 +42,3 @@ def close():
     pass
+    print("closed")
diff --git a/README.md b/README.md
new file mode 100644
--- /dev/null
+++ b/README.md
@@ -0,0 +1,2 @@
+# OpsDesk
+print 하지 마세요
diff --git a/old.py b/old.py
deleted file mode 100644
--- a/old.py
+++ /dev/null
@@ -1 +0,0 @@
-print(1)
"""

RULES = (
    ReviewRule("*.py", r"\bprint\(", "디버그 print는 지우고 로그를 쓰세요."),
    ReviewRule("app/*.py", r"password\s*=\s*['\"]", "비밀번호를 코드에 쓰지 마세요."),
)


def test_added_lines_use_new_file_line_numbers() -> None:
    assert reviewbot.added_lines(DIFF) == [
        ("app/api.py", 11, "    print(rows)"),
        ("app/api.py", 12, '    password = "1234"'),
        ("app/api.py", 43, '    print("closed")'),
        ("README.md", 1, "# OpsDesk"),
        ("README.md", 2, "print 하지 마세요"),
    ]


def test_findings_once_per_rule_per_file() -> None:
    assert reviewbot.findings(DIFF, RULES) == [
        Finding("app/api.py", 11, "디버그 print는 지우고 로그를 쓰세요."),
        Finding("app/api.py", 12, "비밀번호를 코드에 쓰지 마세요."),
    ]  # 43번 줄의 print는 같은 규칙이라 다시 달지 않고, README는 *.py가 아니다


def test_post_review_sends_one_comment_review(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = {}

    def fake(args: list[str], cwd: Path | None = None,
             timeout: int = 60) -> subprocess.CompletedProcess[str]:
        sent["args"] = args
        sent["payload"] = json.loads(Path(args[-1]).read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(args, 0, "{}", "")

    monkeypatch.setattr(external, "run", fake)
    reviewbot.post_review("me/opsdesk", 7, reviewbot.findings(DIFF, RULES))
    assert sent["args"][:5] == ["gh", "api", "--method", "POST", "repos/me/opsdesk/pulls/7/reviews"]
    payload = sent["payload"]
    assert payload["event"] == "COMMENT" and payload["body"] == "🤖 리뷰봇: 2곳을 봐 주세요."
    assert payload["comments"][1] == {"path": "app/api.py", "line": 12, "side": "RIGHT",
                                      "body": "🤖 리뷰봇: 비밀번호를 코드에 쓰지 마세요."}


def test_gh_failures_are_env_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(external, "run", lambda args, cwd=None, timeout=60:
                        subprocess.CompletedProcess(args, 1, "", "HTTP 422"))
    with pytest.raises(EnvError, match="PR #7"):
        reviewbot.pr_diff("me/opsdesk", 7)
    with pytest.raises(EnvError, match="리뷰 코멘트"):
        reviewbot.post_review("me/opsdesk", 7, [])


# ───────────── 채점 직전 한 번(quest check) ─────────────

DIFF_PRINT = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,1 +1,2 @@
 x = 1
+print(x)
"""


@pytest.fixture
def fake_gh(monkeypatch: pytest.MonkeyPatch) -> dict:
    """gh 호출을 흉내 낸다. state['reviews']에 단 리뷰가 쌓인다."""
    state = {"pr": "7", "reviews": [], "calls": []}

    def run(args: list[str], cwd: Path | None = None,
            timeout: int = 60) -> subprocess.CompletedProcess[str]:
        state["calls"].append(args[:3])
        out = ""
        if args[:3] == ["gh", "repo", "view"]:
            out = "me/opsdesk"
        elif args[:3] == ["gh", "pr", "list"]:
            out = state["pr"]
        elif args[:3] == ["gh", "pr", "diff"]:
            out = DIFF_PRINT
        elif args[-2:-1] == ["--input"]:
            state["reviews"].append(json.loads(Path(args[-1]).read_text(encoding="utf-8")))
        elif args[:2] == ["gh", "api"]:
            out = json.dumps([{"body": r["body"]} for r in state["reviews"]])
        return subprocess.CompletedProcess(args, 0, out, "")

    monkeypatch.setattr(external, "run", run)
    return state


def test_bot_reviews_once_before_check(game: Path, quest: Quest, answers: list[str],
                                       fake_gh: dict) -> None:
    code, out = quest("check", "1-1")
    assert "🤖 리뷰봇이 PR #7에 코멘트 1개를 달았습니다" in out and code == 1  # 채점은 따로
    assert fake_gh["reviews"][0]["comments"][0]["body"] == "🤖 리뷰봇: 디버그 print를 지우세요"
    code, out = quest("check", "1-1")
    assert "리뷰봇이" not in out and len(fake_gh["reviews"]) == 1  # 이미 단 PR은 건너뛴다


def test_bot_does_nothing_without_open_pr(game: Path, quest: Quest, fake_gh: dict) -> None:
    fake_gh["pr"] = ""
    code, out = quest("check", "1-1")
    assert "리뷰봇" not in out and fake_gh["reviews"] == []


def test_bot_failure_does_not_block_grading(
    game: Path, quest: Quest, answers: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(workdir: Path, rules: tuple) -> None:
        raise EnvError("gh 명령을 찾지 못했습니다.")

    monkeypatch.setattr(reviewbot, "run_once", broken)
    (game / "fixed.txt").write_text("x", encoding="utf-8")
    answers.append("2")  # 🚀 설명 게이트
    code, out = quest("check", "1-1")
    assert "⚠️ 리뷰봇을 돌리지 못했습니다" in out and code == 0 and "✅ 1." not in out  # 감사 미션은 개수만
    assert "체크 1/1 통과" in out


def test_mission_without_rules_never_calls_bot(game: Path, quest: Quest, fake_gh: dict) -> None:
    quest("check", "0-1")
    assert not any(c[:2] == ["gh", "pr"] for c in fake_gh["calls"])
