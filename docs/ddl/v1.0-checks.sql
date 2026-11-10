-- ERD v1.0 점검. run_checks.py가 빈 메모리 DB에 v1.0.sql을 적용한 뒤 위에서부터 차례로 실행한다.
-- 형식: "-- check: 설명", "-- expect: ok | error <오류 문구 일부> | value <첫 행 첫 칸 값>", 그다음 SQL 한 문장.

-- check: 스키마 버전이 들어 있다
-- expect: value 1.0
SELECT value FROM meta WHERE key = 'schema_version';

-- check: 외래 키 검사가 켜져 있다
-- expect: value 1
PRAGMA foreign_keys;

-- check: 진행 중 미션 추가
-- expect: ok
INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at, est_min, ai_tag)
VALUES ('m_0000000a', '0-1', 0, 'in_progress', '2026-11-16T01:00:00Z', 30, 'pair');

-- check: 화면 번호를 키로 쓰면 막힌다
-- expect: error CHECK constraint failed
INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at, est_min, ai_tag)
VALUES ('5-8', '5-8', 5, 'in_progress', '2026-11-16T01:00:00Z', 30, 'pair');

-- check: 키의 16진수는 소문자만
-- expect: error CHECK constraint failed
INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at, est_min, ai_tag)
VALUES ('m_ABCDEF12', '0-3', 0, 'in_progress', '2026-11-16T01:00:00Z', 30, 'pair');

-- check: 장은 0~17
-- expect: error CHECK constraint failed
INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at, est_min, ai_tag)
VALUES ('m_0000000c', '18-1', 18, 'in_progress', '2026-11-16T01:00:00Z', 30, 'pair');

-- check: 장 칸에 글자를 넣으면 STRICT가 막는다
-- expect: error cannot store TEXT value in INTEGER column
INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at, est_min, ai_tag)
VALUES ('m_0000000c', '0-3', 'zero', 'in_progress', '2026-11-16T01:00:00Z', 30, 'pair');

-- check: 정해진 상태 값만
-- expect: error CHECK constraint failed
INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at, est_min, ai_tag)
VALUES ('m_0000000c', '0-3', 0, 'done', '2026-11-16T01:00:00Z', 30, 'pair');

-- check: 진행 중인데 완료 시각이 있으면 막힌다
-- expect: error CHECK constraint failed
INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at, completed_at, est_min, ai_tag)
VALUES ('m_0000000c', '0-3', 0, 'in_progress', '2026-11-16T01:00:00Z', '2026-11-16T02:00:00Z', 30, 'pair');

-- check: 통과인데 완료 방식이 없으면 막힌다
-- expect: error CHECK constraint failed
INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at, completed_at, est_min, ai_tag)
VALUES ('m_0000000c', '0-3', 0, 'passed', '2026-11-16T01:00:00Z', '2026-11-16T02:00:00Z', 30, 'pair');

-- check: 면제는 시험 면제(exam_skip)로만
-- expect: error CHECK constraint failed
INSERT INTO mission_progress (mission_key, display_id, chapter, status, how, completed_at, est_min, ai_tag)
VALUES ('m_0000000c', '0-3', 0, 'exempted', 'normal', '2026-11-16T02:00:00Z', 30, 'pair');

-- check: 면제가 아니면 시작 시각이 있어야 한다
-- expect: error CHECK constraint failed
INSERT INTO mission_progress (mission_key, display_id, chapter, status, est_min, ai_tag)
VALUES ('m_0000000c', '0-3', 0, 'in_progress', 30, 'pair');

-- check: 힌트는 0~3
-- expect: error CHECK constraint failed
INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at, hints_used, est_min, ai_tag)
VALUES ('m_0000000c', '0-3', 0, 'in_progress', '2026-11-16T01:00:00Z', 4, 30, 'pair');

-- check: 시각은 UTC ISO-8601 형식만
-- expect: error CHECK constraint failed
INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at, est_min, ai_tag)
VALUES ('m_0000000c', '0-3', 0, 'in_progress', '2026-11-16 01:00:00', 30, 'pair');

-- check: AI 태그는 solo·pair·delegate만
-- expect: error CHECK constraint failed
INSERT INTO mission_progress (mission_key, display_id, chapter, status, started_at, est_min, ai_tag)
VALUES ('m_0000000c', '0-3', 0, 'in_progress', '2026-11-16T01:00:00Z', 30, 'auto');

