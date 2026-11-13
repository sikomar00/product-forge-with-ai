# Plan v1.1 — M0(엔진)·M1(0~4장) 구현 (승인 2026-11-09, v1.1 2026-11-13)

## Context
하네스 1~6단계 문서가 모두 승인됐다(GLOSSARY, ADR-0001~0009, IA v1.2, UJ v1.1, PRD v1.2, ERD v1.0, Spec v1.0). 코드는 아직 없다. 이 Plan은 PRD의 M0·M1을 게이트까지 만드는 순서와 분담, 라이브러리, 사용자 작업을 정한다. 이 Plan을 승인하면 **아래 라이브러리 목록과 사용자 작업도 함께 승인한 것으로 본다.** 승인 범위 안에서는 끊지 않고 진행하고, 범위 밖(main 머지·PR·삭제·새 라이브러리·비용)은 멈춰서 묻는다.

2026-11-09 Plan 인터뷰 결정:
1. 시작일(W1)은 날짜가 아니라 조건이다. **M0 게이트 통과 + 0장 부분 완료**(0장 콘텐츠, `quest doctor`, `quest update`)가 되면 시작한다. 첫 세로 조각(T0-4)을 마치면 실측으로 예상 날짜를 다시 계산해 알린다.
2. 엔진은 사용자가 **로컬 Claude Code**로 바이브코딩한다. 2026-11-13 변경: **Windows에서 할 수 있는 만큼 먼저 하고, 맥에서 클론받아 마무리한다.** 작업은 GitHub 작업 브랜치로 옮긴다. OrbStack 랩(T1-4)·실제 장애 주입(T1-3)·맥 SQLite 버전 확인·M0 게이트 최종 확인은 맥에서 한다. Windows에서 깔린 도구: uv 0.13.6(2026-10-27), Python 3.14.10(SQLite 3.53.1, DDL 점검 67/67).
3. 콘텐츠 리포 이름은 `product-forge-content`(비공개, 사용자가 만든다).
4. S1 회귀 테스트에는 **테스트 전용 pandas 3.0.3**을 쓴다.

## 분담
| 누가 | 무엇 | 어디서 |
| --- | --- | --- |
| 사용자 + AI(바이브코딩) | 엔진 구역: T0-1~T0-9, T1-1~T1-5 | Windows 로컬 Claude Code에서 먼저, 맥 로컬 Claude Code에서 마무리. 엔진 리포 |
| AI | 콘텐츠 구역: T1-6~T1-10, 문서 갱신 | 클라우드 세션, 콘텐츠 리포(엔진 작업 세션에는 연결하지 않는다) |
| 사용자 직접 | 리포·계정 생성, 비밀값 입력, 머지 승인 | GitHub, 맥 |

## 구조
Spec v1.0 "패키지 구조"를 그대로 따른다. 의존은 안쪽으로만 향한다. `core/`(상태·규칙)는 `kinds/`·`checks/`·`chaos/`·`cli.py`를 모르고, DB는 `core/state.py`에서만, 외부 명령(git·gh·orb)은 `checks/`·`chaos/`·`labs/`에서만 부른다. 근거: Clean Architecture의 의존성 규칙(Tech Radar Plan v1.0과 같은 2차 자료 기준, 원문 미확인).
- 실행: 엔진 리포에서 `uv sync` 후 `uv run quest`(셸 별칭 `quest`). 개발 환경과 플레이 환경이 같아서 `quest selftest`가 pytest를 쓸 수 있다.
- 규칙: 파일 최대 500줄, 함수 권장 30줄, 순환 복잡도 10 이하(ruff C901로 강제), 공개 함수에 타입 힌트(`rules/code.md`).

