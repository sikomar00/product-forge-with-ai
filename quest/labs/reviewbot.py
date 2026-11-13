"""2장 리뷰봇(M1-07, Spec "리뷰봇"): 학습자 PR의 diff에서 지적할 곳을 찾아 리뷰 코멘트를 단다.

GitHub Actions가 아니라 게임이 로컬에서 `gh`로 단다. 지적 목록(ReviewRule)은 콘텐츠에 있어서
공개 리포(opsdesk)에 올라가지 않는다. 코멘트는 '🤖 리뷰봇:'으로 시작하고 학습자 계정으로 달린다.

2026-11-13 결정: 규칙(Mission.review)이 있는 미션의 quest check 직전에, 채점과 따로 돈다.
체크는 읽기 전용이라 체크 안에서 달 수 없어서다(ADR-0004). 작업 폴더 리포의 가장 최근 열린
PR에, 리뷰봇 리뷰가 아직 없을 때만 한 번 단다(따로 기록하지 않아도 몇 번 돌려도 같다).
"""

import fnmatch
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from quest import external
from quest.core.config import EnvError
from quest.core.mission import ReviewRule

PREFIX = "🤖 리뷰봇: "
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int  # 새 파일 기준 줄 번호(GitHub 리뷰 코멘트의 RIGHT 쪽)
    message: str


def added_lines(diff: str) -> list[tuple[str, int, str]]:
    """unified diff에서 새로 더한 줄: (파일, 새 파일 줄 번호, 내용)."""
    found, path, line, in_header = [], None, 0, True
    for raw in diff.splitlines():
        if raw.startswith("diff --git "):
            in_header = True
        elif in_header and raw.startswith("+++ "):  # 머리줄: 다음 '@@' 전까지만
            path = raw[4:].removeprefix("b/") if raw[4:] != "/dev/null" else None
        elif hunk := _HUNK.match(raw):
            line, in_header = int(hunk[1]), False
        elif not in_header and raw.startswith("+") and path is not None:
            found.append((path, line, raw[1:]))
            line += 1
        elif not in_header and raw.startswith(" "):
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


def _repo(workdir: Path) -> str | None:
    """작업 폴더 리포의 GitHub '소유자/이름'. GitHub 리포가 아니면 None."""
    done = external.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                        cwd=workdir)
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def _latest_open_pr(repo: str) -> int | None:
    """학습자 본인이 연 PR 가운데 가장 최근 것. 공개 리포라 남의 PR에 코멘트를 달지 않게 한다."""
    done = external.run(["gh", "pr", "list", "-R", repo, "--state", "open", "--author", "@me",
                         "--limit", "1", "--json", "number", "-q", ".[0].number"])
    text = done.stdout.strip()
    return int(text) if done.returncode == 0 and text.isdecimal() else None


def _me() -> str:
    done = external.run(["gh", "api", "user", "-q", ".login"])
    if done.returncode != 0 or not done.stdout.strip():
        raise EnvError("GitHub 로그인을 확인하지 못했습니다. gh auth status")
    return done.stdout.strip()


def _already_reviewed(repo: str, pr: int) -> bool:
    """학습자 계정이 단 리뷰봇 리뷰가 이미 있는지(리뷰가 많아도 모든 쪽을 본다)."""
    done = external.run(["gh", "api", "--paginate", f"repos/{repo}/pulls/{pr}/reviews",
                         "-q", ".[] | [.user.login, .body] | @json"])
    if done.returncode != 0:
        raise EnvError(f"PR #{pr}의 리뷰를 읽지 못했습니다.")
    me = _me()
    rows = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
    return any(login == me and (body or "").startswith(PREFIX) for login, body in rows)


def run_once(workdir: Path, rules: tuple[ReviewRule, ...]) -> str | None:
    """열린 PR에 리뷰봇 리뷰가 아직 없으면 단다. 단 경우 화면 안내를, 아니면 None을 돌려준다."""
    if not workdir.is_dir():  # 아직 리포를 만들기 전
        return None
    repo = _repo(workdir)
    pr = _latest_open_pr(repo) if repo else None
    if pr is None or _already_reviewed(repo, pr):
        return None
    found = findings(pr_diff(repo, pr), rules)
    post_review(repo, pr, found)
    return f"🤖 리뷰봇이 PR #{pr}에 코멘트 {len(found)}개를 달았습니다. GitHub에서 확인하세요."