-- check: 진행 중 미션을 통과로 바꾼다(현재 상태 표는 고칠 수 있다)
-- expect: ok
UPDATE mission_progress
SET status = 'passed', how = 'normal', first_check_at = '2026-11-16T01:30:00Z', completed_at = '2026-11-16T01:40:00Z', xp_awarded = 10
WHERE mission_key = 'm_0000000a';

-- check: 시험 면제 미션은 시작 시각 없이 추가할 수 있다
-- expect: ok
INSERT INTO mission_progress (mission_key, display_id, chapter, status, how, completed_at, xp_awarded, est_min, ai_tag)
VALUES ('m_0000000b', '0-2', 0, 'exempted', 'exam_skip', '2026-11-16T01:40:00Z', 5, 20, 'solo');

-- check: 예상 대비 실제 시간(분)
-- expect: value 40
SELECT actual_min FROM v_mission_time WHERE mission_key = 'm_0000000a';

-- check: 장별 힌트 사용률은 통과한 미션만 센다(면제 제외)
-- expect: value 1
SELECT passed FROM v_hint_rate WHERE chapter = 0;

-- check: 게임 상태 한 행 추가
-- expect: ok
INSERT INTO game_state (id, mode, updated_at) VALUES (1, 'normal', '2026-11-16T01:00:00Z');

-- check: 게임 상태는 한 행뿐
-- expect: error CHECK constraint failed
INSERT INTO game_state (id, mode, updated_at) VALUES (2, 'normal', '2026-11-16T01:00:00Z');

-- check: 시험 모드인데 대상이 없으면 막힌다
-- expect: error CHECK constraint failed
UPDATE game_state SET mode = 'exam', mode_started_at = '2026-11-16T03:00:00Z' WHERE id = 1;

-- check: 없는 미션을 시험 대상으로 하면 외래 키가 막는다
-- expect: error FOREIGN KEY constraint failed
UPDATE game_state SET mode = 'exam', mode_mission_key = 'm_ffffffff', mode_started_at = '2026-11-16T03:00:00Z' WHERE id = 1;

-- check: 시험 모드로 바꾼다
-- expect: ok
UPDATE game_state SET mode = 'exam', mode_mission_key = 'm_0000000a', mode_started_at = '2026-11-16T03:00:00Z', updated_at = '2026-11-16T03:00:00Z' WHERE id = 1;

-- check: 시도 기록 추가(체크는 번호와 통과 여부만)
-- expect: ok
INSERT INTO attempts (mission_key, display_id, mode, at, outcome, check_results, engine_version, content_version)
VALUES ('m_0000000a', '0-1', 'normal', '2026-11-16T01:30:00Z', 'pass', '[{"no":1,"ok":true},{"no":2,"ok":true}]', '0.1.0', 'abc1234');

-- check: 체크 결과가 JSON이 아니면 막힌다
-- expect: error CHECK constraint failed
INSERT INTO attempts (mission_key, display_id, mode, at, outcome, check_results, engine_version, content_version)
VALUES ('m_0000000a', '0-1', 'normal', '2026-11-16T01:31:00Z', 'fail', 'ok', '0.1.0', 'abc1234');

-- check: 체크 결과는 배열이어야 한다
-- expect: error CHECK constraint failed
INSERT INTO attempts (mission_key, display_id, mode, at, outcome, check_results, engine_version, content_version)
VALUES ('m_0000000a', '0-1', 'normal', '2026-11-16T01:31:00Z', 'fail', '{"no":1}', '0.1.0', 'abc1234');

-- check: 결과는 pass·fail·error만
-- expect: error CHECK constraint failed
INSERT INTO attempts (mission_key, display_id, mode, at, outcome, check_results, engine_version, content_version)
VALUES ('m_0000000a', '0-1', 'normal', '2026-11-16T01:31:00Z', 'maybe', '[]', '0.1.0', 'abc1234');

-- check: 진행 기록이 없는 미션의 시도는 외래 키가 막는다
-- expect: error FOREIGN KEY constraint failed
INSERT INTO attempts (mission_key, display_id, mode, at, outcome, check_results, engine_version, content_version)
VALUES ('m_ffffffff', '9-9', 'normal', '2026-11-16T01:31:00Z', 'fail', '[]', '0.1.0', 'abc1234');