## 라이브러리 목록 (2026-11-09 PyPI 조회)
| 이름 | 버전 | 쓰는 곳 | 이유 |
| --- | --- | --- | --- |
| `pytest` | 9.2.0 | 개발·`quest selftest` | 테스트. Tech Radar가 같은 버전으로 시험 351개를 돌리는 중. 2026-10-27 출시(13일 전) |
| `ruff` | 0.17.2 | 개발 | 린터·포매터. 순환 복잡도 규칙(C901). 2026-10-22 출시. 최신 0.17.4는 4일밖에 안 돼서 뺐다 |
| `pandas` | 3.0.3 | S1 회귀 테스트 전용 | S1 Python 미션 10개 채점. S1을 만든 날(2026-10-12)의 최신 버전(날짜로 한 추정). Python 3.14 맥 arm64·리눅스 빌드 있음. 하위 의존성 numpy ≥ 2.3.3, python-dateutil |
| `uv_build` | 0.13.6 | 빌드 백엔드 | `quest` 명령 설치용. uv와 같은 버전(2026-10-27). 2026-11-13 추가 승인 |

- 엔진 실행에 필요한 외부 라이브러리는 없다. argparse, sqlite3, tomllib, zoneinfo, importlib, subprocess, urllib·ssl(http 체크), zlib·base64(난독화), json, xml.etree(JUnit XML), dataclasses, pathlib을 쓴다. httpx는 쓰지 않는다(Spec "Plan에서 정한다" → 표준 라이브러리로 충분).
- 하위 의존성의 정확한 버전은 `uv lock`이 만든 `uv.lock`으로 고정하고 T0-1에서 목록을 보고한다.
- CI 액션은 커밋 SHA로 고정한다: `actions/checkout` v7.0.1(`3d3c42e5aac5ba805825da76410c181273ba90b1`), `astral-sh/setup-uv` v10.3.3(`68559e99cc807c1eb7e9238fd43a15bba460eec2`). 릴리스 날짜는 확인하지 못해서 T0-1에서 확인하고, 2주가 안 됐으면 바로 앞 태그를 쓴다.

## 사용자 작업 (필요한 시점에 다시 알려 드린다)
1. (T0-0) 문서 브랜치 `claude/harness-setup`을 main에 머지하는 PR을 승인한다. 지난 브랜치 `claude/design-v0.3` 삭제도 GitHub에서 직접 한다(세션에서는 삭제가 막혀 있다).
2. (T0-1 전, 완료 2026-11-13) Windows에 uv·Python 3.14를 깔았다. (맥으로 옮길 때) 맥에서 엔진 리포를 `git clone`하고 작업 브랜치를 받은 뒤 `uv sync`를 하고, 맥 로컬 Claude Code를 엔진 리포에서 연다(CLAUDE.md 하네스가 자동으로 적용된다).
3. (T1-6 전) GitHub에서 비공개 리포 `product-forge-content`를 만들고, 콘텐츠 작업용 클라우드 세션에 연결한다.
4. (T1-9 전, 2장 출시 점검) 자동화 전용 GitHub 머신 계정 1개를 만들고, 토큰을 `product-forge-content`의 Actions 비밀값에 직접 넣는다. 채팅에는 붙이지 않는다.
5. (UJ-1) 맥에서 `gh auth login`을 한다. `quest update`가 처음에 `gh auth setup-git`을 안내한다.

