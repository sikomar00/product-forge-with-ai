# 🔨 Product Forge With AI

[![ci](https://github.com/sikomar00/product-forge-with-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/sikomar00/product-forge-with-ai/actions/workflows/ci.yml)

업무 요청·장애 처리 SaaS **OpsDesk**를 기획부터 운영·개선까지 AI와 함께 만드는 터미널 학습 게임입니다. 실제 도구를 실제 환경에서 쓰고, 게임은 결과물과 시스템 상태를 읽어서 채점합니다.

## 왜 만들었나

AI 코딩 도구가 코드를 대신 써 주면 결과물은 나오지만, "무엇을 왜 하는지, 어떤 도구의 어떤 기능을 왜 쓰는지"는 남지 않습니다. 이 게임의 목표는 단계마다 그 이유를 알고, AI에게 지시하고, 결과를 검증할 수 있는 수준까지 가는 것입니다.

- 미션마다 AI 사용 태그가 붙습니다: 🔒 solo(AI 금지) · 🤝 pair(개념 질문·리뷰만) · 🚀 delegate(생성 허용, 대신 설명 게이트와 검증 수단을 통과해야 함).
- 통과한 미션은 카드(개념·용법·도메인·도구 지도)가 되어 Leitner 복습 덱에 들어갑니다.
- 앞선 SQL 학습 게임 [sailingstone-quest](https://github.com/sikomar00/sailingstone-quest)(S1)의 엔진(채점·힌트·복습·XP)을 가져와 확장했습니다([ADR-0001](docs/adr/0001-reuse-s1-engine.md)).

## 어떻게 동작하나

```
미션 수신(요청문) → 카드 → 실제 작업 → quest check
   → 체크리스트 피드백(✅/❌ + 흔한 실수 감지) → 통과 시 보상 + 설명 게이트
   → 카드가 복습 덱에 추가 → 다음 미션
```

**엔진과 콘텐츠를 나눴습니다.** 이 공개 리포는 엔진(`quest` 명령)만 담고, 미션의 요청문·체크·정답은 비공개 콘텐츠 리포에 있습니다([ADR-0006](docs/adr/0006-engine-and-content-zones.md), [ADR-0009](docs/adr/0009-content-in-private-repo.md)). 플레이어가 정답을 미리 보지 않게 하려는 장치이고, 엔진은 콘텐츠의 글을 화면에 내지 않습니다(`quest update`는 바뀐 장 번호와 새 미션 수만, `quest selftest`는 통과·실패 개수와 엔진 쪽 오류 위치만 보여 줍니다).

| 영역 | 위치 | 하는 일 |
|---|---|---|
| 명령 | `quest/cli.py`, `quest/commands/` | 홈·미션·채점·힌트·복습·시험·장애 등 19개 명령 |
| 콘텐츠 불러오기 | `quest/core/content.py` | 콘텐츠(Python 모듈, [ADR-0005](docs/adr/0005-content-as-python-modules.md))를 불러와 검증하고 엔진과의 버전 호환을 확인 |
| 체크 프리미티브 | `quest/checks/` | 파일·셸·Git·GitHub·HTTP·SSH 상태를 **읽기 전용**으로 검사([ADR-0004](docs/adr/0004-read-only-state-checks.md)). 화면 출력 대신 종료 코드·JSON·형식 지정 출력을 읽음 |
| 학습 상태 | `quest/core/state.py`, `review.py`, `progress.py` | SQLite(STRICT 표)에 진행·시도·힌트·복습을 기록([ADR-0003](docs/adr/0003-learning-state-in-sqlite.md)). Leitner 5단계 복습과 복습 잠금 |
| 장애 주입 | `quest/chaos/` | 허용된 대상(제품 리포, `~/forge-sandbox/`, `pf-lab*` OrbStack 머신)에만 장애를 넣고, 넣기 전에 스냅샷을 떠서 되돌림([ADR-0007](docs/adr/0007-chaos-injection-safety.md)) |
| 리뷰봇 | `quest/labs/reviewbot.py` | 2장에서 학습자 PR diff를 보고 `gh`로 리뷰 코멘트를 닮([ADR-0011](docs/adr/0011-reviewbot-runs-before-check.md)) |

명령 목록(`quest help`):

```
quest — Product Forge With AI

  quest                        홈: 등급·XP·진행·현재 미션
  quest mission [ID]           미션 보기. ID를 빼면 현재 미션
  quest check [ID]             채점
  quest hint [ID]              다음 단계 힌트(감점)
  quest solution [ID]          모범 답안(보상 20%만)
  quest review                 복습: 만기 카드(최대 15장)
  quest exam                   승급 시험: 현재 장 보스에 먼저 도전
  quest back                   시험·복습 모드를 끝내고 돌아가기
  quest map [장]                장 지도. 장 번호를 주면 그 장의 미션 목록
  quest goals                  졸업 기준 13개 영역의 충족 상태
  quest stats [--sql "SELECT…"] 기록: 시간·힌트·확신·복구, SQL
  quest status --json          기계가 읽는 현재 상태(AI 튜터용)
  quest reset                  진행 초기화(백업을 남긴다)
  quest doctor                 장비 점검: 도구 설치와 허용 버전
  quest update                 콘텐츠 받기·갱신
  quest selftest               받은 콘텐츠의 테스트를 이 엔진으로
  quest incident status|abort  장애 보기·중단(원상 복구)
  quest report [ID]            미션 오판 신고(콘텐츠 리포 이슈)
  quest help                   명령 목록
```

채점 화면은 이런 모습을 목표로 설계했습니다([설계서 3.9절](docs/design.md)의 예시):

```
$ quest check
  채점 중… [5-8]
   ✅ GET /tickets 는 요청자 본인 티켓만 반환
   ❌ GET /tickets/{다른 사람 ID} → 404 또는 403 이어야 함   (현재 200)
   ✅ 담당자는 배정된 티켓 조회 가능
   ❌ 관리자만 담당자 변경 가능                              (요청자 토큰으로 200)
  💡 흔한 실수: 목록에는 필터를 걸었지만 상세 조회는 ID만 보고 반환하고 있어요(IDOR).
```

## 18장 구성

0~2장은 전 과정에서 계속 쓰는 기반 도구이고, 3장부터는 실제 제품 개발 순서를 따릅니다. 미션 207개(코어 177 + 선택 30), 코어 약 235시간(추정)입니다.

| 장 | 주제 | OpsDesk 산출물 |
|---|---|---|
| 0 | 작업장: 개발 환경과 AI 코딩 도구 | 개발 환경, AI 튜터 모드 |
| 1 | 터미널·Linux | 서버 점검 스크립트 |
| 2 | Git·GitHub 협업 | `opsdesk` 리포 |
| 3 | 기획 | PRD·백로그 |
| 4 | 설계 | 다이어그램·ERD·권한 매트릭스·ADR |
| 5 | 백엔드(FastAPI·PostgreSQL) | API v0.1 |
| 6 | 비동기·외부 연동 | SLA·알림 파이프라인 |
| 7 | 프론트엔드(Next.js) | 웹 v0.1 |
| 8 | 테스트·품질 | 품질 게이트 |
| 9 | 컨테이너 | 원커맨드 개발 환경 |
| 10 | 배포·인프라 선택 | **v0.1 공개** |
| 11 | CI/CD | PR 검증 + 자동 배포 |
| 12 | 쿠버네티스 비교 | K8s 필요성 판단 리포트 |
| 13 | 클라우드·IaC | 리포 설정·DNS 코드화 |
| 14 | 운영·관측 | 운영 대시보드·포스트모템 |
| 15 | 제품 안의 AI | AI 품질 리포트 |
| 16 | 분석·개선·런칭 | **v1.0** |
| 17 | Forge Run(최종) | 개선 사이클 리포트·졸업 |

장별 도구와 시간은 [설계서 5절](docs/design.md)에 있습니다.

## 맥에서 시작하기

1. 준비 점검: `curl -fsSL https://raw.githubusercontent.com/sikomar00/product-forge-with-ai/main/scripts/check-mac.sh -o check-mac.sh && bash check-mac.sh` — 이미 설치된 것과 빠진 것, 설치 명령을 보여 준다(읽기만 한다). 마지막 '필요한 것'만 차례로 한다.
2. 엔진 받기: `git clone https://github.com/sikomar00/product-forge-with-ai.git ~/code/product-forge-with-ai && cd ~/code/product-forge-with-ai && uv sync`
3. 점검: `uv run quest doctor` (콘텐츠를 받기 전에는 엔진 쪽만 본다)
4. 어디서나 `quest`로 부르기(선택): `echo "alias quest='uv run --project ~/code/product-forge-with-ai quest'" >> ~/.zshrc && source ~/.zshrc`
5. 처음 `quest`를 실행하면 설정 파일(`~/.config/quest/config.toml`)을 만든다. `<GitHub 사용자 이름>` 두 곳을 내 값으로 바꾼다.
6. 콘텐츠 리포(비공개)가 생긴 뒤: `gh auth login` → `quest update` → `quest`

- 선택 연결 트랙: [tech-radar-agent](https://github.com/sikomar00/tech-radar-agent)

## 개발과 테스트

Python 3.14와 [uv](https://docs.astral.sh/uv/)를 씁니다([ADR-0002](docs/adr/0002-python-314-with-uv.md)). CI는 Ubuntu와 macOS에서 아래를 차례로 돌립니다.

```bash
uv sync --locked
uv run ruff check
uv run pytest                       # S1 회귀 시험은 QUEST_S1_REPO에 sailingstone-quest 경로를 주면 함께 돈다
uv run python docs/ddl/run_checks.py  # 상태 DB 스키마 점검
```

2026-11-14 기준 결과: ruff 통과, pytest 320개 통과, 스키마 점검 67개 통과.

## 문서

- 설계서: [docs/design.md](docs/design.md) (v0.3.5, 2026-11-09)
- 요구사항(PRD)·데이터 구조(ERD)·명세(Spec): [docs/PRD.md](docs/PRD.md), [docs/ERD.md](docs/ERD.md), [docs/SPEC.md](docs/SPEC.md)
- 용어집·결정 기록·정보 구조·사용자 여정: [docs/GLOSSARY.md](docs/GLOSSARY.md), [docs/adr/](docs/adr/), [docs/IA.md](docs/IA.md), [docs/USER-JOURNEY.md](docs/USER-JOURNEY.md)
- 작업 순서: [docs/PLAN.md](docs/PLAN.md), 현재 작업: [Intent.md](Intent.md)

## 현재 상태

- 엔진 M0 게이트 승인(2026-11-13), M1 중 Windows에서 할 수 있는 작업 완료(2026-11-14), 엔진 태그 `v0.1.0`.
- 콘텐츠는 비공개 리포에서 0장 코어까지 완료(2026-11-14).
- 다음은 맥에서 설치·0장 시작(W1)과 OrbStack 랩·사용자 QA.

> 등장하는 회사(포지랩)·인물·데이터는 모두 가상이며, 이 게임은 AI와 함께 만든 학습 도구입니다.
