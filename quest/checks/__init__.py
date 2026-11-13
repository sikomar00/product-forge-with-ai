"""체크 프리미티브(M1-01, ADR-0004, design.md 8.4절). 콘텐츠의 Check.fn이 쓴다.

공통 규칙(Spec "체크 프리미티브"):
- 결과는 Result. "없음"·"다름"은 ok=False이지 예외가 아니다.
- 도구가 없거나 네트워크가 끊긴 환경 문제만 CheckEnvError(그 시도는 error, 실패로 세지 않는다).
- 읽기 전용이다. 대상의 상태를 바꾸지 않는다. 화면 문자열이 아니라 JSON·porcelain 출력을 읽는다.
"""

from quest.core.mission import Result


def ok(detail: str = "") -> Result:
    return Result(True, detail)


def fail(detail: str = "") -> Result:
    return Result(False, detail)


def verdict(passed: bool, detail: str = "") -> Result:
    return Result(passed, detail)
