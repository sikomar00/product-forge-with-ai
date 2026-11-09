# Spec v1.0 (초안 2026-11-09, 승인 대기)

기준: `docs/PRD.md` v1.2, `docs/ERD.md` v1.0, ADR-0001~0009, `docs/IA.md` v1.2, `docs/USER-JOURNEY.md` v1.1, 2026-11-09 Spec 인터뷰 결정. M0·M1은 구현할 수 있는 수준으로 쓴다. M2~M4는 PRD 원칙대로 각 단계를 시작하기 전에 덧붙인다. 콘텐츠의 구체 내용(미션별 체크·정답·힌트)은 이 문서에 쓰지 않는다(ADR-0006).

## 공통

### 파일 위치 (IA "저장 위치")

| 무엇 | 경로 | 비고 |
| --- | --- | --- |
| 설정 | `~/.config/quest/config.toml` | 환경 변수 `QUEST_CONFIG`로 바꿀 수 있다(테스트용) |
| 게임 데이터 루트 | `~/.local/share/quest/` | 환경 변수 `QUEST_HOME`으로 바꿀 수 있다(테스트·플레이스루용) |
| 학습 상태 DB | `<루트>/state.db` | ERD v1.0 |
| 백업 | `<루트>/backups/state-YYYYMMDDTHHMMSSZ.db` | `quest reset`이 만든다 |
| 콘텐츠 | `<루트>/content/` | `quest update`가 받는다. 학습자는 열지 않는다 |
| 장애 스냅샷 | `<루트>/snapshots/<incident_id>/` | 복구하거나 중단하면 지운다 |
| 복습 샌드박스 | `~/forge-sandbox/<화면 번호>-<YYYYMMDD>/` | 재구성 복습용 빈 폴더 |

- 학습자의 작업 공간(OpsDesk 리포, 샌드박스)은 게임 데이터 루트와 엔진 리포 밖에 둔다(IA).

### 설정 파일

```toml
[product]
repo_path = "~/code/opsdesk"          # OpsDesk 리포(2-2에서 만든다)
github_owner = "<GitHub 사용자 이름>"

[content]
repo = "<owner>/<콘텐츠 리포 이름>"     # 비공개. 이름은 Plan에서 정한다
path = "~/.local/share/quest/content"

[lab]
vm_name = "pf-lab"                    # OrbStack 머신 이름. 주입 허용 대상 규칙(M1)에 쓰인다

[review]
lock_threshold = 20                   # 복습 잠금 기준(UJ 결정 3)
```

- 토큰과 비밀번호는 설정 파일에 쓰지 않는다(NF-07). GitHub 호출은 `gh`의 로그인을 쓴다.
- 설정 파일이 없으면 첫 실행 때 기본값으로 만들고, 바꿔야 할 칸을 안내한다.

### 버전과 호환

- 엔진 버전은 SemVer(`0.MINOR.PATCH`)이고 `pyproject.toml`에 둔다.
- 콘텐츠 리포 루트의 `content.toml`에 `requires_engine`(예: `">=0.1,<0.2"`)과 장별 도구 허용 버전(`[tools]`)을 둔다. 콘텐츠 버전은 콘텐츠 리포의 git 커밋(짧은 해시)이다.
- 엔진이 `requires_engine`을 만족하지 않으면 콘텐츠를 불러오지 않고 엔진 갱신을 안내한다(UJ-9).
- DB `meta`에 `schema_version`, 마지막 실행 `engine_version`, 마지막 갱신 `content_version`을 둔다.

### 화면과 종료 코드

- 문구는 한국어다(ADR-0008). 색은 보조이고 ✅·❌·💡 같은 기호를 함께 써서 색 없이도 구분된다. `NO_COLOR` 환경 변수가 있으면 색을 끈다.
- 시각은 UTC로 저장하고 화면에는 `Asia/Seoul`로 보여 준다(표준 라이브러리 `zoneinfo`).
- 종료 코드: `0` 성공(채점 통과 포함), `1` 채점 실패, `2` 사용법 오류, `3` 환경 오류(설정·콘텐츠·SQLite 버전·도구 없음).

## M0 · 엔진

### 패키지 구조 (M0-01)

