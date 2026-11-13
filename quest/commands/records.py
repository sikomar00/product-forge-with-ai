"""IA-6 장 지도, IA-11 기록(M0-06, M0-15, Spec "텔레메트리와 quest stats")."""

import sqlite3

from quest.commands.common import OK, USAGE, Game, line
from quest.core import goals, progress, state, ui

STATUS_LABELS = {None: "안 함", "in_progress": "진행 중", "passed": "✅ 통과", "exempted": "면제"}
RANK_BANDS = {0: "견습", 5: "주니어", 9: "미들", 14: "시니어 후보"}  # 등급이 시작되는 장


def _current_chapter(game: Game) -> int:
    m = progress.current(game.missions, progress.statuses(game.conn))
    return m.ch if m else game.missions[-1].ch


# ───────────── IA-6 장 지도 ─────────────


def _chapter_list(game: Game, current: int) -> None:
    status = progress.statuses(game.conn)
    for ch, name in enumerate(progress.CHAPTERS):
        if ch in RANK_BANDS:
            print(ui.paint(f"── {RANK_BANDS[ch]}", "dim"))
        if ch > current:
            print(f"   🔒 {ch:>2}장 {name}")  # 잠긴 장은 이름만(Spec "진행 규칙")
            continue
        done, total = progress.chapter_counts(game.missions, status, ch)
        mark = "▶" if ch == current else " "
        progress_bar = ui.bar(done, total, width=10) if total else "—"
        print(f" {mark} {ch:>2}장 {ui.pad(name, 18)} {progress_bar}")


def _mission_list(game: Game, ch: int) -> None:
    status = progress.statuses(game.conn)
    print(ui.paint(f"{ch}장 {progress.CHAPTERS[ch]}", "bold"))
    for m in (m for m in game.missions if m.ch == ch):
        track = "코어" if m.track == "core" else "➕선택"
        print(f"  {line(m)} · {track} · {STATUS_LABELS[status.get(m.key)]}")


def cmd_map(game: Game, rest: list[str]) -> int:
    current = _current_chapter(game)
    if not rest:
        _chapter_list(game, current)
        print(ui.paint("장 하나를 보려면 quest map <장 번호>", "dim"))
        return OK
    if not rest[0].isdecimal() or not 0 <= int(rest[0]) <= 17:
        print("장 번호는 0~17입니다.")
        return USAGE
    if int(rest[0]) > current:
        print(f"🔒 {rest[0]}장 {progress.CHAPTERS[int(rest[0])]}은 아직 잠긴 장입니다.")
        return USAGE
    _mission_list(game, int(rest[0]))
    return OK


# ───────────── IA-11 기록 ─────────────


def _chapter_stats(game: Game) -> None:
    conn = game.conn
    times = {r["chapter"]: r for r in conn.execute(
        "SELECT chapter, sum(est_min) AS est, sum(actual_min) AS actual, count(*) AS n"
        " FROM v_mission_time GROUP BY chapter")}
    hints = {r["chapter"]: r["rate"] for r in conn.execute("SELECT * FROM v_hint_rate")}
    status = progress.statuses(conn)
    print(ui.paint("장   진행        예상 → 실제(분)   힌트 사용률", "bold"))
    for ch in range(_current_chapter(game) + 1):
        done, total = progress.chapter_counts(game.missions, status, ch)
        t = times.get(ch)
        spent = f"{t['est']:>4} → {t['actual']:<4}" if t else "   —      "
        rate = f"{hints[ch]:.0%}" if ch in hints else "—"
        print(f"{ch:>2}장  {done:>2}/{total:<2}       {spent}       {rate}")


def _overall_stats(conn: sqlite3.Connection) -> None:
    over = conn.execute("SELECT confident, wrong, rate FROM v_overconfidence").fetchone()
    if over["confident"]:
        print(f"확신(3)했는데 틀린 비율: {over['rate']:.0%} ({over['wrong']}/{over['confident']})")
    else:
        print("확신(3)했는데 틀린 비율: — (확신도 3 응답 없음)")
    mttr = conn.execute("SELECT avg(mttr_sec), count(*) FROM v_mttr").fetchone()
    print(f"평균 복구 시간(MTTR): {round(mttr[0])}초 ({mttr[1]}건)" if mttr[1] else
          "평균 복구 시간(MTTR): — (복구한 장애 없음)")


def readonly_connect() -> sqlite3.Connection:
    """상태 DB 읽기 전용 연결(Spec 결정 13).

    mode=ro는 상태 DB만 막는다. query_only는 다른 DB 파일에도 쓰지 못하게 하고,
    ATTACH는 빈 파일을 새로 만들 수 있어서 권한 검사로 아예 막는다.
    """
    conn = sqlite3.connect(f"{state.db_path().as_uri()}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    conn.set_authorizer(_deny_attach)
    return conn


def _deny_attach(action: int, *_: object) -> int:
    return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_ATTACH else sqlite3.SQLITE_OK


def _run_sql(sql: str) -> int:
    """학습자의 SQL을 읽기 전용 연결로 실행한다. 한 번에 한 문장만 실행된다(sqlite3 규칙)."""
    conn = readonly_connect()
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
    except sqlite3.Error as exc:
        print(f"❌ SQL 오류: {exc}")
        return USAGE
    finally:
        conn.close()
    if cursor.description:
        print(" | ".join(col[0] for col in cursor.description))
    for row in rows:
        print(" | ".join("NULL" if v is None else str(v) for v in row))
    print(ui.paint(f"({len(rows)}행)", "dim"))
    return OK


def cmd_stats(game: Game, rest: list[str]) -> int:
    if rest:
        if len(rest) != 2 or rest[0] != "--sql":
            print('사용법: quest stats 또는 quest stats --sql "SELECT …"')
            return USAGE
        return _run_sql(rest[1])
    _chapter_stats(game)
    print()
    _overall_stats(game.conn)
    print(ui.paint('직접 조회: quest stats --sql "SELECT * FROM v_mission_time"', "dim"))
    return OK


# ───────────── IA-10 졸업 기준 ─────────────


def cmd_goals(game: Game, rest: list[str]) -> int:
    status = progress.statuses(game.conn)
    by_key = {m.key: m for m in game.missions}
    met = 0
    for area, name in goals.AREAS.items():
        keys = game.goals.get(area)
        if not keys:
            print(f"⬜ {ui.pad(name, 12)} — 콘텐츠 준비 전")
            continue
        passed, exempted = goals.area_status(keys, status)
        met += passed == len(keys)
        pending = sum(k not in by_key for k in keys)  # 목록에는 있지만 아직 안 만든 미션
        note = f" (아직 만들지 않은 미션 {pending}개)" if pending else ""
        mark = "✅" if passed == len(keys) else "⬜"
        print(f"{mark} {ui.pad(name, 12)} {passed}/{len(keys)}{note}")
        for key in exempted:
            m_id = by_key[key].id if key in by_key else key
            print(f"     ↳ {m_id}은 면제됨. quest mission {m_id}로 직접 하면 충족")
    print(ui.paint(f"\n졸업 기준 {met}/{len(goals.AREAS)} 충족", "bold"))
    return OK
