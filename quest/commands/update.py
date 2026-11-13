"""IA-18 콘텐츠 갱신(M1-03, UJ-9, Spec "quest update").

출력은 바뀐 장 번호와 새 미션 수뿐이다. 콘텐츠의 글(요청문·정답 등)은 보여 주지 않는다.
"""

import re
import tomllib
from pathlib import Path

from quest import external
from quest.commands.common import OK
from quest.core import config, content, incidents, progress, state

CHAPTER_FILE = re.compile(r"content/ch(\d{2})_\w+\.py")
_AUTH_HINTS = ("authentication failed", "could not read username", "permission denied",
               "repository not found", "terminal prompts disabled")


def _repo_url(repo: str) -> tuple[str, bool]:
    """(클론 주소, GitHub인지). URL이나 있는 경로는 그대로 쓴다(시험·로컬 작업용)."""
    if "://" in repo or repo.startswith("git@") or Path(repo).expanduser().exists():
        return repo, False
    return f"https://github.com/{repo}.git", True


def _git(args: list[str], cwd: Path | None = None) -> str:
    """git을 실행하고 표준 출력을 돌려준다. 실패하면 원인에 맞는 안내로 EnvError."""
    done = external.run(["git", *args], cwd=cwd)
    if done.returncode == 0:
        return done.stdout.strip()
    err = done.stderr.lower()
    if any(hint in err for hint in _AUTH_HINTS):
        raise config.EnvError("콘텐츠 리포에 접근하지 못했습니다(인증). 실행: gh auth login")
    if "could not resolve host" in err or "unable to access" in err:
        raise config.EnvError("네트워크에 연결하지 못했습니다. 받아 둔 콘텐츠로 계속하면 됩니다.")
    raise config.EnvError(f"git {args[0]}이 실패했습니다: {done.stderr.strip()[:200]}")


def _mission_keys(root: Path) -> set[str]:
    """지금 콘텐츠의 미션 키. 아직 없거나 깨졌으면 빈 집합."""
    try:
        return {m.key for m in content.load_content(root).missions}
    except config.EnvError:
        return set()


def _incident_active() -> bool:
    if not state.db_path().exists():
        return False
    conn = state.connect()
    try:
        return incidents.active_incident(conn)
    finally:
        conn.close()


def _clone(repo: str, root: Path) -> None:
    url, on_github = _repo_url(repo)
    if on_github:  # git이 gh 로그인을 쓰게 한다(비공개 리포)
        external.run(["gh", "auth", "setup-git"])
    root.parent.mkdir(parents=True, exist_ok=True)
    _git(["clone", "--quiet", url, str(root)])


def _pull(root: Path) -> str:
    """원격을 받아 requires_engine을 먼저 보고, 맞으면 fast-forward로 합친다.

    합치기 전의 커밋(짧은 해시)을 돌려준다.
    """
    before = _git(["rev-parse", "--short", "HEAD"], root)
    _git(["fetch", "--quiet", "origin"], root)
    remote = _git(["rev-parse", "--abbrev-ref", "origin/HEAD"], root)
    manifest = tomllib.loads(_git(["show", f"{remote}:content.toml"], root))
    content.check_compat(manifest.get("requires_engine", ""), content.version("quest"))
    _git(["merge", "--ff-only", "--quiet", remote], root)
    return before


def _changed_chapters(root: Path, before: str | None) -> list[int]:
    if before is None:
        names = _git(["ls-files", "content"], root).splitlines()
    else:
        names = _git(["diff", "--name-only", before, "HEAD", "--", "content"], root).splitlines()
    return sorted({int(m[1]) for name in names if (m := CHAPTER_FILE.fullmatch(name))})


def _record(before: str | None, after: str, new_missions: int) -> None:
    conn = state.connect()
    try:
        with state.transaction(conn) as tx:
            tx.conn.execute(
                "INSERT INTO meta (key, value) VALUES ('content_version', ?)"
                " ON CONFLICT (key) DO UPDATE SET value = excluded.value", (after,),
            )
            payload = {"from": before, "to": after, "new_missions": new_missions}
            progress.event(tx, "content_updated", None, payload)
    finally:
        conn.close()


def cmd_update(game: None, rest: list[str]) -> int:
    config.ensure_config()
    cfg = config.load_config()
    root, repo = content.content_root(cfg), cfg.get("content", {}).get("repo", "")
    if not repo or "<" in repo:
        raise config.EnvError("설정 파일의 [content] repo에 콘텐츠 리포(소유자/이름)를 적으세요.")
    if _incident_active():  # 장애 미션이 콘텐츠에서 바뀌면 abort가 되돌릴 시나리오를 잃는다
        raise config.EnvError("진행 중인 장애가 있어 콘텐츠를 갱신하지 않습니다. 먼저 복구하거나"
                              " quest incident abort")
    keys_before = _mission_keys(root)
    if (root / ".git").exists():
        before = _pull(root)
    else:
        before = None
        _clone(repo, root)
    after = _git(["rev-parse", "--short", "HEAD"], root)
    if before == after:
        print("이미 최신 콘텐츠입니다.")
        return OK
    new_missions = len(_mission_keys(root) - keys_before)
    _record(before, after, new_missions)
    chapters = ", ".join(f"{ch}장" for ch in _changed_chapters(root, before)) or "없음"
    print(f"콘텐츠를 갱신했습니다. 바뀐 장: {chapters} · 새 미션 {new_missions}개")
    return OK
