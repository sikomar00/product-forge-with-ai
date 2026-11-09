---
status: proposed
---
# 학습 상태는 JSON 파일 대신 SQLite에 저장한다

S1은 학습 상태 전체를 `save.json` 파일 하나로 읽고 쓴다(`quest/engine.py`, 2026-11-09 확인). Product Forge는 시도마다 체크 결과를 남기고, 장애 주입·복구 시각과 MTTR, 복습 카드 만기, 이벤트를 쌓는다(design.md 8.6절). 또 장마다 예상 시간과 실제 시간, 힌트 사용률을 집계해 다음 장을 조정한다(9절). 집계에는 질의가 필요하므로, 상태는 표준 라이브러리 `sqlite3`로 SQLite 파일 하나에 저장한다.

## Considered Options
- JSON 파일 유지: 단순하지만, 기록이 쌓일수록 파일 전체를 다시 써야 하고 집계는 코드로 직접 짜야 한다.
- 서버형 DB(PostgreSQL): 집계는 쉽지만, 게임 하나를 돌리려고 DB 서버를 띄워야 한다.

## Consequences
- 테이블은 `missions`, `attempts`, `incidents`, `cards`, `events`로 시작하고 ERD 단계에서 확정한다.
- 시도 기록을 지우지 않고 쌓을지(추가 전용)는 ERD에서 정한다.
- 상태 파일 위치와 백업 방법은 Spec에서 정한다. 설정 파일은 `~/.config/quest/config.toml`이다(design.md 8.1절).
- S1의 `save.json`은 옮기지 않는다. 다른 게임의 기록이다.