```
quest/
├── cli.py            # 명령 해석(IA-1~IA-20), 종료 코드
├── core/
│   ├── config.py     # 설정·경로(QUEST_HOME, QUEST_CONFIG)
│   ├── state.py      # SQLite 연결·스키마 적용·트랜잭션
│   ├── schema/v1_0.sql   # docs/ddl/v1.0.sql과 같은 내용(테스트로 비교)
│   ├── content.py    # 콘텐츠 불러오기·검증·호환 확인
│   ├── progress.py   # 현재 미션, 장 시작·완료, 잠금
│   ├── rewards.py    # 보상(S1과 같은 계산)
│   ├── review.py     # Leitner, 재구성 복습, 지연 확인 퀴즈
│   ├── spoiler.py    # 난독화와 표시 규칙
│   └── ui.py         # 출력, 색, 시각 표시
├── kinds/            # ops, quiz, predict, drill, decision, audit, incident, boss
├── checks/           # M1부터
├── chaos/            # M1부터
└── labs/             # M1부터(linux-vm.yml 등)
```

- 파일은 `rules/code.md`의 최대 500줄을 지킨다.

### 미션 스키마 (M0-04, ERD)

design.md 8.3절 스키마에서 바꾸고 더하는 것:

- `key: str` 추가. 미션 키(`m_` + 소문자 16진수 8자리). 한 번 정하면 바꾸지 않는다.
- `id: str`은 화면 번호(예: `"5-8"`)다. 콘텐츠 모듈의 `MISSIONS` 튜플 순서가 장 안의 순서다.
- `checks`: `Check(no, desc, fn, hint)`. `no`는 1부터 빈틈없이 이어진다. `fn(ctx) -> Result(ok: bool, detail: str)`이고 읽기 전용이다. `detail`은 화면용이라 DB에 저장하지 않는다.
- 카드: `Card(key, kind, front, back, grading, choices)`. `key`는 `c_` + 8자리, `kind`는 `concept`·`usage`·`domain`·`tool_map`, `grading`은 `choice`(객관식)·`regex`·`self`(자가 채점) 가운데 하나다.
- 퀴즈·예측·결정·드릴·설명 게이트 문항: `Item(no, prompt, kind, choices, answer, ask_confidence)`. `answer`는 난독화한다.
- `hints`(3개)와 `solution`은 난독화 문자열이다.
- `solve: Callable[[Ctx], None] | None` 추가. 자동 플레이스루가 모범 답안을 적용하는 함수다(콘텐츠 구역). 문항형 미션은 플레이스루가 정답을 자동 입력한다.
- `requires_lab: bool = False` 추가(1장 VM 미션 등), `badge: str | None = None` 추가(통과하면 주는 배지).
- `Ctx`: 체크와 `solve`가 받는 맥락. `workdir`(OpsDesk 리포 또는 샌드박스), `config`, `lab`(VM 이름), `gh`(GitHub 호출기. 실제 호출 또는 기록 재생), `now`.

### 콘텐츠 불러오기 (M0-04, M0-05)

- 설정의 `content.path`에서 `content.toml`을 읽고 `requires_engine`을 확인한 뒤, `content/ch*.py`를 `importlib`로 불러온다. 각 모듈은 `MISSIONS`와, 있으면 `DELAYED_QUIZ`(지연 확인 퀴즈 문항 10개)를 내놓는다.
- 불러올 때 검증한다: 미션 키·카드 키 형식과 중복, 화면 번호 중복, 장 번호 0~17, 체크·문항 번호가 1부터 이어지는지, `est_min > 0`, 힌트 3개. 하나라도 어긋나면 어느 미션이 왜 틀렸는지 알리고 종료 코드 3으로 멈춘다.
- 키 불변(ERD 가정 2)은 콘텐츠 리포의 `keys.lock`(키와 처음 붙은 화면 번호를 추가만 하는 목록)과 비교하는 콘텐츠 테스트가 막는다. 엔진은 이 파일을 읽지 않는다.
- 선택 미션은 콘텐츠에 만들어진 것만 보인다. 열고 싶으면 AI에게 요청하고 `quest update`로 받는다.

### 상태 DB (M0-03, M0-19, ERD)

