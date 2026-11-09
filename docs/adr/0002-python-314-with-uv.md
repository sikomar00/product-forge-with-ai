---
status: accepted
---
# 엔진은 Python 3.14로 쓰고, 설치와 실행은 uv로 한다

Python 공식 버전 상태 페이지(2026-11-09 확인) 기준으로 3.14는 버그 수정을 지원받는 중이고 2030-10에 지원이 끝난다. 3.15는 2026-10-09에 나와 출시 한 달째다. Tech Radar가 쓰는 3.11은 보안 패치만 받고 2027-10에 지원이 끝난다. 엔진은 표준 라이브러리 우선이라 버전 호환 부담이 작다. 그래서 3.14를 쓰고, Python 설치·가상 환경·실행은 uv로 통일한다. uv는 이미 Brewfile에 있다(design.md 7.1절). 사용자 결정(2026-11-09).

## Considered Options
- 3.15: 가장 최신이지만, 나중에 쓸 라이브러리(예: psycopg)가 지원하는지 따로 확인해야 한다.
- 3.11(Tech Radar와 같은 버전): 두 프로젝트의 버전이 같아지지만 보안 패치만 받는다. 커리큘럼이 끝나는 시점(보수 일정 2027-05)까지는 지원된다.

## Consequences
- `pyproject.toml`의 `requires-python`을 3.14 기준으로 적는다. 정확한 범위와 라이브러리 버전은 Plan에서 승인받는다.
- 출처: https://devguide.python.org/versions/
