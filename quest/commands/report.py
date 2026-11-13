"""IA-20 미션 오판 신고(M1-11, UJ-11, Spec "미션 오판 신고 quest report").

진단 정보(미션 키·화면 번호, 최근 시도 3개의 체크 번호별 결과, 버전)만 담는다.
파일 내용·토큰·체크 설명은 담지 않는다. 이슈와 답글에도 스포일러 규칙을 적용한다.
"""

import json
import platform
import sys

from quest import external
from quest.commands.ask import confirm, read
from quest.commands.common import OK, Game, target, versions
from quest.core import config
from quest.core.mission import Mission

RECENT_ATTEMPTS = 3
OUTCOME_LABELS = {"pass": "통과", "fail": "실패", "error": "채점 못 함"}


def _attempt_lines(game: Game, m: Mission) -> list[str]:
    rows = game.conn.execute(
        "SELECT at, mode, outcome, check_results FROM attempts WHERE mission_key = ?"
        " ORDER BY attempt_id DESC LIMIT ?", (m.key, RECENT_ATTEMPTS),
    ).fetchall()
    lines = []
    for row in rows:
        checks = " ".join(f"{c['no']}{'✅' if c['ok'] else '❌'}" for c in json.loads(row[3]))
        lines.append(f"- {row[0]} · {OUTCOME_LABELS[row[2]]} · {row[1]} · 체크 {checks or '없음'}")
    return lines or ["- 아직 채점 기록 없음"]


def diagnosis(game: Game, m: Mission) -> str:
    """이슈 본문. 번호·버전·결과만 담는다."""
    engine, content_version = versions(game.conn)
    tools = ", ".join(f"{name} {external.version_of([name, '--version']) or '없음'}"
                      for name in ("git", "gh", "uv"))
    return "\n".join([
        f"미션: {m.key} ({m.id}) · 유형 {m.kind}",
        f"엔진 {engine} · 콘텐츠 {content_version}",
        f"환경: {platform.platform()} · Python {sys.version.split()[0]} · {tools}",
        "최근 시도(최신순):", *_attempt_lines(game, m),
    ])


def _repo(game: Game) -> str:
    repo = game.cfg.get("content", {}).get("repo", "")
    if not repo or "<" in repo:
        raise config.EnvError("설정 파일의 [content] repo에 콘텐츠 리포(소유자/이름)를 적으세요.")
    return repo


def cmd_report(game: Game, rest: list[str]) -> int:
    m, code = target(game, rest)
    if m is None:
        return code
    body = diagnosis(game, m)
    print("이 진단 정보로 콘텐츠 리포에 이슈를 엽니다:\n")
    print(body)
    note = (read("\n한 줄 설명(선택, 그냥 Enter면 건너뜀): ") or "").strip()
    if note:
        body += f"\n\n학습자 설명: {note}"
    if not confirm("이슈를 열까요?"):
        print("열지 않았습니다.")
        return OK
    done = external.run(["gh", "issue", "create", "-R", _repo(game),
                         "--title", f"[오판 신고] {m.id} ({m.key})", "--body", body])
    if done.returncode != 0:
        raise config.EnvError("이슈를 열지 못했습니다. gh auth status와 리포 이름을 확인하세요.")
    print(f"이슈를 열었습니다: {done.stdout.strip()}")
    print("답글은 gh issue view로 보세요. 고쳐졌다는 답이 오면 quest update 뒤 quest check.")
    return OK
