"""설정 파일과 게임 데이터 위치(Spec "파일 위치", "설정 파일")."""

import os
import tomllib
from pathlib import Path

DEFAULT_CONFIG = """\
[product]
repo_path = "~/code/opsdesk"          # OpsDesk 리포(2-2에서 만든다)
github_owner = "<GitHub 사용자 이름>"

[content]
repo = "<GitHub 사용자 이름>/product-forge-content"
path = "~/.local/share/quest/content"

[lab]
vm_name = "pf-lab"                    # OrbStack 머신 이름

[review]
lock_threshold = 20                   # 복습 잠금 기준
"""


class EnvError(Exception):
    """설정·콘텐츠·SQLite 버전·도구 문제. CLI가 종료 코드 3으로 바꾼다(Spec "종료 코드")."""


def home() -> Path:
    """게임 데이터 루트. 테스트·플레이스루는 QUEST_HOME으로 바꾼다."""
    if env := os.environ.get("QUEST_HOME"):
        return Path(env)
    return Path.home() / ".local" / "share" / "quest"


def config_path() -> Path:
    if env := os.environ.get("QUEST_CONFIG"):
        return Path(env)
    return Path.home() / ".config" / "quest" / "config.toml"


def ensure_config() -> bool:
    """설정 파일이 없으면 기본값으로 만든다. 만들었으면 True(바꿔야 할 칸 안내용)."""
    path = config_path()
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return True


def load_config() -> dict:
    path = config_path()
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EnvError(f"설정 파일이 없습니다: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise EnvError(f"설정 파일 형식이 틀렸습니다: {path} ({exc})") from exc