## M0 작업 순서 (PRD M0-01~19, 게이트와 대응) — 사용자 + AI
- **T0-0 문서 마무리**(AI): `docs/PLAN.md`(이 Plan), `Intent.md`(하네스 8단계) 작성. CLAUDE.md 6절에 "엔진 작업 중 AI는 콘텐츠 위치(`~/.local/share/quest/content`)를 읽지 않는다"를 더한다. 문서 브랜치 PR(사용자 승인).
- **T0-1 리포 기본** 📐2~3h: `pyproject.toml`(Python 3.14, 위 라이브러리), `uv.lock`, ruff 설정, GitHub Actions(ruff·pytest·DDL 점검·500줄 검사, ubuntu·macos 러너 둘 다), `.gitignore` 보강, `.gitattributes`(`* text=auto eol=lf`, Windows 줄바꿈 차단).
- **T0-2 상태 DB** 📐3~5h: `core/config.py`(QUEST_HOME·QUEST_CONFIG), `core/state.py`, `core/schema/v1_0.sql`, SQLite 버전 확인. 시험: 스키마 비교, DDL 점검 67개(M0-03, M0-19).
- **T0-3 콘텐츠 불러오기와 가짜 콘텐츠** 📐4~6h: Spec의 미션 스키마 dataclass, 불러오기·검증·호환 확인, `tests/fixtures/fake_content/`(8가지 유형)(M0-04, M0-05, M0-18).
- **T0-4 첫 세로 조각** 📐5~8h: `progress.py`, `kinds/ops.py`, IA-1 홈·IA-2 미션·IA-3 채점·IA-16 도움말. 가짜 실습 미션 하나가 처음부터 끝까지 돈다. **여기서 실제 걸린 시간을 재고 W1 예상일을 다시 계산한다.**
- **T0-5 보상·힌트·모범 답안** 📐3~5h: `rewards.py`(S1 `on_success`와 같은 계산), `spoiler.py`(`obf1:`), IA-4·IA-5(M0-08, M0-09).
- **T0-6 나머지 유형·복습·잠금·시험** 📐6~10h: `kinds/` 나머지, 설명 게이트·확신도, `review.py`(Leitner·재구성·지연 확인 퀴즈), 복습 잠금, IA-7·IA-8·IA-9(M0-07, M0-10~M0-14).
- **T0-7 기록과 상태 출력** 📐5~8h: 이벤트 22종, IA-6 지도·IA-10 goals·IA-11 stats(`--sql` 읽기 전용)·IA-15 `status --json`·IA-17 reset(백업)(M0-06, M0-15, M0-16).
- **T0-8 S1 회귀** 📐4~8h: `tests/` 안의 S1 어댑터, S1 리포를 읽기 전용으로 참조해 52개 모범 답안 채점·XP 비교(M0-17).
- **T0-9 M0 게이트** 📐2~3h: 게이트 숫자 보고, `code-review` 스킬, QA(`rules/qa.md` → `docs/qa-guide.md`), 승인.
- M0 합계 📐34~56h(근거 있는 실측 없음. T0-4 뒤에 다시 계산).

## M1 작업 순서 (PRD M1-01~11) — 엔진은 사용자 + AI, 콘텐츠는 AI
- **T1-0 0장 부분 엔진** 📐4~6h: `quest doctor`(IA-12)와 `quest update`(IA-18). 시험용 콘텐츠 리포(로컬 git)로 시험(M1-02, M1-03). → M0 게이트와 함께 **W1 시작 조건**.
- **T1-1 체크 프리미티브 6종** 📐8~12h: fs·shell·ssh·git·github(`ctx.gh`, 기록 재생 가능)·http, 단위 테스트와 읽기 전용 시험(M1-01). 장 순서에 맞춰 1장에 필요한 것부터.
- **T1-2 selftest·report** 📐4~6h: IA-19(내용 가림), IA-20(이슈 본문에 금지 항목 없음 시험)(M1-04, M1-11).
- **T1-3 장애 주입** 📐6~10h: `chaos/`, 주입 허용 대상, 스냅샷·abort, IA-13. 1-I1 전에 끝낸다(M1-05).
- **T1-4 OrbStack 랩** 📐4~8h: 먼저 미확인 3건을 맥에서 확인한다(머신 안 실습용 sshd, 머신 스냅샷, cloud-init 사용자 생성). 그다음 `labs/linux-vm.yml`과 머신 생성(M1-06). 안 되는 것이 나오면 Lima로 바꿀지 그때 묻는다.
- **T1-5 리뷰봇** 📐3~5h: 게임이 로컬에서 `gh api`로 PR 리뷰 코멘트를 단다. 2-4 전에 끝낸다(M1-07).
- **T1-6 콘텐츠 리포 골격**(AI): `content.toml`, `keys.lock`, CI(엔진 태그 고정), 기록 재생 장치, 플레이스루 러너. GitHub 러너에서 systemd를 쓸 수 있는지 먼저 확인한다(M1-08, M1-09).
- **T1-7 0장 콘텐츠**(AI): 코어 9개, 미션 테스트, 플레이스루. → **W1 시작 조건**.
- **T1-8 1~4장 콘텐츠**(AI): 학습자보다 한 장 앞서서 한 장씩. 장마다 미션 테스트, 플레이스루(기록 재생), 보고는 개수만(M1-08, M1-10).
- **T1-9 출시 점검**(AI): GitHub가 필요한 장(2장)은 내보내기 전에 머신 계정으로 실제 GitHub 플레이스루를 돌리고 기록을 갱신한다(M1-09).
- **T1-10 M1 게이트**(AI + 사용자): 4장까지 끝나면 숫자 보고와 승인.
- M1 엔진 합계 📐29~47h. 콘텐츠(T1-6~T1-9)는 AI가 하므로 사용자 시간은 머지 승인과 `quest update` 정도다.

