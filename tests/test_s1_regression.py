"""S1 회귀 시험(T0-8, M0-17): S1 미션 52개(SQL 42, Python 10)를 새 엔진으로 채점하고 XP를 비교한다.

S1 리포 위치는 환경 변수 QUEST_S1_REPO(CI는 고정 커밋을 받아 둔다). 없으면 이 파일만 건너뛴다.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from s1_adapter import S1_COMMIT, answer_path, load_engine, s1_root, to_mission

from quest.core import content, progress, rewards, state
from quest.core.mission import Ctx

ROOT = s1_root()
pytestmark = pytest.mark.skipif(ROOT is None, reason="QUEST_S1_REPO가 없어 S1 회귀를 건너뛴다")

# (힌트 수, 실패 수, 모범 답안을 봤는지): 원샷, 실패, 힌트, 감점 최대, 모범 답안
SCENARIOS = [(0, 0, False), (0, 2, False), (1, 0, False), (2, 1, False), (3, 0, False),
             (3, 4, True)]


@pytest.fixture(scope="module")
def s1(tmp_path_factory: pytest.TempPathFactory):
    scratch = tmp_path_factory.mktemp("s1")
    engine = load_engine(ROOT, scratch)
    answers = scratch / "answers"
    answers.mkdir()
    missions = {m["id"]: to_mission(m, engine, answer_path(m, answers)) for m in engine.MISSIONS}
    return engine, missions, answers


def test_s1_repo_is_the_pinned_commit() -> None:
    head = (ROOT / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        head = (ROOT / ".git" / head.split()[1]).read_text(encoding="utf-8").strip()
    assert head == S1_COMMIT


def test_s1_has_52_missions_and_fits_new_schema(s1) -> None:
    engine, missions, _ = s1
    # PRD의 'SQL 42, Python 10'은 파일 기준이다. Python 파일에도 SQL로 채점하는 미션이 2개 있다.
    assert (len(engine.SQL_MISSIONS), len(engine.PY_MISSIONS)) == (42, 10)
    assert content.validate(list(missions.values()), {}) == []


def test_all_model_answers_pass_in_new_engine(s1) -> None:
    """52개 모범 답안이 새 엔진의 체크 채점(kinds.ops)으로 모두 통과한다."""
    from quest.kinds import ops

    _, missions, answers = s1
    ctx = Ctx(workdir=answers, config={}, lab="", gh=None, now=datetime.now(UTC))
    failed = [m.id for m in missions.values() if not all(r.ok for r in ops.grade(m, ctx)[0])]
    assert failed == []
    assert len(missions) == 52


def test_wrong_answer_fails(s1, tmp_path: Path) -> None:
    """채점이 무엇이든 통과시키는 것이 아님을 확인한다."""
    from quest.kinds import ops

    _, missions, _ = s1
    (tmp_path / "1-1.sql").write_text("SELECT product_name FROM products", encoding="utf-8")
    ctx = Ctx(workdir=tmp_path, config={}, lab="", gh=None, now=datetime.now(UTC))
    results, _ = ops.grade(missions["1-1"], ctx)
    assert results[0].ok is False and "컬럼 수" in results[0].detail


def _s1_gain(engine, m: dict, cur: dict, capsys: pytest.CaptureFixture[str]) -> int:
    """S1 on_success가 준 XP. 화면 출력은 버린다."""
    st = engine.new_state("회귀")
    st["cur"] = {"id": m["id"], "fails": 0, "hints": 0, "solution_seen": False, **cur}
    engine.on_success(st, m)
    capsys.readouterr()
    return st["xp"]


def test_mission_xp_matches_s1(s1, capsys: pytest.CaptureFixture[str]) -> None:
    """52개 × 시나리오 6개: 새 엔진 보상 계산이 S1 on_success와 같다."""
    engine = s1[0]
    differ = []
    for m in engine.MISSIONS:
        for hints, fails, seen in SCENARIOS:
            cur = {"mode": "normal", "hints": hints, "fails": fails, "solution_seen": seen}
            ours = rewards.mission_xp(m["xp"], rewards.Help(hints, fails, seen))
            if ours != _s1_gain(engine, m, cur, capsys):
                differ.append((m["id"], hints, fails, seen))
    assert differ == []


def test_rebuild_xp_matches_s1_review(s1, capsys: pytest.CaptureFixture[str]) -> None:
    engine = s1[0]
    differ = [m["id"] for m in engine.MISSIONS
              if rewards.rebuild_xp(m["xp"]) != _s1_gain(engine, m, {"mode": "review"}, capsys)]
    assert differ == []


def test_exam_exemption_matches_s1(s1, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """승급 시험: S1과 새 엔진이 같은 미션을 면제하고 같은 XP를 준다(보스 보상 제외)."""
    engine, missions, _ = s1
    adapted = tuple(missions.values())
    exams = [m for m in engine.MISSIONS if m["exam"]]
    assert exams
    for exam in exams:
        s1_total = _s1_gain(engine, exam, {"mode": "exam"}, capsys) - round(exam["xp"] * 1.2)
        conn = state.connect(tmp_path / f"{exam['id']}.db")
        with state.transaction(conn) as tx:
            boss = missions[exam["id"]]
            progress.start(tx, boss)
            ours = progress.exempt_rest_of_chapter(tx, adapted, boss)
        conn.close()
        assert sum(xp for _, xp in ours) == s1_total, exam["id"]