-- check: 시도 기록은 고칠 수 없다
-- expect: error append-only
UPDATE attempts SET outcome = 'fail' WHERE attempt_id = 1;

-- check: 시도 기록은 지울 수 없다
-- expect: error append-only
DELETE FROM attempts WHERE attempt_id = 1;

-- check: 미션 안 문항 응답(확신도 3인데 틀림)
-- expect: ok
INSERT INTO responses (attempt_id, chapter, context, item_no, correct, confidence, at)
VALUES (1, 0, 'mission', 1, 0, 3, '2026-11-16T01:30:00Z');

-- check: 지연 확인 퀴즈 응답은 시도 없이
-- expect: ok
INSERT INTO responses (chapter, context, item_no, correct, confidence, at)
VALUES (0, 'delayed_quiz', 1, 1, 2, '2026-12-04T01:00:00Z');

-- check: 지연 확인 퀴즈에 시도를 붙이면 막힌다
-- expect: error CHECK constraint failed
INSERT INTO responses (attempt_id, chapter, context, item_no, correct, at)
VALUES (1, 0, 'delayed_quiz', 2, 1, '2026-12-04T01:00:00Z');

-- check: 미션 응답에 시도가 없으면 막힌다
-- expect: error CHECK constraint failed
INSERT INTO responses (chapter, context, item_no, correct, at)
VALUES (0, 'mission', 2, 1, '2026-11-16T01:30:00Z');

-- check: 확신도는 1~3
-- expect: error CHECK constraint failed
INSERT INTO responses (attempt_id, chapter, context, item_no, correct, confidence, at)
VALUES (1, 0, 'mission', 2, 1, 4, '2026-11-16T01:30:00Z');

-- check: 응답 기록은 지울 수 없다
-- expect: error append-only
DELETE FROM responses WHERE response_id = 1;

-- check: 만기가 지난 카드 추가
-- expect: ok
INSERT INTO cards (card_key, mission_key, kind, box, added_at, due_at)
VALUES ('c_0000000a', 'm_0000000a', 'concept', 1, '2026-11-16T01:40:00Z', '2026-01-01T00:00:00Z');

-- check: 만기가 먼 카드 추가
-- expect: ok
INSERT INTO cards (card_key, mission_key, kind, box, added_at, due_at)
VALUES ('c_0000000b', 'm_0000000a', 'tool_map', 1, '2026-11-16T01:40:00Z', '2999-01-01T00:00:00Z');

-- check: 상자는 1~5
-- expect: error CHECK constraint failed
INSERT INTO cards (card_key, mission_key, kind, box, added_at, due_at)
VALUES ('c_0000000c', 'm_0000000a', 'concept', 6, '2026-11-16T01:40:00Z', '2026-11-17T00:00:00Z');

-- check: 카드 종류는 네 가지만
-- expect: error CHECK constraint failed
INSERT INTO cards (card_key, mission_key, kind, added_at, due_at)
VALUES ('c_0000000c', 'm_0000000a', 'note', '2026-11-16T01:40:00Z', '2026-11-17T00:00:00Z');

-- check: 카드 키는 c_ + 16진수 8자리
-- expect: error CHECK constraint failed
INSERT INTO cards (card_key, mission_key, kind, added_at, due_at)
VALUES ('k_0000000c', 'm_0000000a', 'concept', '2026-11-16T01:40:00Z', '2026-11-17T00:00:00Z');

-- check: 지금 만기인 카드 수(복습 잠금 판단에 쓴다)
-- expect: value 1
SELECT due FROM v_due_cards;

-- check: 복습 결과 추가(확신도 3, 맞음)
-- expect: ok
INSERT INTO reviews (card_key, at, correct, confidence, box_before, box_after)
VALUES ('c_0000000a', '2026-11-17T01:00:00Z', 1, 3, 1, 2);

-- check: 복습의 확신도도 1~3
-- expect: error CHECK constraint failed
INSERT INTO reviews (card_key, at, correct, confidence, box_before, box_after)
VALUES ('c_0000000a', '2026-11-17T01:00:00Z', 1, 0, 1, 2);

-- check: 복습 기록은 고칠 수 없다
-- expect: error append-only
UPDATE reviews SET correct = 0 WHERE review_id = 1;

-- check: 확신했는데 틀린 비율 = 확신도 3인 답 2개 중 1개
-- expect: value 0.5
SELECT rate FROM v_overconfidence;

