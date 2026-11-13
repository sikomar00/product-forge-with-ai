"""IA-13 장애: 주입(장애 미션을 볼 때), 상태, 중단(M1-05, ADR-0007, Spec "장애 주입").

순서: 허용 대상 확인 → 스냅샷 → incidents에 active 행 → inject → verify.
2026-11-13 결정: 주입은 장애 미션을 quest mission으로 볼 때 대상을 보여 주고 확인을 받은 뒤 한다.
중단한 뒤 다시 quest mission을 치면 다시 묻는다.
"""

import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from quest import chaos
from quest.commands.ask import confirm
from quest.commands.common import ENV, OK, USAGE, Game, make_ctx
from quest.core import config, progress, state, ui
from quest.core.mission import Mission


def snapshot_folder(ref: str) -> Path:
    return config.home() / "snapshots" / ref


def _mission_of(game: Game, row: sqlite3.Row) -> Mission:
    return next(m for m in game.missions if m.key == row["mission_key"])


def _restore_and_close(game: Game, row: sqlite3.Row) -> None:
    """스냅샷으로 되돌리고 시나리오 cleanup 뒤 aborted로 닫는다(중단·주입 실패 공통)."""
    folder = snapshot_folder(row["snapshot_ref"])
    chaos.restore(folder)
    _mission_of(game, row).chaos.cleanup(make_ctx(game.cfg))
    with state.transaction(game.conn) as tx:
        progress.close_incident(tx, row, "aborted")
    shutil.rmtree(folder, ignore_errors=True)


def offer_injection(game: Game, m: Mission) -> int:
    """장애 미션을 볼 때 부른다. 통과 전이고 진행 중인 장애가 없으면 묻고 주입한다."""
    active = progress.incident_row(game.conn)
    if active is not None:
        same = active["mission_key"] == m.key
        print("🚨 이 장애가 진행 중입니다. 복구한 뒤 quest check" if same else
              "다른 장애가 진행 중입니다. 먼저 복구하거나 quest incident abort")
        return OK
    ctx = make_ctx(game.cfg)
    if reasons := chaos.refusals(ctx, m.chaos):
        for reason in reasons:
            print(ui.paint(f"❌ 주입하지 않습니다: {reason}", "red"))
        return USAGE
    print(f"\n🚨 장애를 주입합니다. 대상: {', '.join(m.chaos.targets)}")
    if not confirm("시작할까요? 언제든 quest incident abort로 원래대로 되돌릴 수 있습니다"):
        print("주입하지 않았습니다. 준비되면 다시 quest mission")
        return OK
    ref = f"{m.id}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    chaos.snapshot(ctx, m.chaos, snapshot_folder(ref))
    with state.transaction(game.conn) as tx:
        progress.open_incident(tx, m, ref)
    try:
        m.chaos.inject(ctx)
        injected = m.chaos.verify(ctx)
    except Exception:  # 시나리오 오류: 반쯤 걸린 장애를 남기지 않고 되돌린다
        injected = False
    if not injected:
        _restore_and_close(game, progress.incident_row(game.conn))
        print(ui.paint("⚠️ 장애를 걸지 못해 원래대로 되돌렸습니다. quest report로 알려 주세요.",
                       "yellow"))
        return ENV
    print(ui.paint("🚨 장애가 시작됐습니다. 원인을 찾아 복구한 뒤 quest check", "red"))
    return OK


def _status(game: Game) -> int:
    row = progress.incident_row(game.conn)
    if row is None:
        print("진행 중인 장애가 없습니다.")
        return OK
    m = _mission_of(game, row)
    minutes = (datetime.now(UTC) - state.parse_utc(row["injected_at"])).total_seconds() // 60
    print(f"🚨 {m.id} {m.title} · {int(minutes)}분째")
    print(ui.paint("복구했으면 quest check, 그만두려면 quest incident abort", "dim"))
    return OK


def _abort(game: Game) -> int:
    row = progress.incident_row(game.conn)
    if row is None:
        print("진행 중인 장애가 없습니다.")
        return OK
    _restore_and_close(game, row)
    print("장애를 중단하고 주입 전 상태로 되돌렸습니다. 다시 하려면 quest mission")
    return OK


def cmd_incident(game: Game, rest: list[str]) -> int:
    actions = {"status": _status, "abort": _abort}
    if len(rest) != 1 or rest[0] not in actions:
        print("사용법: quest incident status | quest incident abort")
        return USAGE
    return actions[rest[0]](game)