- 시작할 때 `sqlite3.sqlite_version`이 3.37 이상인지 확인하고, 낮으면 이유와 함께 종료 코드 3으로 멈춘다. 연결마다 `PRAGMA foreign_keys = ON`을 켠다.
- DB가 없으면 `quest/core/schema/v1_0.sql`로 만든다. 이 파일은 `docs/ddl/v1.0.sql`과 같아야 한다(테스트).
- 명령 하나의 쓰기는 트랜잭션 하나로 묶는다.
- `quest stats --sql "<SELECT…>"`는 읽기 전용 연결(`file:…?mode=ro`, `uri=True`)로 실행해, 학습자의 SQL이 상태를 바꾸지 못하게 한다.

### 진행 규칙

- **현재 미션**: 콘텐츠 순서(장 → 장 안의 순서)에서 통과·면제가 아닌 첫 코어 미션. 저장하지 않고 계산한다(ERD 가정 5).
- **미션 시작**: `quest mission`이 그 미션을 처음 보여 줄 때다. 이때 `mission_progress` 행을 만들고(`started_at`, `est_min`·`ai_tag` 사본), `mission_started` 이벤트를 남긴다. 복습 잠금 확인도 이때 한다.
- **장 시작·완료**: 장의 첫 미션이 시작되면 `chapter_progress.started_at`, 보스를 통과하면 `completed_via = 'boss'`, 시험으로 통과하면 `'exam'`.
- **잠긴 장**: 현재 장보다 뒤의 장은 IA-6에서 이름만 보인다.
- 면제된 미션은 `quest mission <ID>`로 언제든 다시 할 수 있다. 보상은 없다.

### 채점 (M0-07, M0-10, M0-11)

`quest check [ID]`(ID가 없으면 현재 미션, 시험·복습 모드면 그 대상):

1. 실습·감사·장애·보스 미션: 체크를 번호 순서대로 모두 실행한다. 환경 문제(도구 없음, 네트워크)로 체크가 끝나지 못하면 그 시도는 `outcome = 'error'`이고 실패 수에 세지 않는다.
2. 퀴즈·예측·결정·드릴 미션: 문항을 그 자리에서 묻고 바로 채점한다. 퀴즈와 예측은 확신도(1~3)를 함께 받는다. 문항마다 `responses`에 남긴다.
3. 실패하면 트랩을 차례로 돌려, 걸린 것의 메시지를 💡로 보여 준다.
4. 표시: 실습·보스 미션은 체크마다 ✅/❌와 설명, 실패한 체크의 방향 힌트를 보여 준다. 감사·장애 미션은 통과 개수와 방향만 보여 준다(IA 결정 4).
5. 통과하면 보상을 계산하고, 🤝·🚀 미션은 설명 게이트 문항을 묻는다. 게이트 문항을 하나라도 틀리면 그 미션은 통과하지 않는다. 다시 `quest check`를 하면 체크와 게이트를 처음부터 다시 본다(design.md 3.5절).
6. 최종 통과: 카드를 1번 상자에 넣고(만기는 다음 날), 배지가 있으면 주고, `mission_progress`를 통과로 바꾸고, 다음 미션을 안내한다.
7. `quest check`를 실행할 때마다 `attempts`에 한 행을 남긴다. 체크는 번호와 통과 여부만 기록한다.

### 보상 (M0-08) — S1 `engine.py`의 `on_success`와 같은 계산

- 모범 답안을 봤으면 `round(xp × 0.2)`.
- 아니면 `round(xp × max(0.4, 1 − 0.2 × 힌트 수))`에, 실패 0번·힌트 0개면 원샷 보너스 `round(xp × 0.2)`를 더한다.
- 시험 모드로 보스를 통과하면, 그 장의 남은 코어 미션마다 `round(xp × 0.5)`를 주고 면제한다(`how = 'exam_skip'`).
- 재구성 복습을 통과하면 `max(3, round(xp × 0.15))`를 `rebuild_passed` 이벤트 값으로 남긴다.
- 반올림은 Python `round()`(0.5는 짝수 쪽, 은행가 반올림)를 그대로 쓴다. S1과 같은 결과를 내려는 것이다.
- 총 XP = `mission_progress.xp_awarded`의 합 + `rebuild_passed` 이벤트 값의 합. 등급은 장 진행으로 정한다(design.md 3.1절).
- 원샷 5연속 같은 S1 배지 규칙을 가져오고, 미션별 배지는 콘텐츠의 `badge`로 준다.

### 힌트와 모범 답안 (M0-09)

