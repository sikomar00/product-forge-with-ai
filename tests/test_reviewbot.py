"""리뷰봇 시험(M1-07): diff 읽기, 지적 찾기, 리뷰 코멘트 달기(gh 호출은 가짜)."""

import json
import subprocess
from pathlib import Path

import pytest

from quest import external
from quest.core.config import EnvError
from quest.labs import reviewbot
from quest.labs.reviewbot import Finding, ReviewRule

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
