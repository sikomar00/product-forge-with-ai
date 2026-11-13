"""설정 시험: 환경 변수로 위치 바꾸기, 기본 설정 만들기, 형식 오류."""

from pathlib import Path

import pytest

from quest.core import config


@pytest.fixture
def cfg_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "cfg" / "config.toml"
    monkeypatch.setenv("QUEST_CONFIG", str(path))
    return path


def test_quest_home_env_overrides_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUEST_HOME", str(tmp_path))
    assert config.home() == tmp_path


def test_default_home_is_xdg_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUEST_HOME", raising=False)
    assert config.home() == Path.home() / ".local" / "share" / "quest"


def test_ensure_config_creates_default_once(cfg_file: Path) -> None:
    assert config.ensure_config() is True
    assert config.ensure_config() is False
    loaded = config.load_config()
    assert loaded["review"]["lock_threshold"] == 20
    assert loaded["lab"]["vm_name"] == "pf-lab"


def test_ensure_config_keeps_existing_file(cfg_file: Path) -> None:
    cfg_file.parent.mkdir(parents=True)
    cfg_file.write_text('[lab]\nvm_name = "pf-lab-2"\n', encoding="utf-8")
    assert config.ensure_config() is False
    assert config.load_config()["lab"]["vm_name"] == "pf-lab-2"


def test_missing_config_is_env_error(cfg_file: Path) -> None:
    with pytest.raises(config.EnvError, match="없습니다"):
        config.load_config()


def test_broken_config_is_env_error(cfg_file: Path) -> None:
    cfg_file.parent.mkdir(parents=True)
    cfg_file.write_text("[lab\n", encoding="utf-8")
    with pytest.raises(config.EnvError, match="형식"):
        config.load_config()