- 난독화 형식: `obf1:` + base64(zlib(UTF-8 원문)). 보안이 아니라 우연히 보는 것을 막는 용도다.
- `quest hint`: 다음 단계 힌트를 보여 주기 전에 감점을 알리고 `[y/N]`으로 확인한다. 보여 주면 `hints_used`를 올리고 `hint_opened`(값: 단계)를 남긴다. 3단계를 다 봤으면 `quest solution`을 안내한다.
- `quest solution`: 같은 방식으로 확인한 뒤 보여 주고, `solution_seen = 1`과 `solution_viewed`를 남긴다. 이렇게 통과한 미션은 재구성 복습에서 먼저 나온다.

### 복습 (M0-12)

- Leitner 상자 간격 📐: 1번 1일, 2번 2일, 3번 4일, 4번 8일, 5번 16일. 맞히면 한 칸 올라가고(최대 5), 틀리면 1번으로 간다. 만기는 복습 시각 + 새 상자의 간격이다.
- `quest review`: 만기 카드를 만기가 오래된 순서로 최대 15장 낸다. 객관식·정규식 카드는 확신도를 함께 받고, 자가 채점 카드는 뒷면을 보여 준 뒤 맞았는지 묻는다.
- 재구성 복습: 마지막 재구성 복습에서 7일이 지났으면, 카드를 마친 뒤 제안한다. 받아들이면 복습 모드가 되고, 대상은 모범 답안을 보고 통과한 미션 → 가장 오래전에 통과한 미션 순서로 고른다. 샌드박스를 만들고 그 미션의 체크를 샌드박스(`ctx.workdir`)에 대고 돌린다.
- 지연 확인 퀴즈: 장을 마치고 14일이 지난 장이 있으면 `quest review`가 그 장의 `DELAYED_QUIZ` 10문항을 한 번 낸다. 다 풀면 `delayed_quiz_done_at`을 채운다.
- 연속 복습일: `quest review`를 끝낸 날짜(한국 시간)가 하루도 빠지지 않고 이어진 날 수.

### 복습 잠금 (M0-13)

- 새 미션을 시작할 때(IA-2에서 처음 보여 줄 때, IA-7 시험 시작)에만 확인한다. `v_due_cards.due`가 `review.lock_threshold` 이상이면 시작하지 않고, 남은 만기 카드 수와 `quest review`를 안내한다.
- 잠금이 처음 걸릴 때 `review_lock_on`, 풀릴 때 `review_lock_off`를 남긴다. 진행 중인 미션, 장애 복구, 복습은 막지 않는다.

### 승급 시험 (M0-14)

- `quest exam`: 현재 장의 보스를 대상으로 시험 모드에 들어간다(`game_state.mode = 'exam'`). 0장·17장, 이미 보스를 통과한 장, 복습 잠금 중에는 거절한다.
- 보스를 통과하면 그 장의 남은 코어 미션(장애 미션 포함)을 면제한다. 선택 미션은 면제하지 않는다. 장은 `completed_via = 'exam'`으로 끝나고 모드는 일반으로 돌아간다.
- `quest back`은 모드를 일반으로 돌리고 `exam_left`(시험) 또는 `rebuild_left`(재구성 복습)를 남긴다.

### 텔레메트리와 `quest stats` (M0-15)

- 이벤트 22종(ERD)을 해당 시점에 남긴다. 값(`payload`)에는 키·숫자만 넣는다.
- `quest stats`: 장별 진행과 예상·실제 시간(`v_mission_time`), 힌트 사용률(`v_hint_rate`), 확신했는데 틀린 비율(`v_overconfidence`), MTTR(`v_mttr`). `--sql`은 위의 읽기 전용 연결을 쓴다.

### `quest status --json` (M0-16)

```json
{
  "schema": 1,
  "mission": {"key": "m_7f3a2c1d", "id": "5-8", "kind": "ops", "ai": "pair"},
  "mode": "normal",
  "remaining_checks": {"numbers": [2, 4], "count": 2},
  "incident_active": false,
  "review_lock": false
}
```

- 이 밖의 키는 넣지 않는다. 체크 설명·힌트·정답은 넣지 않는다(테스트로 확인).

### 초기화와 백업 (IA-17, NF-06, ERD 결정 3)

