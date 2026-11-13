-- Product Forge With AI · 학습 상태 DDL v1.0 (docs/ERD.md)
-- 대상: SQLite 3.37 이상(STRICT 표). 연결마다 PRAGMA foreign_keys = ON 을 켠다(SQLite 기본값은 꺼짐).
-- 규칙:
--   * 시각은 UTC ISO-8601 텍스트 'YYYY-MM-DDTHH:MM:SSZ'.
--   * 콘텐츠 텍스트(요청문·힌트·체크 설명·정답)는 저장하지 않는다. 키·번호·숫자·시각만 저장한다.
--   * 미션은 바뀌지 않는 미션 키(m_ + 16진수 8자리)로 가리킨다. 화면 번호(예: 5-8)는 기록 당시 사본일 뿐 키가 아니다.
--   * 추가 전용 표(attempts, responses, reviews, events, self_assessments, badges)는 수정·삭제를 트리거로 막는다.

PRAGMA foreign_keys = ON;

-- ───────────── 현재 상태 표 ─────────────

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,                    -- schema_version, created_at, engine_version, content_version
  value TEXT NOT NULL
) STRICT;

CREATE TABLE mission_progress (
  mission_key    TEXT PRIMARY KEY
                 CHECK (length(mission_key) = 10 AND mission_key GLOB 'm_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
  display_id     TEXT NOT NULL,              -- 기록 당시 화면 번호. 키가 아니다
  chapter        INTEGER NOT NULL CHECK (chapter BETWEEN 0 AND 17),
  status         TEXT NOT NULL CHECK (status IN ('in_progress', 'passed', 'exempted')),
  how            TEXT CHECK (how IN ('normal', 'solution', 'exam', 'exam_skip')),
  started_at     TEXT CHECK (started_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  first_check_at TEXT CHECK (first_check_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  completed_at   TEXT CHECK (completed_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  fails          INTEGER NOT NULL DEFAULT 0 CHECK (fails >= 0),
  hints_used     INTEGER NOT NULL DEFAULT 0 CHECK (hints_used BETWEEN 0 AND 3),
  solution_seen  INTEGER NOT NULL DEFAULT 0 CHECK (solution_seen IN (0, 1)),
  xp_awarded     INTEGER NOT NULL DEFAULT 0 CHECK (xp_awarded >= 0),
  est_min        INTEGER NOT NULL CHECK (est_min > 0),        -- 시작할 때 콘텐츠의 예상 시간(분) 사본
  ai_tag         TEXT NOT NULL CHECK (ai_tag IN ('solo', 'pair', 'delegate')),
  CHECK ((status = 'in_progress') = (completed_at IS NULL)),
  CHECK ((status = 'in_progress') = (how IS NULL)),
  CHECK (status <> 'passed' OR how IN ('normal', 'solution', 'exam')),
  CHECK (status <> 'exempted' OR how = 'exam_skip'),
  CHECK (status = 'exempted' OR started_at IS NOT NULL)
) STRICT;

CREATE TABLE game_state (                     -- 시험·복습 모드와 그 대상만 저장한다. 현재 미션은 계산한다
  id               INTEGER PRIMARY KEY CHECK (id = 1),
  mode             TEXT NOT NULL DEFAULT 'normal' CHECK (mode IN ('normal', 'exam', 'review')),
  mode_mission_key TEXT REFERENCES mission_progress (mission_key),
  mode_started_at  TEXT CHECK (mode_started_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  updated_at       TEXT NOT NULL CHECK (updated_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  CHECK ((mode = 'normal') = (mode_mission_key IS NULL)),
  CHECK ((mode = 'normal') = (mode_started_at IS NULL))
) STRICT;

CREATE TABLE cards (
  card_key         TEXT PRIMARY KEY
                   CHECK (length(card_key) = 10 AND card_key GLOB 'c_[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
  mission_key      TEXT NOT NULL REFERENCES mission_progress (mission_key),
  kind             TEXT NOT NULL CHECK (kind IN ('concept', 'usage', 'domain', 'tool_map')),
  box              INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),
  added_at         TEXT NOT NULL CHECK (added_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  due_at           TEXT NOT NULL CHECK (due_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  last_reviewed_at TEXT CHECK (last_reviewed_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z')
) STRICT;
CREATE INDEX cards_due ON cards (due_at);

CREATE TABLE chapter_progress (
  chapter              INTEGER PRIMARY KEY CHECK (chapter BETWEEN 0 AND 17),
  started_at           TEXT NOT NULL CHECK (started_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  completed_at         TEXT CHECK (completed_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  completed_via        TEXT CHECK (completed_via IN ('boss', 'exam')),
  delayed_quiz_done_at TEXT CHECK (delayed_quiz_done_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  CHECK ((completed_at IS NULL) = (completed_via IS NULL)),
  CHECK (delayed_quiz_done_at IS NULL OR completed_at IS NOT NULL)
) STRICT;

CREATE TABLE incidents (                      -- 장애 주입 하나. M1부터 쓴다
  incident_id  INTEGER PRIMARY KEY,
  mission_key  TEXT NOT NULL REFERENCES mission_progress (mission_key),
  source       TEXT NOT NULL CHECK (source IN ('mission', 'oncall')),
  status       TEXT NOT NULL CHECK (status IN ('active', 'recovered', 'aborted')),
  injected_at  TEXT NOT NULL CHECK (injected_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  recovered_at TEXT CHECK (recovered_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  aborted_at   TEXT CHECK (aborted_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  snapshot_ref TEXT NOT NULL,                -- 스냅샷 위치(경로나 ID). 콘텐츠 텍스트가 아니다
  rca_correct  INTEGER CHECK (rca_correct IN (0, 1)),
  CHECK ((status = 'active'    AND recovered_at IS NULL     AND aborted_at IS NULL) OR
         (status = 'recovered' AND recovered_at IS NOT NULL AND aborted_at IS NULL) OR
         (status = 'aborted'   AND aborted_at IS NOT NULL   AND recovered_at IS NULL))
) STRICT;
CREATE UNIQUE INDEX incidents_one_active ON incidents (status) WHERE status = 'active';

-- ───────────── 추가 전용 표 ─────────────

CREATE TABLE attempts (                       -- quest check 한 번
  attempt_id      INTEGER PRIMARY KEY,
  mission_key     TEXT NOT NULL REFERENCES mission_progress (mission_key),
  display_id      TEXT NOT NULL,
  mode            TEXT NOT NULL CHECK (mode IN ('normal', 'exam', 'review')),
  at              TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  outcome         TEXT NOT NULL CHECK (outcome IN ('pass', 'fail', 'error')),   -- error는 실패 수에 세지 않는다
  check_results   TEXT NOT NULL CHECK (json_valid(check_results) AND json_type(check_results) = 'array'),  -- [{"no":1,"ok":true}, …] 번호와 통과 여부만
  engine_version  TEXT NOT NULL,
  content_version TEXT NOT NULL
) STRICT;
CREATE INDEX attempts_mission ON attempts (mission_key, at);

CREATE TABLE responses (                      -- 퀴즈·예측·결정·설명 게이트·지연 확인 퀴즈 문항 하나의 정오
  response_id INTEGER PRIMARY KEY,
  attempt_id  INTEGER REFERENCES attempts (attempt_id),
  chapter     INTEGER NOT NULL CHECK (chapter BETWEEN 0 AND 17),
  context     TEXT NOT NULL CHECK (context IN ('mission', 'explain_gate', 'delayed_quiz')),
  item_no     INTEGER NOT NULL CHECK (item_no >= 1),   -- 문항 번호. 내용이 아니다
  correct     INTEGER NOT NULL CHECK (correct IN (0, 1)),
  confidence  INTEGER CHECK (confidence BETWEEN 1 AND 3),
  at          TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  CHECK ((context = 'delayed_quiz') = (attempt_id IS NULL))
) STRICT;

CREATE TABLE reviews (                        -- 카드 복습 한 번
  review_id  INTEGER PRIMARY KEY,
  card_key   TEXT NOT NULL REFERENCES cards (card_key),
  at         TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  correct    INTEGER NOT NULL CHECK (correct IN (0, 1)),
  confidence INTEGER CHECK (confidence BETWEEN 1 AND 3),
  box_before INTEGER NOT NULL CHECK (box_before BETWEEN 1 AND 5),
  box_after  INTEGER NOT NULL CHECK (box_after BETWEEN 1 AND 5)
) STRICT;
CREATE INDEX reviews_at ON reviews (at);

CREATE TABLE events (                         -- 텔레메트리 사건 하나
  event_id    INTEGER PRIMARY KEY,
  at          TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
  kind        TEXT NOT NULL CHECK (kind IN (
                'mission_started', 'first_check', 'hint_opened', 'solution_viewed',
                'mission_passed', 'mission_exempted',
                'exam_started', 'exam_passed', 'exam_left',
                'review_started', 'review_finished', 'rebuild_started', 'rebuild_passed', 'rebuild_left',
                'review_lock_on', 'review_lock_off',
                'incident_injected', 'incident_recovered', 'incident_aborted',
                'content_updated', 'selftest_run', 'reset_backup')),
  mission_key TEXT REFERENCES mission_progress (mission_key),
  payload     TEXT CHECK (payload IS NULL OR (json_valid(payload) AND json_type(payload) = 'object'))  -- 키·숫자만
) STRICT;
CREATE INDEX events_kind_at ON events (kind, at);

CREATE TABLE self_assessments (               -- 0-9 진단의 장별 이해도. 다시 진단하면 새 행
  assessment_id INTEGER PRIMARY KEY,
  chapter       INTEGER NOT NULL CHECK (chapter BETWEEN 0 AND 17),
  level         INTEGER NOT NULL CHECK (level BETWEEN 1 AND 3),
  reason        TEXT,                         -- 학습자가 직접 쓴 근거
  assessed_at   TEXT NOT NULL CHECK (assessed_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z')
) STRICT;

CREATE TABLE badges (
  badge_key TEXT PRIMARY KEY,
  earned_at TEXT NOT NULL CHECK (earned_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z')
) STRICT;

CREATE TRIGGER attempts_no_update BEFORE UPDATE ON attempts BEGIN SELECT RAISE(ABORT, 'attempts is append-only'); END;
CREATE TRIGGER attempts_no_delete BEFORE DELETE ON attempts BEGIN SELECT RAISE(ABORT, 'attempts is append-only'); END;
CREATE TRIGGER responses_no_update BEFORE UPDATE ON responses BEGIN SELECT RAISE(ABORT, 'responses is append-only'); END;
CREATE TRIGGER responses_no_delete BEFORE DELETE ON responses BEGIN SELECT RAISE(ABORT, 'responses is append-only'); END;
CREATE TRIGGER reviews_no_update BEFORE UPDATE ON reviews BEGIN SELECT RAISE(ABORT, 'reviews is append-only'); END;
CREATE TRIGGER reviews_no_delete BEFORE DELETE ON reviews BEGIN SELECT RAISE(ABORT, 'reviews is append-only'); END;
CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
CREATE TRIGGER self_assessments_no_update BEFORE UPDATE ON self_assessments BEGIN SELECT RAISE(ABORT, 'self_assessments is append-only'); END;
CREATE TRIGGER self_assessments_no_delete BEFORE DELETE ON self_assessments BEGIN SELECT RAISE(ABORT, 'self_assessments is append-only'); END;
CREATE TRIGGER badges_no_update BEFORE UPDATE ON badges BEGIN SELECT RAISE(ABORT, 'badges is append-only'); END;
CREATE TRIGGER badges_no_delete BEFORE DELETE ON badges BEGIN SELECT RAISE(ABORT, 'badges is append-only'); END;

-- ───────────── 조회용 뷰 (quest stats, 복습 잠금, PRD 지표) ─────────────

CREATE VIEW v_mission_time AS               -- 미션별 예상 대비 실제 시간(분)
SELECT mission_key, display_id, chapter, est_min,
       CAST(ROUND((julianday(completed_at) - julianday(started_at)) * 1440) AS INTEGER) AS actual_min,
       fails, hints_used, solution_seen, ai_tag
FROM mission_progress
WHERE status = 'passed';

CREATE VIEW v_hint_rate AS                  -- 장별 힌트 사용률
SELECT chapter, COUNT(*) AS passed, SUM(hints_used > 0) AS used_hint,
       ROUND(1.0 * SUM(hints_used > 0) / COUNT(*), 3) AS rate
FROM mission_progress
WHERE status = 'passed'
GROUP BY chapter;

CREATE VIEW v_overconfidence AS             -- 확신도 3으로 답했는데 틀린 비율
SELECT COUNT(*) AS confident, SUM(correct = 0) AS wrong,
       ROUND(1.0 * SUM(correct = 0) / COUNT(*), 3) AS rate
FROM (SELECT correct FROM responses WHERE confidence = 3
      UNION ALL
      SELECT correct FROM reviews WHERE confidence = 3);

CREATE VIEW v_mttr AS                       -- 복구한 장애의 MTTR(초)
SELECT incident_id, mission_key, source,
       CAST(ROUND((julianday(recovered_at) - julianday(injected_at)) * 86400) AS INTEGER) AS mttr_sec
FROM incidents
WHERE status = 'recovered';

CREATE VIEW v_due_cards AS                  -- 지금 만기인 카드 수. 복습 잠금 기준값은 설정 파일에 있다
SELECT COUNT(*) AS due
FROM cards
WHERE due_at <= strftime('%Y-%m-%dT%H:%M:%SZ', 'now');

CREATE VIEW v_delayed_quiz_due AS           -- 장 완료 14일 뒤가 지연 확인 퀴즈 만기
SELECT chapter, strftime('%Y-%m-%dT%H:%M:%SZ', julianday(completed_at) + 14) AS due_at
FROM chapter_progress
WHERE completed_at IS NOT NULL AND delayed_quiz_done_at IS NULL;

INSERT INTO meta (key, value) VALUES ('schema_version', '1.0');
