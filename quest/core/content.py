"""콘텐츠 불러오기·검증·호환 확인(M0-04, M0-05, Spec "콘텐츠 불러오기", "버전과 호환")."""

import importlib.util
import operator
import re
import tomllib
from collections import Counter
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from types import ModuleType

from quest.core import answers, spoiler
from quest.core.config import EnvError
from quest.core.mission import (
    AI_MODES,
    CARD_GRADINGS,
    CARD_KINDS,
    CHECK_KINDS,
    ITEM_FORMATS,
    ITEM_KINDS,
    KINDS,
    SCAFFOLDS,
    TRACKS,
    Card,
    Item,
    Mission,
)

MISSION_KEY = re.compile(r"m_[0-9a-f]{8}")
CARD_KEY = re.compile(r"c_[0-9a-f]{8}")
CHAPTER_FILE = re.compile(r"ch(\d{2})_\w+\.py")
DELAYED_QUIZ_SIZE = 10
_COMPARE = {
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
}
_CLAUSE = re.compile(r"\s*(>=|<=|==|!=|>|<)\s*(\d+(?:\.\d+)*)\s*")


@dataclass(frozen=True)
class Content:
    missions: tuple[Mission, ...]  # 장 → 장 안의 순서
    delayed_quiz: dict[int, tuple[Item, ...]]  # 장 번호 → 지연 확인 퀴즈 문항


def content_root(cfg: dict) -> Path:
    """콘텐츠는 설정 파일에 적힌 경로에서만 불러온다(M0-05)."""
    try:
        return Path(cfg["content"]["path"]).expanduser()
    except KeyError as exc:
        raise EnvError("설정 파일에 [content] path가 없습니다.") from exc


def load_content(root: Path, engine_version: str | None = None) -> Content:
    manifest = _read_manifest(root)
    if "requires_engine" not in manifest:
        raise EnvError("content.toml에 requires_engine이 없습니다.")
    check_compat(manifest["requires_engine"], engine_version or version("quest"))
    missions: list[Mission] = []
    quizzes: dict[int, tuple[Item, ...]] = {}
    errors: list[str] = []
    for path in sorted((root / "content").glob("ch*.py")):
        errors += _collect(path, missions, quizzes)
    errors += validate(missions, quizzes)
    if errors:
        raise EnvError("콘텐츠가 미션 스키마에 맞지 않습니다:\n" + "\n".join(errors))
    return Content(tuple(missions), quizzes)


def _tuple_of(value: object, cls: type) -> bool:
    return isinstance(value, tuple) and all(isinstance(v, cls) for v in value)


def _collect(
    path: Path, missions: list[Mission], quizzes: dict[int, tuple[Item, ...]]
) -> list[str]:
    """장 파일 하나를 불러와 missions·quizzes에 더하고, 모양이 틀린 곳을 돌려준다."""
    chapter = CHAPTER_FILE.fullmatch(path.name)
    if chapter is None:
        return [f"{path.name}: 파일 이름은 chNN_이름.py 형식이어야 합니다"]
    module = _import(path)
    if not _tuple_of(getattr(module, "MISSIONS", None), Mission):
        return [f"{path.name}: MISSIONS는 Mission의 튜플이어야 합니다"]
    missions.extend(module.MISSIONS)
    if not hasattr(module, "DELAYED_QUIZ"):
        return []
    if not _tuple_of(module.DELAYED_QUIZ, Item):
        return [f"{path.name}: DELAYED_QUIZ는 Item의 튜플이어야 합니다"]
    if int(chapter[1]) in quizzes:
        return [f"{path.name}: {int(chapter[1])}장 DELAYED_QUIZ가 다른 파일에도 있습니다"]
    quizzes[int(chapter[1])] = module.DELAYED_QUIZ
    return []


def _read_manifest(root: Path) -> dict:
    path = root / "content.toml"
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EnvError(f"콘텐츠가 없습니다: {path}. quest update로 받으세요.") from exc
    except tomllib.TOMLDecodeError as exc:
        raise EnvError(f"content.toml 형식이 틀렸습니다: {exc}") from exc