- `quest reset`: 확인 문구 `초기화`를 입력해야 실행된다. `sqlite3.Connection.backup()`으로 `backups/state-<시각>.db`를 만든 뒤 DB를 새로 만들고, 첫 이벤트 `reset_backup`에 백업 파일 이름을 남긴다.
- 복원: 게임을 끈 상태에서 백업 파일을 `state.db`로 복사한다. `quest help`에 방법을 적는다.

### M0 시험 (게이트와 대응)

- S1 회귀: S1 리포를 읽기 전용으로 참조해, S1 미션 52개의 모범 답안을 새 엔진의 S1 어댑터로 채점하고 같은 시나리오의 XP가 S1과 같은지 비교한다. S1 어댑터와 pandas는 `tests/` 안에만 둔다(pandas 처리는 Plan).
- 가짜 콘텐츠(`tests/fixtures/fake_content/`)에 8가지 유형의 미션을 하나 이상 넣고, IA-1~IA-11·IA-15~IA-17을 명령마다 시험한다.
- 엔진이 만든 DB의 스키마가 `docs/ddl/v1.0.sql`과 같고, `docs/ddl/v1.0-checks.sql` 67개를 통과한다.
- `quest status --json`의 키가 위 목록뿐이다.
- 엔진 리포에 `content/` 폴더와 콘텐츠 파일이 없다. 500줄 넘는 파일이 없다.

## M1 · 0~4장

### 체크 프리미티브 (M1-01)

- 공통 규칙: 결과는 `Result`로 돌려준다. "없음"·"다름"은 `ok=False`이지 예외가 아니다. 도구가 없거나 네트워크가 끊긴 것처럼 환경 문제일 때만 `CheckEnvError`를 낸다(시도는 `error`).
- 모듈별 근거 데이터(design.md 8.4절): `fs`(pathlib), `shell`(subprocess, 상태를 바꾸지 않는 명령만), `ssh`(랩 VM에서 명령 실행), `git`(git CLI의 porcelain·format 출력), `github`(`gh api`의 JSON, `ctx.gh`를 거쳐 기록 재생 가능), `http`(표준 라이브러리 `urllib`·`ssl`. httpx를 쓸지는 Plan).
- 읽기 전용 시험(NF-02): 프리미티브를 실행하기 전후로 대상의 상태(파일 해시, `git status --porcelain`과 HEAD)가 같아야 한다.

### `quest doctor` (M1-02, M0-19)

- 검사: SQLite 3.37 이상, Python 3.14, uv, git, gh와 `gh auth status`, OrbStack(`orb`), 그리고 `content.toml`의 `[tools]`에 적힌 0~4장 도구와 허용 버전.
- 결과는 도구마다 ✅/❌, 찾은 버전, 설치 명령(Brewfile 줄)이다.

### `quest update` (M1-03, UJ-9)

- 처음에는 `gh auth setup-git`으로 git이 gh 로그인을 쓰게 한 뒤 `git clone`으로 콘텐츠 리포를 `content.path`에 받는다.
- 다음부터는 `git fetch` 후 `git show origin/<기본 브랜치>:content.toml`로 `requires_engine`을 먼저 확인한다. 맞으면 `git merge --ff-only`, 맞지 않으면 합치지 않고 엔진 갱신을 안내한다.
- 출력은 바뀐 장과 새 미션 수(미션 키를 비교해 센다)뿐이다. `meta.content_version`을 바꾸고 `content_updated`(값: 이전·새 버전, 새 미션 수)를 남긴다.
- 인증 실패면 `gh auth login`을, 네트워크 실패면 받아 둔 콘텐츠로 계속하라고 안내한다.

### `quest selftest` (M1-04, UJ-10)

- 받아 둔 콘텐츠의 `tests/`를 서브프로세스 pytest로 돌리고(`-q`, `--junitxml`), JUnit XML에서 통과·실패 개수만 읽어 보여 준다. pytest 출력은 화면에 내보내지 않는다.
- 실패하면 테스트 이름에서 화면 번호를, traceback에서 `quest/` 패키지 프레임의 파일·줄만 뽑아 보여 준다. 콘텐츠 쪽 프레임과 오류 메시지는 보여 주지 않는다.
- `selftest_run`(값: 통과·실패 개수)을 남긴다. pytest는 엔진의 개발 의존성이다(Plan).

