"""미션 스키마: 엔진과 콘텐츠의 경계(M0-04, Spec "미션 스키마", design.md 8.3절).

콘텐츠 모듈은 이 파일의 클래스로 MISSIONS와 DELAYED_QUIZ를 만든다.
2026-11-13 결정: 개념·용법·도메인·도구 지도는 cards 하나로 합치고, 문항 형식은 4가지로 나눈다.
T1-3에서 장애(chaos)·근본 원인 퀴즈(rca)를 더했다. 감사 미션은 체크와 설명 게이트로 채점한다.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MISSION_KEY = re.compile(r"m_[0-9a-f]{8}")  # 바꾸지 않는 미션 키(ERD)
KINDS = ("ops", "quiz", "predict", "drill", "decision", "audit", "incident", "boss")
CHECK_KINDS = ("ops", "audit", "incident", "boss")  # 체크로 채점한다
ITEM_KINDS = ("quiz", "predict", "drill", "decision")  # 문항으로 채점한다
AI_MODES = ("solo", "pair", "delegate")
TRACKS = ("core", "elective")
SCAFFOLDS = ("worked", "completion", "independent")
CARD_KINDS = ("concept", "usage", "domain", "tool_map")
CARD_GRADINGS = ("choice", "regex", "self")
# choice: 하나 고르기, multi: 여러 개 고르기(같은 집합이어야 정답),
# order: 순서 맞추기, regex: 단답·명령
ITEM_FORMATS = ("choice", "multi", "order", "regex")


class CheckEnvError(Exception):
    """도구가 없거나 네트워크가 끊긴 것 같은 환경 문제. 그 시도는 error이고 실패로 세지 않는다.

    메시지는 엔진이 만들고 화면에 그대로 나간다. 정답 위치 같은 힌트를 넣지 않는다(M1-01).
    """


@dataclass(frozen=True)
class Result:
    ok: bool
    detail: str = ""  # 화면용. DB에 저장하지 않는다


@dataclass(frozen=True)
class Ctx:
    """체크·트랩·solve가 받는 맥락."""

    workdir: Path
    config: dict
    lab: str
    gh: object | None  # GitHub 호출기(실제 호출 또는 기록 재생). M1에서 정한다
    now: datetime


@dataclass(frozen=True)
class Check:
    no: int
    desc: str
    fn: Callable[[Ctx], Result]
    hint: str  # 실패했을 때 보여 주는 방향 힌트


@dataclass(frozen=True)
class Trap:
    """흔한 실수 상태를 감지하면 msg를 보여 준다."""

    fn: Callable[[Ctx], bool]
    msg: str


@dataclass(frozen=True)
class Card:
    key: str  # c_ + 소문자 16진수 8자리
    kind: str  # CARD_KINDS
    front: str
    back: str
    grading: str  # CARD_GRADINGS
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Item:
    """퀴즈·예측·결정·드릴·설명 게이트·지연 확인 퀴즈 문항 하나."""

    no: int
    prompt: str
    kind: str  # ITEM_FORMATS
    answer: str  # 난독화(obf1:)
    choices: tuple[str, ...] = ()
    ask_confidence: bool = False


@dataclass(frozen=True)
class Chaos:
    """장애 시나리오(콘텐츠 구역, Spec "장애 주입").

    targets: 주입 허용 확인·스냅샷 대상. 경로(작업 폴더 기준, ~ 가능) 또는 'lab:<머신 이름>'.
    inject는 장애를 만들고, verify는 장애가 실제로 걸렸는지 보고, cleanup은 시나리오가 따로
    남긴 것(프로세스·VM 안 변경 등)을 치운다. 파일·폴더는 엔진이 스냅샷으로 되돌린다.
    """

    targets: tuple[str, ...]
    inject: Callable[[Ctx], None]
    verify: Callable[[Ctx], bool]
    cleanup: Callable[[Ctx], None]


@dataclass(frozen=True)
class Mission:
    key: str  # m_ + 소문자 16진수 8자리. 바꾸지 않는다
    id: str  # 화면 번호(예: "5-8")
    ch: int
    kind: str  # KINDS
    title: str
    frm: str  # 요청을 보낸 등장인물
    xp: int
    ai: str  # AI_MODES
    msg: str  # 요청문
    hints: tuple[str, ...]  # 3단계, 난독화
    cards: tuple[Card, ...] = ()
    checks: tuple[Check, ...] = ()
    traps: tuple[Trap, ...] = ()
    solution: str | None = None  # 난독화
    items: tuple[Item, ...] = ()
    explain: tuple[Item, ...] = ()  # 설명 게이트
    requires: tuple[str, ...] = ()
    track: str = "core"
    scaffold: str = "independent"
    spiral: tuple[int, ...] = ()
    tr: bool = False  # Tech Radar 연결 트랙
    est_min: int = 30
    solve: Callable[[Ctx], None] | None = None  # 자동 플레이스루용 모범 답안 적용
    requires_lab: bool = False
    badge: str | None = None
    chaos: Chaos | None = None  # 장애 미션(incident)의 시나리오
    rca: tuple[Item, ...] = ()  # 장애 미션의 근본 원인 퀴즈. 복구한 뒤 묻는다
