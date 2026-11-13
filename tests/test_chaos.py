"""장애 주입 시험(M1-05, ADR-0007, IA-13): 허용 대상, 스냅샷·abort, 복구·MTTR, 근본 원인 퀴즈."""

import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import Quest

from quest import chaos
from quest.core.mission import Chaos, Ctx


def _db(game: Path) -> sqlite3.Connection:
    return sqlite3.connect(game.parent / "home" / "state.db", isolation_level=None)


def _ctx(workdir: Path) -> Ctx:
    cfg = {"product": {"repo_path": str(workdir)}}
    return Ctx(workdir=workdir, config=cfg, lab="pf-lab", gh=None, now=datetime.now(UTC))


# ───────────── 허용 대상 ─────────────


@pytest.mark.parametrize(
    ("target", "refused"),
    [
        ("service.conf", None),
        ("sub/dir", None),
        ("lab:pf-lab", None),
        ("lab:pf-lab-2", None),
        ("lab:my-ubuntu", "pf-lab"),
        ("/etc/hosts", "시스템 경로"),
        ("/usr/local/bin/x", "시스템 경로"),
        ("../outside.txt", "허용 대상"),
    ],
)
def test_injection_targets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str,
                           refused: str | None) -> None:
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(tmp_path / "home"))
    work = tmp_path / "opsdesk"
    work.mkdir()
    reason = chaos.refusal(_ctx(work), target)
    assert (reason is None) if refused is None else (refused in reason)


def test_tech_radar_and_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(tmp_path))
    work = tmp_path / "opsdesk"
    work.mkdir()
    ctx = _ctx(work)
    assert chaos.refusal(ctx, "~/forge-sandbox/1-1-20261113/a.txt") is None
    radar = tmp_path / "opsdesk" / "tech-radar-agent" / "x"
    assert "Tech Radar" in chaos.refusal(ctx, str(radar))


