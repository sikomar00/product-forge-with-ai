# QA 기록

`rules/qa.md`를 따른다. 결과는 이 문서에만 남긴다(CLAUDE.md 6절). 사용자가 확인한 결과도 아래 "사용자 QA" 표에 적고, 실패는 `Intent.md`로 올린다.

## M0 게이트 (2026-11-13, 브랜치 `engine/windows-setup`)

환경: Windows 11 + uv 0.13.6 + Python 3.14.10 + SQLite 3.53.1. CI(GitHub Actions ubuntu·macos)도 같은 Python·SQLite 빌드다.

| 게이트 (PRD M0) | 확인 방법 | 기대 | 실제 | 결과 |
| --- | --- | --- | --- | --- |
| S1 미션 52개 모범 답안이 새 엔진에서 통과, 같은 시나리오 XP가 S1과 같다 | `tests/test_s1_regression.py` (S1 커밋 `513ec58`) | 52/52, XP 차이 0 | 52/52 통과, 미션 XP 312/312·재구성 52/52·시험 면제 같음 | Pass |
| 가짜 미션으로 IA-1~IA-11, IA-15~IA-17 동작(명령마다 시험) | pytest(아래 표) + 터미널 QA 22개 | 명령마다 시험 있음 | 14개 명령 모두 시험 있음, 터미널 22/22 | Pass |
| 엔진 리포에 콘텐츠 파일이 없다 | `test_no_content_files_outside_fake_fixture` | 0개 | 0개 | Pass |
| `status --json`에 체크 설명·힌트·정답이 없다 | `test_status_json_*` 2개 | 금지 글자 0개, 키 6개만 | 0개, 키 6개 | Pass |
| 500줄 넘는 파일이 없다 | `test_no_code_file_over_500_lines` | 0개 | 0개(가장 긴 코드 289줄 `core/progress.py`) | Pass |
| 엔진 스키마가 `docs/ddl/v1.0.sql`과 같고 점검 67개 통과 | `test_state.py`, `docs/ddl/run_checks.py` | 같음, 67/67 | 같음, 67/67(엔진이 만든 DB에서도) | Pass |

전체 시험: pytest 199/199 (Windows, CI ubuntu, CI macos), ruff 통과(순환 복잡도 10, 인자 3개 이하 포함).

## Claude QA

### 명령별 시험 (pytest)

| IA | 명령 | 시험 파일 |
| --- | --- | --- |
| IA-1 | `quest` | `test_cli_slice.py`, `test_review.py`(잠금 표시) |
| IA-2 | `quest mission [ID]` | `test_cli_slice.py`, `test_review.py`(잠금) |
| IA-3 | `quest check` | `test_cli_slice.py`, `test_cli_items.py`, `test_exam.py`, `test_rebuild.py` |
| IA-4·5 | `quest hint`·`solution` | `test_cli_hints.py`, `test_exam.py`(다시 하기), `test_rebuild.py`(재구성 중 차단) |
| IA-6 | `quest map [장]` | `test_records.py` |
| IA-7·8 | `quest exam`·`back` | `test_exam.py`, `test_rebuild.py` |
| IA-9 | `quest review` | `test_review.py`, `test_rebuild.py` |
| IA-10 | `quest goals` | `test_records.py`, `test_exam.py` |
| IA-11 | `quest stats [--sql]` | `test_records.py` |
| IA-15 | `quest status --json` | `test_records.py` |
| IA-16 | `quest help` | `test_cli_slice.py`, `test_records.py` |
| IA-17 | `quest reset` | `test_records.py` |

### 터미널 QA (2026-11-13, 실제 `uv run quest` 실행, 가짜 콘텐츠)

| ID | 명령 | 기대(종료 코드 · 화면) | 결과 |
| --- | --- | --- | --- |
| IA-16 | `quest help` | 0 · 명령 목록 | Pass |
| IA-16b | `quest nope` | 2 · 도움말 | Pass |
| IA-1 | `quest` | 0 · 현재 미션 0-1 | Pass |
| IA-2 | `quest mission` | 0 · 요청문 | Pass |
| IA-3a | `quest check`(파일 없음) | 1 · ❌ 체크와 방향 힌트 | Pass |
| IA-4 | `quest hint` + y | 0 · 💡 힌트 1/3 | Pass |
| IA-3b | `quest check` + 설명 게이트 | 0 · +8 XP(힌트 감점) | Pass |
| IA-5 | `quest solution 0-1`(끝낸 미션) | 0 · 감점 없이 모범 답안 | Pass |
| IA-3c | `quest check`(퀴즈) | 0 · +6 XP(원샷) | Pass |
| IA-6 | `quest map`, `quest map 0` | 0 · 장 목록, 미션 목록 | Pass |
| IA-10 | `quest goals` | 0 · 졸업 기준 1/13 | Pass |
| IA-11 | `quest stats`, `--sql SELECT`, `--sql DELETE` | 0, 0, 2 · 읽기만 됨 | Pass |
| IA-15 | `quest status --json` | 0 · 현재 미션 0-3 | Pass |
| IA-9 | `quest review` | 0 · 만기 카드 0장 | Pass |
| IA-7 | `quest exam`(0장) | 2 · 0장은 시험 없음 | Pass |
| IA-8 | `quest back`(일반) | 0 · 이미 일반 진행 | Pass |
| IA-17 | `quest reset`(틀린 문구 → '초기화') | 0 · 거절 → 백업 후 초기화, 0 XP | Pass |