### 장애 주입 (M1-05, ADR-0007)

- 시나리오 인터페이스(콘텐츠 구역): `inject(ctx)`, `verify(ctx) -> bool`, `cleanup(ctx)`, 그리고 스냅샷 대상 목록.
- 엔진의 순서: 주입 허용 대상인지 확인 → 스냅샷 → `incidents`에 `active` 행 → `inject` → 홈에 경과 시간 표시. 복구 체크를 통과하면 `recovered`, `quest incident abort`면 스냅샷으로 되돌리고 `cleanup` 뒤 `aborted`.
- 스냅샷 종류: 파일·폴더는 tar 묶음, git 리포는 `git bundle --all`과 추적 파일 묶음, VM 안의 변경은 시나리오가 바꾼 파일·서비스와 원래 값의 목록(되돌리기 목록).
- **주입 허용 대상**(ADR-0007의 라벨 규칙): ① 이름이 `pf-lab`으로 시작하는 OrbStack 머신, ② `product.repo_path` 아래 또는 `~/forge-sandbox/` 아래 경로, ③ 라벨 `product-forge.lab=true`가 붙은 Docker 리소스(9장부터), ④ 이름이 `pf-`로 시작하는 k3d 클러스터(12장부터). 그 밖은 엔진이 거절한다. 맥 시스템 경로(`/System`, `/usr`, `/etc`, `~/Library`)와 Tech Radar 리포 경로는 명시적으로 거절한다.
- 진행 중인 장애는 하나뿐이다(ERD). MTTR은 주입 시각부터 복구 체크 통과까지다.

### Linux VM 랩 (M1-06, 2026-11-09 결정: OrbStack 머신)

- `requires_lab`인 미션을 처음 시작할 때, 확인을 받고 OrbStack CLI로 Ubuntu 머신 `pf-lab`을 `quest/labs/linux-vm.yml`(cloud-init)로 만든다. 미션별 준비(실습 파일 등)는 콘텐츠가 한다.
- 머신은 장이 끝나도 지우지 않는다. 지울지는 학습자가 정한다.
- `quest doctor`가 머신 상태도 보여 준다.

### 리뷰봇 (M1-07)

- 2-4의 리뷰봇은 GitHub Actions가 아니라 게임이 로컬에서 `gh api`로 학습자 PR에 리뷰 코멘트를 단다. 지적 목록은 콘텐츠에 있으므로 공개 리포인 `opsdesk`에 올라가지 않는다. 코멘트는 `🤖 리뷰봇:`으로 시작하고 학습자 계정으로 달린다.

### 콘텐츠 리포 구조와 CI (ADR-0009, M1-08)

```
<콘텐츠 리포>/
├── content.toml                 # requires_engine, [tools]
├── keys.lock                    # 미션·카드 키 기록(추가만)
├── content/ch00_workshop.py … ch04_*.py
├── content/tool_maps/
├── tests/test_missions_ch00.py …   # 풀린·안 풀린·흔한 실수 상태, 장애는 inject·verify·cleanup·abort
├── tests/cassettes/             # 기록해 둔 GitHub 응답
└── .github/workflows/ci.yml     # 고정한 엔진 버전으로 미션 테스트와 플레이스루(기록 재생)
```

- CI는 엔진을 태그로 고정해 설치한다(예: `git+https://github.com/<owner>/product-forge-with-ai@v0.1.0`).

### 자동 플레이스루 (M1-09, 2026-11-09 결정)

- 새 `QUEST_HOME`과 빈 OpsDesk 샌드박스 리포에서 0장 첫 미션부터 4장 보스까지, 미션마다 `solve(ctx)`를 적용하고 `quest check`가 통과하는지 차례로 확인한다. 문항형 미션은 정답을 자동 입력한다.
- 평소(CI): GitHub 호출은 `tests/cassettes/`의 기록을 재생한다. 토큰이 필요 없다.
- 장을 내보내기 전: 사용자가 만든 GitHub 머신 계정 1개(약관상 허용, 자동화 전용)로 실제 GitHub에서 한 번 돌리고 기록을 갱신한다. 토큰은 콘텐츠 리포 Actions 비밀값이나 클라우드 세션 자격 증명에만 둔다(NF-07).
- Linux VM 미션: CI 러너(Ubuntu VM) 안에서 같은 cloud-init 파일로 실습 환경을 만들고, 러너 자신을 대상으로 체크한다.
- 결과는 통과·실패 개수만 보고한다(스포일러 규칙).