## 위험
| 위험 | 대응 |
| --- | --- |
| 엔진 제작 시간의 실측이 없다 | T0-4 뒤에 다시 계산하고 W1 예상일을 알린다 |
| 학습 시간과 엔진 작업 시간이 같은 주 20시간을 나눠 쓴다. 1~4장을 플레이하는 동안 M1 엔진 작업 T1-1~T1-5(📐25~41h)가 함께 돈다 | 1·2장을 마치면 실측으로 전체 일정을 다시 계산한다(design.md 3.8절) |
| OrbStack 미확인 3건 | T1-4 첫머리에서 확인. 안 되면 Lima 전환을 묻는다 |
| pandas 3.0.3과 S1 코드가 맞지 않을 수 있다 | T0-8에서 실패하면 원인을 보고하고 버전을 다시 정한다 |
| GitHub 러너에서 systemd를 못 쓸 수 있다 | VM 미션 플레이스루를 맥에서 돌리고 개수만 보는 방식으로 바꾼다 |
| Windows에서 되던 것이 맥에서 깨진다(줄바꿈·경로·SQLite 버전) | `.gitattributes`로 LF 고정, 경로는 `pathlib`만, CI를 macos 러너에서도 돌린다. 맥으로 옮기면 게이트 숫자를 맥에서 다시 잰다 |
| 로컬 AI가 콘텐츠를 읽을 수 있다 | 콘텐츠는 엔진 리포 밖에 있고, CLAUDE.md에 읽지 않는 규칙을 더한다(T0-0) |

## 검증
- 엔진: `uv run ruff check`, `uv run pytest`(통과 수 보고), `python docs/ddl/run_checks.py`(67/67), 스키마 비교, S1 회귀 52/52, `status --json` 키 시험, 500줄 검사가 모두 CI에서 초록이어야 한다.
- 손으로 돌려 보기: `QUEST_HOME=$(mktemp -d) uv run quest`로 가짜 콘텐츠에서 홈 → 미션 → 채점 → 힌트 → 모범 답안 → 복습 → 시험 → `quest back` → `quest reset`(백업 파일 생성)까지.
- M1: 콘텐츠 리포 CI 초록(개수만), 맥에서 `quest selftest`, 플레이스루 0장 첫 미션~4장 보스, 장애 시험(주입 허용 대상 밖이면 거절), `quest update` 호환·비호환 시험.
- QA: `rules/qa.md`대로 `docs/qa-guide.md`에 Claude QA와 사용자 QA 목록을 남긴다. 사용자 QA 예: 홈 화면 문구와 색 없이도 구분되는지, 맥에서 OrbStack 랩 생성, 실제 맥 경로.

## 승인 뒤 바로 할 일
1. 이 Plan을 `docs/PLAN.md`로 저장하고, `Intent.md`(하네스 8단계)를 쓴다. CLAUDE.md 6절에 콘텐츠 읽기 금지 줄을 더한다.
2. `claude/harness-setup`에 커밋·푸시한다(클라우드 세션 규칙).
3. main 머지 PR은 따로 여쭙는다.
