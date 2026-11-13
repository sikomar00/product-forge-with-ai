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
from quest.core import config, incidents, state, ui
from quest.core.mission import Mission


def snapshot_folder(ref: str) -> Path:
    return config.home() / "snapshots" / ref


def _mission_of(game: Game, row: sqlite3.Row) -> Mission | None:
    """장애의 미션. 콘텐츠에서 사라졌으면 None(그래도 파일은 되돌릴 수 있어야 한다)."""
    return next((m for m in game.missions if m.key == row["mission_key"]), None)


def _restore_and_close(game: Game, row: sqlite3.Row) -> None:
    """시나리오 cleanup(프로세스 정지·VM 안 변경 되돌리기)을 먼저 하고, 스냅샷으로 파일을 되돌린 뒤
    aborted로 닫는다.

    cleanup이나 되돌리기가 하나라도 실패하면 장애를 닫지 않고 스냅샷도 남긴다. 그래야 원인을
    고친 뒤 다시 abort할 수 있다(CLAUDE.md "abort로 원상 복구할 수 있어야 한다").
    """
    folder, m = snapshot_folder(row["snapshot_ref"]), _mission_of(game, row)
    cleanup_error = None
    try:
        if m is not None and m.chaos is not None:
            m.chaos.cleanup(make_ctx(game.cfg))
    except Exception as exc:  # 시나리오 오류: 파일 되돌리기는 계속하고, 끝에 알리고 멈춘다
        cleanup_error = exc
    try:
        chaos.restore(folder)
    except OSError as exc:
        raise config.EnvError(f"되돌리지 못했습니다({exc}). 스냅샷은 {folder}에 남아 있습니다."
                              " 다른 프로그램이 파일을 쓰고 있지 않은지 보고 다시 abort") from exc
    if cleanup_error is not None:
        raise config.EnvError(
            f"파일은 되돌렸지만 시나리오 정리가 실패했습니다({type(cleanup_error).__name__})."
            " 장애는 진행 중으로 남깁니다. 랩·도구 상태를 확인하고 다시 quest incident abort"
        ) from cleanup_error
    with state.transaction(game.conn) as tx:
        incidents.close_incident(tx, row, "aborted")
    shutil.rmtree(folder, ignore_errors=True)


def offer_injection(game: Game, m: Mission) -> int:
    """장애 미션을 볼 때 부른다. 통과 전이고 진행 중인 장애가 없으면 묻고 주입한다."""
    active = incidents.incident_row(game.conn)
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
        incidents.open_incident(tx, m, ref)
    try:
        m.chaos.inject(ctx)
        injected = m.chaos.verify(ctx)
    except Exception as exc:  # 시나리오 오류: 반쯤 걸린 장애를 남기지 않고 되돌린다
        print(ui.paint(f"⚠️ 시나리오 오류: {type(exc).__name__}", "yellow"))
        injected = False
    if not injected:
        _restore_and_close(game, incidents.incident_row(game.conn))
        print(ui.paint("⚠️ 장애를 걸지 못해 원래대로 되돌렸습니다. quest report로 알려 주세요.",
                       "yellow"))
        return ENV
    print(ui.paint("🚨 장애가 시작됐습니다. 원인을 찾아 복구한 뒤 quest check", "red"))
    return OK


def _status(game: Game) -> int:
    row = incidents.incident_row(game.conn)
    if row is None:
        print("진행 중인 장애가 없습니다.")
        return OK
    m = _mission_of(game, row)
    minutes = (datetime.now(UTC) - state.parse_utc(row["injected_at"])).total_seconds() // 60
    name = f"{m.id} {m.title}" if m else f"{row['mission_key']}(콘텐츠에 없음)"
    print(f"🚨 {name} · {int(minutes)}분째")
    print(ui.paint("복구했으면 quest check, 그만두려면 quest incident abort", "dim"))
    return OK


def _abort(game: Game) -> int:
    row = incidents.incident_row(game.conn)
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
