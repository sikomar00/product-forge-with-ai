"""2장 리뷰봇(M1-07, Spec "리뷰봇"): 학습자 PR의 diff에서 지적할 곳을 찾아 리뷰 코멘트를 단다.

GitHub Actions가 아니라 게임이 로컬에서 `gh`로 단다. 지적 목록(ReviewRule)은 콘텐츠에 있어서
공개 리포(opsdesk)에 올라가지 않는다. 코멘트는 '🤖 리뷰봇:'으로 시작하고 학습자 계정으로 달린다.

shortcut: 언제 리뷰봇을 돌릴지(명령·시점)는 2장 콘텐츠를 만들 때 정한다. 체크는 읽기 전용이라
체크 안에서 코멘트를 달 수는 없다(ADR-0004).
"""

import fnmatch
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from quest import external
from quest.core.config import EnvError

PREFIX = "🤖 리뷰봇: "
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class ReviewRule:
    """path(glob)에 맞는 파일에서, 새로 더한 줄이 pattern(정규식)에 맞으면 message를 단다."""

    path: str
    pattern: str
    message: str


@dataclass(frozen=True)
class Finding:
    path: str
    line: int  # 새 파일 기준 줄 번호(GitHub 리뷰 코멘트의 RIGHT 쪽)
    message: str


def added_lines(diff: str) -> list[tuple[str, int, str]]:
    """unified diff에서 새로 더한 줄: (파일, 새 파일 줄 번호, 내용)."""
    found, path, line = [], None, 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].removeprefix("b/") if raw[4:] != "/dev/null" else None
        elif hunk := _HUNK.match(raw):
            line = int(hunk[1])
        elif raw.startswith("+") and path is not None:
            found.append((path, line, raw[1:]))
            line += 1
        elif raw.startswith(" "):
            line += 1
    return found


def findings(diff: str, rules: tuple[ReviewRule, ...]) -> list[Finding]:
    """규칙마다 파일당 첫 번째로 걸린 줄에만 단다(같은 지적이 줄마다 반복되지 않게)."""
    result, seen = [], set()
    for path, line, text in added_lines(diff):
        for number, rule in enumerate(rules):
            hit = fnmatch.fnmatch(path, rule.path) and re.search(rule.pattern, text)
            if hit and (number, path) not in seen:
                seen.add((number, path))
                result.append(Finding(path, line, rule.message))
    return result


def pr_diff(repo: str, pr: int) -> str:
    done = external.run(["gh", "pr", "diff", str(pr), "-R", repo])
    if done.returncode != 0:
        raise EnvError(f"PR #{pr}의 변경 내용을 읽지 못했습니다. PR 번호와 gh 로그인을 확인하세요.")
    return done.stdout


def post_review(repo: str, pr: int, found: list[Finding]) -> None:
    """찾은 곳마다 줄 코멘트를 단 리뷰 하나를 남긴다(승인·변경 요청이 아니라 COMMENT)."""
    payload = {
        "event": "COMMENT",
        "body": PREFIX + (f"{len(found)}곳을 봐 주세요." if found else "지적할 곳이 없습니다."),
        "comments": [{"path": f.path, "line": f.line, "side": "RIGHT", "body": PREFIX + f.message}
                     for f in found],
    }
    with tempfile.TemporaryDirectory() as folder:
        body = Path(folder) / "review.json"
        body.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        done = external.run(["gh", "api", "--method", "POST",
                             f"repos/{repo}/pulls/{pr}/reviews", "--input", str(body)])
    if done.returncode != 0:
        raise EnvError("리뷰 코멘트를 달지 못했습니다. gh 로그인과 PR 상태를 확인하세요.")