def _import(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"quest_content_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # 콘텐츠 코드의 어떤 오류든 파일 이름과 함께 환경 오류로 알린다
        raise EnvError(f"콘텐츠 파일을 불러오지 못했습니다: {path.name} ({exc!r})") from exc
    return module


# ───────────── 호환 확인 ─────────────


def _as_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def satisfies(spec: str, engine: str) -> bool:
    """requires_engine(예: ">=0.1,<0.2")을 엔진 버전이 만족하는지."""
    current = _as_tuple(engine)
    for clause in spec.split(","):
        match = _CLAUSE.fullmatch(clause)
        if match is None:
            raise EnvError(f"content.toml의 requires_engine 형식이 틀렸습니다: {spec!r}")
        wanted = _as_tuple(match[2])
        width = max(len(current), len(wanted))  # 0.1과 0.1.0을 같게 본다
        pad = (0,) * width
        if not _COMPARE[match[1]]((current + pad)[:width], (wanted + pad)[:width]):
            return False
    return True


def check_compat(spec: str, engine: str) -> None:
    if not satisfies(spec, engine):
        raise EnvError(
            f"이 콘텐츠는 엔진 {spec}이 필요한데 지금 엔진은 {engine}입니다. "
            "엔진 리포에서 git pull과 uv sync로 엔진을 갱신하세요."
        )


# ───────────── 검증 ─────────────


def validate(missions: list[Mission], quizzes: dict[int, tuple[Item, ...]]) -> list[str]:
    """스키마에 맞지 않는 곳을 '어느 미션이 왜'의 형태로 모두 돌려준다."""
    errors = _duplicates("미션 키", [m.key for m in missions])
    errors += _duplicates("화면 번호", [m.id for m in missions])
    errors += _duplicates("카드 키", [c.key for m in missions for c in m.cards])
    for m in missions:
        errors += [f"{m.key} ({m.id}): {e}" for e in _mission_errors(m)]
    for ch, items in sorted(quizzes.items()):
        errors += [f"{ch}장 DELAYED_QUIZ: {e}" for e in _quiz_errors(items)]
    return errors


def _duplicates(label: str, values: list[str]) -> list[str]:
    return [f"{label} 중복: {v}" for v, n in Counter(values).items() if n > 1]


def _numbering(label: str, numbers: list[int]) -> list[str]:
    if numbers == list(range(1, len(numbers) + 1)):
        return []
    return [f"{label} 번호는 1부터 빈틈없이 이어져야 합니다: {numbers}"]


def _mission_errors(m: Mission) -> list[str]:
    rules = [
        (MISSION_KEY.fullmatch(m.key) is None, f"미션 키 형식이 틀렸습니다: {m.key!r}"),
        (not 0 <= m.ch <= 17, f"장 번호는 0~17이어야 합니다: {m.ch}"),
        (m.kind not in KINDS, f"알 수 없는 유형: {m.kind!r}"),
        (m.ai not in AI_MODES, f"알 수 없는 AI 사용 방식: {m.ai!r}"),
        (m.track not in TRACKS, f"알 수 없는 트랙: {m.track!r}"),
        (m.scaffold not in SCAFFOLDS, f"알 수 없는 스캐폴드: {m.scaffold!r}"),
        (m.est_min <= 0, f"est_min은 0보다 커야 합니다: {m.est_min}"),
        (len(m.hints) != 3, f"힌트는 3개여야 합니다: {len(m.hints)}개"),
        (not all(map(spoiler.decodes, m.hints)), "힌트는 난독화(obf1:)해야 합니다"),
        (m.solution is not None and not spoiler.decodes(m.solution),
         "모범 답안은 난독화해야 합니다"),
        (m.kind in CHECK_KINDS and not m.checks, f"{m.kind} 유형은 체크가 있어야 합니다"),
        (m.kind in ITEM_KINDS and not m.items, f"{m.kind} 유형은 문항이 있어야 합니다"),
    ]
    errors = [message for broken, message in rules if broken]
    errors += _numbering("체크", [c.no for c in m.checks])
    errors += _numbering("문항", [i.no for i in m.items])
    errors += _numbering("설명 게이트 문항", [i.no for i in m.explain])
    errors += [e for c in m.cards for e in _card_errors(c)]
    errors += [e for i in (*m.items, *m.explain) for e in _item_errors(i)]
    return errors


def _patterns_compile(patterns: tuple[str, ...]) -> bool:
    """정규식 카드는 choices에 허용 정규식을 하나 이상 둔다(2026-11-13 결정)."""
    try:
        return bool(patterns) and all(re.compile(p) for p in patterns)
    except re.error:
        return False


def _card_errors(c: Card) -> list[str]:
    rules = [
        (CARD_KEY.fullmatch(c.key) is None, "카드 키 형식이 틀렸습니다"),
        (c.kind not in CARD_KINDS, f"알 수 없는 카드 종류: {c.kind!r}"),
        (c.grading not in CARD_GRADINGS, f"알 수 없는 채점 방식: {c.grading!r}"),
        (c.grading == "choice" and c.back not in c.choices, "객관식 카드의 뒷면이 보기에 없습니다"),
        (c.grading == "regex" and not _patterns_compile(c.choices), "정규식 카드의 보기 오류"),
    ]
    return [f"카드 {c.key!r}: {message}" for broken, message in rules if broken]


def _item_errors(i: Item) -> list[str]:
    rules = [
        (i.kind not in ITEM_FORMATS, f"알 수 없는 문항 형식: {i.kind!r}"),
        (not spoiler.decodes(i.answer), "정답은 난독화(obf1:)해야 합니다"),
        (i.kind in ("choice", "multi", "order") and not i.choices, "보기가 없습니다"),
    ]
    errors = [message for broken, message in rules if broken]
    if not errors:
        errors = answers.answer_errors(i)
    return [f"문항 {i.no}: {message}" for message in errors]


def _quiz_errors(items: tuple[Item, ...]) -> list[str]:
    errors = [] if len(items) == DELAYED_QUIZ_SIZE else [f"문항은 10개여야 합니다: {len(items)}개"]
    errors += _numbering("문항", [i.no for i in items])
    errors += [e for i in items for e in _item_errors(i)]
    return errors