### 미션 오판 신고 `quest report` (IA-20, 2026-11-09 결정)

- `quest report [ID]`: 진단 정보를 모아 먼저 보여 주고, 확인을 받은 뒤 `gh issue create -R <content.repo>`로 비공개 콘텐츠 리포에 이슈를 연다.
- 담는 것: 미션 키와 화면 번호, 최근 시도 3개의 결과와 체크 번호별 통과 여부, 엔진·콘텐츠 버전, macOS·도구 버전, 학습자가 쓴 한 줄 설명(선택).
- 담지 않는 것: 파일 내용, 토큰, 체크 설명.
- AI의 답글도 스포일러 규칙을 따른다. 정답·힌트·체크 내용 없이 "콘텐츠 버전 X에서 고쳤다"만 쓴다. 학습자는 콘텐츠 코드를 열지 않도록 `gh issue view`로 답글을 본다.

### M1 시험 (게이트와 대응)

- 체크 프리미티브 6종의 단위 테스트(기록한 출력 사용)와 읽기 전용 시험.
- 장애 미션 1-I1·2-I1의 inject·verify·cleanup·abort 시험, 주입 허용 대상 밖이면 거절하는 시험.
- 시험용 콘텐츠 리포로 `quest update`(호환·비호환)와 `quest selftest`(내용 가림) 시험.
- 콘텐츠 리포 CI: 0~4장 코어 미션 50개 테스트와 자동 플레이스루(기록 재생).

## 승인 시 함께 확인할 가정
1. 파일 위치는 XDG 방식(`~/.config`, `~/.local/share`)을 따른다. 설정 경로가 이미 `~/.config/quest/`로 정해져 있어서다.
2. 종료 코드는 0·1·2·3 네 가지다.
3. 선택 미션은 콘텐츠에 만들어진 것만 보인다. 열 때는 AI에게 요청하고 `quest update`로 받는다.
4. 미션은 `quest mission`이 처음 보여 줄 때 시작한 것으로 친다(실제 시간 측정의 시작점).
5. 설명 게이트를 하나라도 틀리면 미션은 통과하지 않고, 다시 체크부터 본다.
6. Leitner 간격은 1·2·4·8·16일이고, 복습 한 번에 최대 15장이다 📐.
7. 재구성 복습은 7일마다 제안하고, 모범 답안을 본 미션부터 고른다.
8. 승급 시험은 남은 코어 미션을 장애 미션까지 면제하고(S1과 같음), 선택 미션은 면제하지 않는다. 면제된 미션은 나중에 보상 없이 다시 할 수 있다.
9. 카드 복습에는 XP가 없다. XP는 S1과 같은 계산으로 미션과 재구성 복습에서만 생긴다.
10. 미션 스키마에 `key`, `solve`, `requires_lab`, `badge`가 늘어나고, 체크와 문항은 번호를 갖는다.
11. 리뷰봇은 GitHub Actions가 아니라 게임이 로컬에서 코멘트를 단다(design.md 8.2절의 "리뷰봇 워크플로"를 바꿈). 지적 목록을 공개 리포에 올리지 않기 위해서다.
12. 랩 VM은 처음 필요할 때 확인을 받고 만들며, 장이 끝나도 지우지 않는다.
13. `quest stats --sql`은 읽기 전용 연결로만 실행한다.
14. 콘텐츠 리포의 CI는 엔진을 태그로 고정해 쓴다.

## 확인하지 못한 것
- OrbStack 머신 안에 실습용 SSH 서버를 따로 띄우고 맥에서 접속할 수 있는지(1장 SSH 미션). 내장 SSH는 이 맥에서만 접속을 받는다는 것까지 확인했다. 구현 때 확인한다.
- OrbStack 머신을 통째로 스냅샷하는 방법이 있는지. 없으면 위의 되돌리기 목록 방식으로 한다.
- GitHub 호스티드 Ubuntu 러너에서 systemd를 그대로 쓸 수 있는지(VM 미션 플레이스루).
- 맥에서 uv로 받는 Python 3.14의 SQLite 버전(ERD에서 이어짐). 엔진이 시작할 때 확인한다.
