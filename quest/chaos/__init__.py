"""장애 주입 안전장치: 허용 대상 판정, 스냅샷, 되돌리기(M1-05, ADR-0007, Spec "장애 주입").

주입 허용 대상: product.repo_path 아래, ~/forge-sandbox/ 아래 경로, 이름이 pf-lab으로 시작하는
OrbStack 머신('lab:<이름>'). 그 밖은 거절한다. 시스템 경로와 Tech Radar 리포는 명시적으로 거절한다.
Docker(9장)·k3d(12장) 대상은 그 장을 만들 때 더한다.

2026-11-13 결정: 경로 스냅샷은 대상 폴더를 .git까지 통째로 tar로 묶는다. Spec의
'git bundle + 추적 파일 묶음'과 같은 상태를 한 방법으로 되돌린다.
랩 머신 안의 변경은 시나리오의 cleanup이 되돌린다.
"""

import json
import os
import shutil
import stat
import tarfile
import tempfile
from pathlib import Path

from quest.core.mission import Chaos, Ctx

LAB_PREFIX = "pf-lab"
REFUSED_ROOTS = ("/System", "/usr", "/etc", "/bin", "/sbin", "/Library", "~/Library",
                 "C:/Windows", "C:/Program Files")
REFUSED_NAMES = ("tech-radar-agent",)
MANIFEST = "manifest.json"


def _path(ctx: Ctx, target: str) -> Path:
    candidate = Path(target).expanduser()
    return (candidate if candidate.is_absolute() else ctx.workdir / candidate).resolve()


def _under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def refusal(ctx: Ctx, target: str) -> str | None:
    """주입하면 안 되는 대상이면 그 이유, 괜찮으면 None."""
    if target.startswith("lab:"):
        name = target.removeprefix("lab:")
        ok = name.startswith(LAB_PREFIX)
        return None if ok else f"랩 머신 이름이 {LAB_PREFIX}로 시작하지 않음: {name}"
    path = _path(ctx, target)
    if any(_under(path, Path(root).expanduser().resolve()) for root in REFUSED_ROOTS):
        return f"시스템 경로는 건드리지 않음: {path}"
    if any(name in path.parts for name in REFUSED_NAMES):
        return f"Tech Radar 리포는 건드리지 않음: {path}"
    repo = Path(ctx.config.get("product", {}).get("repo_path", "")).expanduser()
    allowed = [(Path.home() / "forge-sandbox").resolve()]
    if repo.parts:
        allowed.append(repo.resolve())
    if not any(_under(path, root) for root in allowed):
        return f"주입 허용 대상(OpsDesk 리포·~/forge-sandbox) 밖: {path}"
    return None


def refusals(ctx: Ctx, chaos: Chaos) -> list[str]:
    return [reason for target in chaos.targets if (reason := refusal(ctx, target))]


def snapshot(ctx: Ctx, chaos: Chaos, folder: Path) -> None:
    """경로 대상을 folder에 묶어 둔다. 없던 경로는 '없었음'으로 적어 되돌릴 때 지운다."""
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    for number, target in enumerate(t for t in chaos.targets if not t.startswith("lab:")):
        path = _path(ctx, target)
        entries.append({"path": str(path), "existed": path.exists(), "archive": f"{number}.tar"})
        if path.exists():
            with tarfile.open(folder / f"{number}.tar", "w") as archive:
                archive.add(path, arcname=path.name)
    (folder / MANIFEST).write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")


def _unlock(path: Path) -> None:
    """지우기 전에 소유자 읽기·쓰기(폴더는 열기까지)를 연다. 링크는 따라가지 않는다.

    Windows는 git이 .git/objects를 읽기 전용으로 두고, 장애 시나리오는 chmod 000을 걸 수 있다.
    """
    if path.is_symlink():
        return
    if path.is_dir():
        os.chmod(path, stat.S_IRWXU)
        for child in path.iterdir():
            _unlock(child)
    else:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _remove(path: Path) -> None:
    if path.is_symlink():  # 링크 자체만 지운다. 가리키는 파일의 권한은 건드리지 않는다
        path.unlink()
    elif path.is_dir():
        _unlock(path)
        shutil.rmtree(path)
    elif path.exists():
        _unlock(path)
        path.unlink()


def restore(folder: Path) -> None:
    """snapshot이 묶어 둔 상태로 되돌린다.

    먼저 임시 폴더에 다 풀어 본 뒤 바꿔 끼운다. 풀다가 실패해도 지금 파일은 그대로 남는다.
    우리가 만든 묶음이라 'tar' 필터를 쓴다('data'는 .venv 같은 절대 경로 링크를 거절한다).
    """
    for entry in json.loads((folder / MANIFEST).read_text(encoding="utf-8")):
        path = Path(entry["path"])
        if not entry["existed"]:
            _remove(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)  # 시나리오가 상위 폴더까지 지웠을 수 있다
        staging = Path(tempfile.mkdtemp(prefix=".quest-restore-", dir=path.parent))
        try:
            with tarfile.open(folder / entry["archive"]) as archive:
                archive.extractall(staging, filter="tar")  # 절대 경로·.. 로 밖에 풀리지 않게
            _remove(path)
            (staging / path.name).rename(path)
        finally:
            _remove(staging)
