# Intent

## 현재 작업: M0 · 엔진 (Plan v1.1 2026-11-13, 착수 전)

### 1. 문제
하네스 1~7단계 문서는 승인됐지만 게임 코드는 아직 없다. 0장을 시작하려면(W1) M0 게이트 통과와 0장 부분(0장 콘텐츠, `quest doctor`, `quest update`)이 필요하다(`docs/PLAN.md` 결정 1).

### 2. 기대 결과
- PRD M0-01~M0-19를 만족하고 M0 게이트를 통과한다: S1 회귀 52/52, 가짜 미션으로 IA-1~IA-11·IA-15~IA-17 동작, DDL 점검 67/67, `status --json` 금지 필드 0개, 엔진 리포의 콘텐츠 파일 0개, 500줄 넘는 파일 0개.
- T0-4(첫 세로 조각)를 마치면 실제 걸린 시간으로 W1 예상일을 다시 계산한다.

### 3. 영향 범위
- 엔진 리포 `product-forge-with-ai`의 엔진 구역: `quest/`, `tests/`, `pyproject.toml`, `uv.lock`, `.github/workflows/`.
- 참조 ID: PRD M0-01~M0-19, IA-1~IA-11·IA-15~IA-17, UJ-2·UJ-3·UJ-4·UJ-6·UJ-7·UJ-8, ERD v1.0의 표 12개(`docs/ddl/v1.0.sql`), Spec v1.0 "M0 · 엔진".
- 바꾸지 않는 것: S1 리포(읽기만), `tech-radar-agent` 리포, 콘텐츠 리포(아직 없음).

### 4. 제약
- 엔진은 사용자가 로컬 Claude Code로 바이브코딩한다. Windows에서 할 수 있는 만큼 먼저 하고 맥에서 클론받아 마무리한다(Plan 결정 2, 2026-11-13). AI는 Plan 범위 안에서 돕고, 결정과 리뷰는 사용자가 한다.
- 라이브러리는 Plan 목록만 쓴다(pytest 9.2.0, ruff 0.17.2, 테스트 전용 pandas 3.0.3). 그 밖은 먼저 묻는다.
- `rules/code.md`(파일 최대 500줄, 순환 복잡도 10 이하, 공개 함수 타입 힌트)를 지키고, 엔진 테스트는 가짜 미션 픽스처로만 한다(ADR-0006).
- 엔진 작업 중 AI는 콘텐츠 위치를 읽지 않는다(CLAUDE.md 6절).

### 5. 열린 질문과 진행
- 다음 작업: T0-1 리포 기본(사용자 + AI, Windows). 사용자 작업 1·2는 끝났다(PR #2 머지, Windows에 uv 0.13.6·Python 3.14.10). 원격 브랜치 `claude/harness-setup` 삭제는 사용자가 GitHub에서 한다.
- 확인할 것: CI 액션의 릴리스 날짜(T0-1), 맥 uv Python 3.14의 SQLite 버전(T0-2, Windows는 3.53.1), pandas 3.0.3과 S1 코드의 호환(T0-8), OrbStack 미확인 3건(T1-4), GitHub 러너의 systemd(T1-6).
- 실측 기록: T0-4를 마치면 채운다.

## 완료한 작업
- 하네스 1~7단계 문서(2026-11-09): GLOSSARY, ADR-0001~0009, IA v1.2, User Journey v1.1, PRD v1.2, ERD v1.0(DDL 점검 67/67 통과), Spec v1.0, Plan v1.0 모두 승인.
- 설계서 v0.3~v0.3.5(2026-11-09). v0.3.2까지 main에 머지했다(PR #1).