def test_snapshot_restores_files_folders_and_git(tmp_path: Path) -> None:
    work = tmp_path / "opsdesk"
    (work / ".git").mkdir(parents=True)
    (work / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (work / "app.py").write_text("print(1)\n", encoding="utf-8")
    scenario = Chaos((".", "new.txt"), lambda ctx: None, lambda ctx: True, lambda ctx: None)
    folder = tmp_path / "snap"
    chaos.snapshot(_ctx(work), scenario, folder)
    (work / "app.py").write_text("broken\n", encoding="utf-8")
    (work / ".git" / "HEAD").write_text("detached\n", encoding="utf-8")
    (work / "new.txt").write_text("not here before\n", encoding="utf-8")
    chaos.restore(folder)
    assert (work / "app.py").read_text(encoding="utf-8") == "print(1)\n"
    assert (work / ".git" / "HEAD").read_text(encoding="utf-8") == "ref: refs/heads/main\n"
    assert not (work / "new.txt").exists()  # 없던 파일은 지운다


# ───────────── 명령: 주입 → 상태 → 중단·복구 ─────────────


def _incidents(game: Path) -> list[tuple]:
    return _db(game).execute(
        "SELECT status, recovered_at IS NOT NULL, aborted_at IS NOT NULL, rca_correct"
        " FROM incidents ORDER BY incident_id").fetchall()


def test_inject_then_abort_restores(game: Path, quest: Quest, answers: list[str]) -> None:
    (game / "service.conf").write_text("mode=ok\n", encoding="utf-8")
    answers.append("y")
    code, out = quest("mission", "1-2")
    assert code == 0 and "대상: service.conf" in out and "장애가 시작됐습니다" in out
    assert (game / "service.conf").read_text(encoding="utf-8") == "mode=broken\n"
    assert "🚨 진행 중인 장애" in quest()[1]
    assert "1-2 가짜 장애 · 0분째" in quest("incident", "status")[1]
    code, out = quest("reset")
    assert code == 2 and "incident abort" in out  # 진행 중인 장애가 있으면 초기화하지 않는다
    code, out = quest("incident", "abort")
    assert code == 0 and "되돌렸습니다" in out
    assert (game / "service.conf").read_text(encoding="utf-8") == "mode=ok\n"
    assert _incidents(game) == [("aborted", 0, 1, None)]
    assert not list((game.parent / "home" / "snapshots").iterdir())  # 스냅샷은 지운다


def test_recover_with_rca_records_mttr(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.append("y")
    quest("mission", "1-2")
    (game / "service.conf").write_text("mode=ok\n", encoding="utf-8")
    answers.append("1")  # 근본 원인 퀴즈를 틀린다
    code, out = quest("check", "1-2")
    assert code == 1 and "장애를 복구했습니다" in out and "아직 통과가 아닙니다" in out
    assert _incidents(game) == [("recovered", 1, 0, 0)]
    answers.append("2")
    code, out = quest("check", "1-2")  # 복구는 끝났고 근본 원인 퀴즈만 다시 본다
    assert code == 0 and "+20 XP" in out and "원샷" not in out  # 퀴즈 실패 1회라 보너스 없음
    assert _incidents(game) == [("recovered", 1, 0, 1)]
    mttr = _db(game).execute("SELECT count(*) FROM v_mttr").fetchone()
    assert mttr == (1,)
    kinds = [k for (k,) in _db(game).execute("SELECT kind FROM events WHERE kind LIKE 'incident%'")]
    assert kinds == ["incident_injected", "incident_recovered"]


def test_check_before_injection_is_refused(game: Path, quest: Quest) -> None:
    code, out = quest("check", "1-2")
    assert code == 2 and "quest mission으로 장애를 시작" in out


def test_declining_injection_changes_nothing(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.append("n")
    code, out = quest("mission", "1-2")
    assert code == 0 and "주입하지 않았습니다" in out
    assert _incidents(game) == [] and not (game / "service.conf").exists()


def test_refused_target_is_not_injected(
    game: Path, quest: Quest, answers: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(chaos, "refusal", lambda ctx, target: "시스템 경로는 건드리지 않음: /etc")
    code, out = quest("mission", "1-2")
    assert code == 2 and "주입하지 않습니다: 시스템 경로" in out and _incidents(game) == []


def test_failed_injection_is_rolled_back(
    game: Path, quest: Quest, answers: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (game / "service.conf").write_text("mode=ok\n", encoding="utf-8")
    from quest.commands import incident

    real = incident.offer_injection

    def broken_verify(g: object, m: object) -> int:
        object.__setattr__(m.chaos, "verify", lambda ctx: False)  # 장애가 걸리지 않은 척
        return real(g, m)

    monkeypatch.setattr("quest.commands.play.offer_injection", broken_verify)
    answers.append("y")
    code, out = quest("mission", "1-2")
    assert code == 3 and "원래대로 되돌렸습니다" in out
    assert (game / "service.conf").read_text(encoding="utf-8") == "mode=ok\n"
    assert _incidents(game) == [("aborted", 0, 1, None)]


def test_no_exam_during_incident(game: Path, quest: Quest, answers: list[str]) -> None:
    answers.append("y")
    quest("mission", "1-2")
    _db(game).executemany(
        "INSERT OR IGNORE INTO mission_progress (mission_key, display_id, chapter, status, how,"
        " started_at, completed_at, est_min, ai_tag) VALUES (?, '0-x', 0, 'passed', 'normal',"
        " '2026-01-01T00:00:00Z', '2026-01-01T00:10:00Z', 5, 'solo')",
        [(f"m_f000000{n}",) for n in range(1, 6)],
    )
    code, out = quest("exam")
    assert code == 2 and "진행 중인 장애" in out


def test_restore_handles_read_only_git_objects(tmp_path: Path) -> None:
    """Windows에서 git은 .git/objects를 읽기 전용으로 둔다. 그래도 되돌릴 수 있어야 한다."""
    import stat

    work = tmp_path / "opsdesk"
    objects = work / ".git" / "objects"
    objects.mkdir(parents=True)
    blob = objects / "ab12"
    blob.write_text("blob", encoding="utf-8")
    blob.chmod(stat.S_IREAD)
    scenario = Chaos((".",), lambda ctx: None, lambda ctx: True, lambda ctx: None)
    chaos.snapshot(_ctx(work), scenario, tmp_path / "snap")
    (work / "added.txt").write_text("x", encoding="utf-8")
    chaos.restore(tmp_path / "snap")
    assert not (work / "added.txt").exists() and blob.read_text(encoding="utf-8") == "blob"


def test_broken_snapshot_keeps_current_files(tmp_path: Path) -> None:
    work = tmp_path / "opsdesk"
    work.mkdir()
    (work / "app.py").write_text("now", encoding="utf-8")
    scenario = Chaos((".",), lambda ctx: None, lambda ctx: True, lambda ctx: None)
    chaos.snapshot(_ctx(work), scenario, tmp_path / "snap")
    (tmp_path / "snap" / "0.tar").write_bytes(b"not a tar file")
    with pytest.raises(Exception):  # noqa: B017 - tarfile이 내는 오류 종류는 상관없다
        chaos.restore(tmp_path / "snap")
    assert (work / "app.py").read_text(encoding="utf-8") == "now"  # 지우고 실패하지 않는다


def test_abort_still_restores_when_mission_left_content(
    game: Path, quest: Quest, answers: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (game / "service.conf").write_text("mode=ok\n", encoding="utf-8")
    answers.append("y")
    quest("mission", "1-2")
    from quest.commands import common

    real_open = common.open_game

    def without_incident_mission() -> object:
        loaded = real_open()
        missions = tuple(m for m in loaded.missions if m.id != "1-2")
        return common.Game(loaded.conn, missions, loaded.cfg, loaded.quizzes, loaded.goals)

    monkeypatch.setattr("quest.cli.open_game", without_incident_mission)
    assert "콘텐츠에 없음" in quest("incident", "status")[1]
    code, out = quest("incident", "abort")
    assert code == 0 and (game / "service.conf").read_text(encoding="utf-8") == "mode=ok\n"
    assert _incidents(game) == [("aborted", 0, 1, None)]


def test_restore_when_scenario_deleted_parent_folder(tmp_path: Path) -> None:
    work = tmp_path / "opsdesk"
    (work / "config").mkdir(parents=True)
    (work / "config" / "app.toml").write_text("port = 80\n", encoding="utf-8")
    scenario = Chaos(("config/app.toml",), lambda ctx: None, lambda ctx: True, lambda ctx: None)
    chaos.snapshot(_ctx(work), scenario, tmp_path / "snap")
    import shutil

    shutil.rmtree(work / "config")  # 시나리오가 rm -rf config
    chaos.restore(tmp_path / "snap")
    assert (work / "config" / "app.toml").read_text(encoding="utf-8") == "port = 80\n"


@pytest.mark.skipif(sys.platform == "win32", reason="chmod 000·심볼릭 링크는 POSIX에서 본다")
def test_restore_unlocks_000_folder_and_leaves_link_targets_alone(tmp_path: Path) -> None:
    import os

    work = tmp_path / "opsdesk"
    work.mkdir()
    (work / "app.py").write_text("ok", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("mine", encoding="utf-8")
    os.chmod(outside, 0o644)
    scenario = Chaos((".",), lambda ctx: None, lambda ctx: True, lambda ctx: None)
    chaos.snapshot(_ctx(work), scenario, tmp_path / "snap")
    locked = work / "locked"
    locked.mkdir()
    (locked / "x").write_text("x", encoding="utf-8")
    os.chmod(locked, 0)  # 권한 장애
    (work / "link").symlink_to(outside)
    chaos.restore(tmp_path / "snap")
    assert not locked.exists() and not (work / "link").exists()
    assert oct(outside.stat().st_mode & 0o777) == oct(0o644)  # 링크가 가리킨 파일은 그대로


def test_failed_cleanup_keeps_incident_open(
    game: Path, quest: Quest, answers: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (game / "service.conf").write_text("mode=ok\n", encoding="utf-8")
    answers.append("y")
    quest("mission", "1-2")
    from quest.commands import incident

    real = incident._mission_of

    def failing_cleanup(g: object, row: object) -> object:
        m = real(g, row)

        def boom(ctx: object) -> None:
            raise TimeoutError("orb")

        object.__setattr__(m.chaos, "cleanup", boom)
        return m

    monkeypatch.setattr(incident, "_mission_of", failing_cleanup)
    code, out = quest("incident", "abort")
    assert code == 3 and "장애는 진행 중으로 남깁니다" in out
    assert (game / "service.conf").read_text(encoding="utf-8") == "mode=ok\n"  # 파일은 되돌렸다
    assert _incidents(game) == [("active", 0, 0, None)]
    assert list((game.parent / "home" / "snapshots").iterdir())  # 다시 abort할 스냅샷이 남는다
    monkeypatch.setattr(incident, "_mission_of", real)  # 원인을 고친 뒤 다시 abort
    code, out = quest("incident", "abort")
    assert code == 0, out