-- check: 장 시작
-- expect: ok
INSERT INTO chapter_progress (chapter, started_at) VALUES (0, '2026-11-16T01:00:00Z');

-- check: 완료 시각만 있고 완료 방식이 없으면 막힌다
-- expect: error CHECK constraint failed
UPDATE chapter_progress SET completed_at = '2026-11-20T00:00:00Z' WHERE chapter = 0;

-- check: 보스 통과로 장 완료
-- expect: ok
UPDATE chapter_progress SET completed_at = '2026-11-20T00:00:00Z', completed_via = 'boss' WHERE chapter = 0;

-- check: 지연 확인 퀴즈 만기는 완료 14일 뒤
-- expect: value 2026-12-04T00:00:00Z
SELECT due_at FROM v_delayed_quiz_due WHERE chapter = 0;

-- check: 진행 중 장애 추가
-- expect: ok
INSERT INTO incidents (mission_key, source, status, injected_at, snapshot_ref)
VALUES ('m_0000000a', 'mission', 'active', '2026-11-16T02:00:00Z', 'snap-0001');

-- check: 진행 중인 장애는 하나뿐
-- expect: error UNIQUE constraint failed
INSERT INTO incidents (mission_key, source, status, injected_at, snapshot_ref)
VALUES ('m_0000000a', 'oncall', 'active', '2026-11-16T02:05:00Z', 'snap-0002');

-- check: 복구 상태인데 복구 시각이 없으면 막힌다
-- expect: error CHECK constraint failed
UPDATE incidents SET status = 'recovered' WHERE incident_id = 1;

-- check: 복구 처리
-- expect: ok
UPDATE incidents SET status = 'recovered', recovered_at = '2026-11-16T02:10:00Z', rca_correct = 1 WHERE incident_id = 1;

-- check: MTTR(초)
-- expect: value 600
SELECT mttr_sec FROM v_mttr WHERE incident_id = 1;

-- check: 앞 장애를 복구한 뒤에는 새 장애를 시작할 수 있다
-- expect: ok
INSERT INTO incidents (mission_key, source, status, injected_at, snapshot_ref)
VALUES ('m_0000000a', 'oncall', 'active', '2026-11-17T09:00:00Z', 'snap-0003');

-- check: 중단과 복구 시각이 함께 있으면 막힌다
-- expect: error CHECK constraint failed
INSERT INTO incidents (mission_key, source, status, injected_at, recovered_at, aborted_at, snapshot_ref)
VALUES ('m_0000000a', 'mission', 'aborted', '2026-11-16T02:00:00Z', '2026-11-16T02:10:00Z', '2026-11-16T02:20:00Z', 'snap-0004');

-- check: 이벤트 기록(값은 키·숫자만)
-- expect: ok
INSERT INTO events (at, kind, mission_key, payload) VALUES ('2026-11-16T01:40:00Z', 'mission_passed', 'm_0000000a', '{"xp":10}');

-- check: 정해진 이벤트 종류만
-- expect: error CHECK constraint failed
INSERT INTO events (at, kind) VALUES ('2026-11-16T01:41:00Z', 'mission_won');

-- check: 이벤트 값은 JSON 객체만
-- expect: error CHECK constraint failed
INSERT INTO events (at, kind, payload) VALUES ('2026-11-16T01:41:00Z', 'selftest_run', '[1]');

-- check: 이벤트는 지울 수 없다
-- expect: error append-only
DELETE FROM events WHERE event_id = 1;

-- check: 자기 진단 추가
-- expect: ok
INSERT INTO self_assessments (chapter, level, reason, assessed_at) VALUES (2, 2, '브랜치·머지·충돌은 해 봤다', '2026-11-16T05:00:00Z');

-- check: 이해도는 1~3
-- expect: error CHECK constraint failed
INSERT INTO self_assessments (chapter, level, assessed_at) VALUES (2, 4, '2026-11-16T05:00:00Z');

-- check: 자기 진단은 고칠 수 없다(다시 진단하면 새 행)
-- expect: error append-only
UPDATE self_assessments SET level = 3 WHERE assessment_id = 1;

-- check: 배지 추가
-- expect: ok
INSERT INTO badges (badge_key, earned_at) VALUES ('first_green_ci', '2026-11-20T00:00:00Z');

-- check: 배지는 지울 수 없다
-- expect: error append-only
DELETE FROM badges WHERE badge_key = 'first_green_ci';
