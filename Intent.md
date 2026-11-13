# Intent

## 현재 작업: M0 · 엔진 (Plan v1.1 2026-11-13, T0-1 완료)

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
- 지금 방침(2026-11-13 사용자): Windows에서 할 수 있는 것을 모두 하고 맥으로 넘어간다. M0 게이트 승인은 아직 받지 않았다(숫자·QA는 `docs/qa-guide.md`).
- 다음 작업(맥): T1-4 OrbStack 랩(미확인 3건 + ssh 체크의 `orb -m` 형식), 랩 VM 대상 실제 주입, 사용자 QA U1~U9(`docs/qa-guide.md`), M0 게이트 승인. 그다음 콘텐츠(T1-6~, 클라우드 세션, 별도 리포). `core/progress.py`는 장애 함수를 `core/incidents.py`로 나눠 298줄이다.
- 결정 기록(2026-11-13): ADR-0010 졸업 기준은 통과한 미션으로(면제 불인정), ADR-0011 리뷰봇은 quest check 직전에 한 번. GLOSSARY에 면제·졸업 기준 영역·리뷰봇을 더하고 랩 항목의 '리뷰봇 워크플로'를 고쳤다. Windows 먼저 진행(Plan v1.1)과 장애 스냅샷 방식(Spec)은 되돌리기 쉬워 ADR로 만들지 않았다.
- Windows에서 할 엔진 작업은 끝났다(2026-11-13): T1-5 리뷰봇(quest check 직전에 학습자 본인 PR에 한 번), M1 코드 리뷰 15건·보안 검토 1건 반영. pytest 294/294(Windows·CI ubuntu·macos).
- T1-1~T1-3 완료(2026-11-13, Windows): 체크 프리미티브 6종(읽기 전용 시험), `quest selftest`·`quest report`, 장애 주입 안전장치(허용 대상·스냅샷·abort·복구·MTTR·근본 원인 퀴즈).
- T1-0 완료(2026-11-13): `quest doctor`(엔진 도구 + content.toml [tools] 0~4장), `quest update`(첫 클론, requires_engine 먼저 확인 후 ff 합치기, 바뀐 장·새 미션 수만 표시, content_updated 기록), `quest/external.py`(외부 명령 경계). 이 PC의 doctor는 orb(맥 전용)만 ❌.
- T0-9 진행(2026-11-13): 배지, 인자 3개 이하 정리(Tx·Help, ruff PLR0913), M0 전체 리뷰 10건 중 9건 반영, QA 기록.
- T0-8 완료(2026-11-13): S1 = `sikomar00/sailingstone-quest`(공개) 커밋 `513ec58`(2026-10-12). 엔진 리포 밖에 받아 읽기만 하고, 시험이 S1의 DB·세이브·워크스페이스 쓰기를 임시 폴더로 돌린다(시험 뒤 S1 `git status` 변경 0). 52개 모범 답안이 새 엔진 채점으로 모두 통과, 보상 XP(시나리오 6개 × 52)·재구성 복습 XP·승급 시험 면제 XP가 S1과 모두 같다. pandas 3.0.3 호환 확인. 로컬은 환경 변수 `QUEST_S1_REPO`, CI는 고정 커밋을 `s1/`에 받는다. 남은 차이: S1 배지 규칙(원샷 5연속 등)은 새 엔진에 아직 없다.
- T0-7 완료(2026-11-13): IA-6 `map`, IA-10 `goals`(content.toml [goals], 면제 불인정, 면제 미션 직접 통과 시 인정), IA-11 `stats`(`--sql` 읽기 전용·ATTACH 차단), IA-15 `status --json`, IA-17 `reset`. T0-6 리뷰 10건 중 8건, T0-7 리뷰 9건 중 7건 반영(나머지는 Spec·채팅에 이유 기록). 미룬 것: 인자 3개 이하 규칙 위반 함수 정리(별도 리팩터링, 사용자 결정 대기).
- T0-6 완료(2026-11-13): `cli.py`를 `quest/commands/`로 나눔. 문항형 채점·확신도·설명 게이트(`core/answers.py`, `commands/ask.py`·`grade.py`), 카드 복습·잠금·연속 복습일·재구성 복습·지연 확인 퀴즈(`core/review.py`, `commands/study.py`), 승급 시험·돌아가기(`commands/modes.py`). 정해진 세부 규칙은 Spec에 "(T0-6)"으로 적었다.
- T0-5 완료(2026-11-13): `core/spoiler.py`(obf1), `quest hint`·`quest solution`(감점 안내 후 [y/N] 확인, `hint_opened`·`solution_viewed` 기록). 콘텐츠 검증이 난독화 문자열을 실제로 풀어 본다. 끝낸 미션의 모범 답안은 감점 없이 보이고 기록하지 않는다(AI 판단, 리뷰 필요).
- T0-4 완료(2026-11-13): `core/progress.py`·`core/rewards.py`(계산만)·`core/ui.py`·`kinds/ops.py`·`cli.py`. 가짜 실습 미션이 홈 → 미션 → 채점 → 통과까지 돈다(IA-1·2·3·16, 종료 코드 0·1·2·3). 뒤 단계로 미룬 것: 설명 게이트·복습 잠금·연속 복습일·배지(T0-6), 나머지 이벤트(T0-7), `quest hint`(T0-5).
- T0-3 완료(2026-11-13): `core/mission.py`(미션 스키마), `core/content.py`(불러오기·검증·호환), `tests/fixtures/fake_content/`(8가지 유형, 미션 9개, 지연 확인 퀴즈 10문항). 스키마 결정 3가지는 Spec "미션 스키마"에 적었다.
- T0-2 완료(2026-11-13): `core/config.py`·`core/state.py`·`core/schema/v1_0.sql`. 엔진이 만든 DB에서 DDL 점검 67/67, 외래 키를 끄면 3개가 실패해 점검이 동작함을 확인. meta의 `engine_version` 갱신은 명령이 생기는 T0-4에서 한다. 원격 브랜치 `claude/harness-setup` 삭제는 사용자가 GitHub에서 한다.
- T0-1 완료(2026-11-13, 브랜치 `engine/windows-setup`): CI가 ubuntu·macos에서 초록(ruff, pytest 1개, DDL 67/67). Python은 uv 관리 빌드 3.14.10으로 고정해 세 환경 모두 SQLite 3.53.1이다. 빌드 백엔드로 uv_build 0.13.6을 썼다(uv와 같은 버전).
- 확인할 것: 맥 로컬에서 SQLite 3.53.1인지 확인(CI macos 러너에서는 3.53.1), OrbStack 미확인 3건(T1-4), GitHub 러너의 systemd(T1-6).
- 실측 기록(T0-4): AI 구현 시간 약 5분(2026-11-13 12:09:58~12:14:46 UTC, 문서 읽기·코드·시험·직접 실행 포함). Plan 추정 5~8h는 사용자가 함께 짜는 시간이었다. 사용자 리뷰 시간은 재지 못했다. 남은 엔진 작업의 병목은 AI 구현이 아니라 사용자 리뷰·결정, S1 리포 준비(T0-8), 0장 콘텐츠(T1-7, 클라우드 세션)다. W1 예상일은 사용자 리뷰 시간을 한 번 재고 다시 계산한다.

## 완료한 작업
- 하네스 1~7단계 문서(2026-11-09): GLOSSARY, ADR-0001~0009, IA v1.2, User Journey v1.1, PRD v1.2, ERD v1.0(DDL 점검 67/67 통과), Spec v1.0, Plan v1.0 모두 승인.
- 설계서 v0.3~v0.3.5(2026-11-09). v0.3.2까지 main에 머지했다(PR #1).
