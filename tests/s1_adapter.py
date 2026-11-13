"""S1 회귀 어댑터(T0-8, M0-17, ADR-0001). tests/ 안에만 둔다(Spec "M0 시험").

S1 리포(sikomar00/sailingstone-quest)를 읽기 전용으로 불러와,
S1 미션을 새 엔진의 Mission으로 감싼다.
체크는 S1의 채점 함수(grade_sql·grade_py)를 그대로 부른다. S1 리포에는 아무것도 쓰지 않는다:
S1이 DB·세이브·워크스페이스를 쓰는 경로를 모두 임시 폴더로 돌린다.

S1 패키지 이름도 quest라서 새 엔진과 겹친다. s1quest라는 이름으로 따로 불러온다.
"""

import hashlib
import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

from quest.core.mission import Check, Ctx, Mission, Result
from quest.core.spoiler import obfuscate

S1_COMMIT = "513ec5891c7fdea0ae01c9cec14505c3103e8e09"  # 2026-10-12, S1을 만든 날의 main
S1_ENV = "QUEST_S1_REPO"


def s1_root() -> Path | None:
    value = os.environ.get(S1_ENV)
    return Path(value) if value else None


def load_engine(root: Path, scratch: Path) -> ModuleType:
    """S1 engine 모듈. 쓰기 경로(DB·세이브·워크스페이스·화면용 ROOT)를 scratch로 돌린다."""
    package = root / "quest"
    if "s1quest" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "s1quest", package / "__init__.py", submodule_search_locations=[str(package)]
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["s1quest"] = module
        spec.loader.exec_module(module)
    engine = importlib.import_module("s1quest.engine")
    engine.ROOT, engine.DB = scratch, scratch / "data" / "hangyeol.db"
    engine.WS, engine.SAVE = scratch / "workspace", scratch / "save.json"
    engine.save = lambda st: None  # S1 세이브 파일을 만들지 않는다
    return engine


def answer_path(m: dict, folder: Path) -> Path:
    """S1 모범 답안을 학습자 답안 파일처럼 써 둔다. 파이썬 미션은 ref 함수를 그대로 부른다.

    S1 solution 명령처럼 소스만 옮기면 ref가 쓰는 모듈 상수(B1_SQL 등)가 빠져서 깨진다.
    """
    if m["kind"] == "sql":
        path = folder / f"{m['id']}.sql"
        path.write_text(m["sol"], encoding="utf-8")
        return path
    ref = m["ref"]
    path = folder / f"{m['id'].replace('-', '_')}.py"
    path.write_text(
        f"from {ref.__module__} import {ref.__name__} as _ref\n\n\n"
        "def solve(conn, *args):\n    return _ref(conn, *args)\n",
        encoding="utf-8",
    )
    return path


def mission_key(s1_id: str) -> str:
    return "m_" + hashlib.sha256(f"s1:{s1_id}".encode()).hexdigest()[:8]


def to_mission(m: dict, engine: ModuleType, answer: Path) -> Mission:
    """S1 미션 하나를 새 엔진 Mission으로. 체크 1개 = S1 채점 규칙 통과."""
    grade = engine.grade_sql if m["kind"] == "sql" else engine.grade_py

    def check(ctx: Ctx) -> Result:
        ok, feedback, _counted = grade(m, ctx.workdir / answer.name, {"cur": {"fails": 0}})
        return Result(ok, " / ".join(str(line) for line in feedback))

    return Mission(
        key=mission_key(m["id"]), id=f"s1-{m['id']}", ch=m["ch"],
        kind="boss" if m["exam"] else "ops", title=m["title"], frm=m["frm"], xp=m["xp"],
        ai="solo", msg=m["msg"], hints=tuple(obfuscate(h) for h in m["hints"]),
        solution=obfuscate(m.get("sol") or m["ref"].__name__),
        checks=(Check(1, "S1 채점 규칙을 통과한다", check, "S1 피드백을 보세요"),),
    )