합계 22/22 통과, 실패 0.

### 맥에서 다시 볼 것 (Windows에서 확인하지 못함)

- 맥 실제 기기에서의 실행. CI macos 러너(Apple Silicon)에서는 199/199 통과했다.

## 사용자 QA (사람이 직접)

| # | 확인할 것 | 방법 | 정상이면 보이는 것 | 주의점 | 결과 |
| --- | --- | --- | --- | --- | --- |
| U1 | 맥에서 설치·실행 | 먼저 `bash scripts/check-mac.sh`로 이미 있는 것과 빠진 것을 보고, '필요한 것'만 한 뒤 `uv sync`와 `uv run quest help` | 명령 목록과 "백업에서 되돌리기" 안내 | 첫 실행이면 설정 파일을 만들었다는 안내가 함께 나온다 | 미확인 |
| U2 | 화면 모양 | `QUEST_HOME`·`QUEST_CONFIG`를 임시 폴더로 두고 가짜 콘텐츠로 `quest`, `quest map`, `quest goals` | 이모지(🎫🤝🔒)가 깨지지 않고, 한글 장 이름 칸이 맞는다 | 터미널 글꼴에 따라 이모지 폭이 다를 수 있다. 어긋나면 화면을 캡처해 알려 주기 | 미확인 |
| U3 | 색 없이도 구분되는지 | `NO_COLOR=1 uv run quest check` | ✅·❌·💡 기호만으로 통과·실패·트랩이 구분된다 | 색이 꺼진 것이 정상이다 | 미확인 |
| U4 | 문구가 이해되는지 | 위 흐름(미션 → 실패 → 힌트 → 통과 → 복습)을 한 번 따라 하기 | 다음에 칠 명령이 화면 맨 아래에 늘 보인다 | 어색한 문장은 그대로 복사해 알려 주기 | 미확인 |
| U5 | 백업 되돌리기 | `quest reset`(초기화 입력) 뒤, 게임을 끈 상태에서 `backups/`의 파일을 `state.db` 자리에 복사하고 `quest` | 초기화 전 XP와 진행이 돌아온다 | 복사 전에 지금 `state.db`를 지우거나 이름을 바꿔야 한다 | 미확인 |
| U6 | 맥 경로 | 환경 변수 없이 `uv run quest` 한 번 | `~/.config/quest/config.toml`과 `~/.local/share/quest/`가 생긴다 | 아직 실제 콘텐츠가 없어서 "콘텐츠가 없습니다 … quest update" 안내와 종료 코드 3이 정상이다 | 미확인 |

## M1 (Windows 범위, 2026-11-13)

맥이 필요한 것(OrbStack 랩, 랩 VM 대상 실제 주입, `ssh` 체크의 `orb` 명령 형식)은 아직 확인하지 않았다.

### 터미널 QA (실제 `uv run quest`, 로컬 git 콘텐츠 리포)

| ID | 명령 | 기대(종료 코드 · 화면) | 결과 |
| --- | --- | --- | --- |
| IA-18a | `quest update`(처음) | 0 · 바뀐 장 0·1장, 새 미션 9개 | Pass |
| IA-18b | `quest update`(다시) | 0 · 이미 최신 | Pass |
| IA-12 | `quest doctor` | 3 · orb 없음(맥 전용), 나머지 ✅ | Pass |
| IA-19 | `quest selftest` | 0 · 통과 2 · 실패 0 | Pass |
| IA-13a | `quest incident status`(없음) | 0 · 진행 중인 장애 없음 | Pass |
| IA-13b | `quest check 1-2`(주입 전) | 2 · 먼저 장애를 시작하라 | Pass |
| IA-13c | `quest mission 1-2` + y | 0 · 장애 시작 | Pass |
| IA-13d | `quest incident status` | 0 · 1-2 · 0분째 | Pass |
| IA-13e | `quest incident abort` | 0 · 되돌림, 원래 없던 파일은 지워짐 | Pass |
| IA-13f·g | 다시 주입 → 복구 → `quest check 1-2` + 근본 원인 답 | 0 · 장애 복구, 통과 | Pass |
| IA-11 | `quest stats` | 0 · MTTR 표시 | Pass |
| IA-20 | `quest report 1-2` → n | 0 · 이슈를 열지 않음 | Pass |

합계 13/13 통과(+ 파일 복원 확인 1건).

### 맥에서 할 것

| # | 확인할 것 | 방법 | 정상이면 보이는 것 | 주의점 | 결과 |
| --- | --- | --- | --- | --- | --- |
| U7 | OrbStack 미확인 3건(T1-4) | 맥에서 Claude와 함께 확인(머신 안 sshd, 머신 스냅샷, cloud-init 사용자) | 3건 모두 된다, 안 되면 Lima 전환을 묻는다 | Windows에서는 확인할 수 없다 | 미확인 |
| U8 | `ssh` 체크의 명령 형식 | `orb -m pf-lab uname -a`가 머신 안에서 실행되는지 | 리눅스 커널 정보가 나온다 | 다르면 `quest/checks/ssh.py`의 `_command`만 고친다 | 미확인 |
| U9 | 실제 GitHub로 `quest report` | 콘텐츠 리포를 만든 뒤 `quest report` → y | 비공개 콘텐츠 리포에 이슈가 열린다 | 이슈 본문에 체크 설명·힌트가 없는지 본다 | 미확인 |
