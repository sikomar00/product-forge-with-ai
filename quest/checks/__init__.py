"""체크 프리미티브(M1-01, ADR-0004, design.md 8.4절). 콘텐츠의 Check.fn이 쓴다.

공통 규칙(Spec "체크 프리미티브", CLAUDE.md 6절):
- 결과는 Result. "없음"·"다름"은 ok=False이지 예외가 아니다.
- 도구가 없거나 네트워크가 끊긴 환경 문제만 CheckEnvError(그 시도는 error, 실패로 세지 않는다).
- 읽기 전용이다. 대상의 상태를 바꾸지 않는다.
- 화면 출력 문자열을 정규식으로 맞추지 않는다.
  종료 코드, JSON, porcelain·형식을 지정한 출력을 읽는다.
"""

from quest.core.mission import Result

MISSING = object()  # 값을 찾지 못했다는 표시. None은 JSON null과 겹쳐서 따로 둔다. 모든 모듈이 같다


def ok(detail: str = "") -> Result:
    return Result(True, detail)


def fail(detail: str = "") -> Result:
    return Result(False, detail)


def verdict(passed: bool, detail: str = "") -> Result:
    return Result(passed, detail)


def dig(value: object, keys: tuple[str | int, ...]) -> object:
    """JSON 값에서 keys 경로를 따라간 값. 중간에 없으면 MISSING."""
    for key in keys:
        if value is MISSING:
            return MISSING
        try:
            value = value[key]
        except (KeyError, IndexError, TypeError):
            return MISSING
    return value
