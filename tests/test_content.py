"""콘텐츠 불러오기 시험(M0-04, M0-05, M0-18): 가짜 콘텐츠, 검증 메시지, 호환 확인."""

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from quest.core import content
from quest.core.config import EnvError
from quest.core.mission import KINDS, Card, Item

FAKE = Path(__file__).parent / "fixtures" / "fake_content"


@pytest.fixture(scope="module")
def loaded() -> content.Content:
    return content.load_content(FAKE)


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    """고쳐 볼 수 있는 가짜 콘텐츠 사본."""
    return Path(shutil.copytree(FAKE, tmp_path / "fake"))


def test_fake_content_covers_all_eight_kinds(loaded: content.Content) -> None:
    assert {m.kind for m in loaded.missions} == set(KINDS)


def test_missions_keep_chapter_then_file_order(loaded: content.Content) -> None:
    ids = [m.id for m in loaded.missions]
    assert ids == ["0-1", "0-2", "0-3", "0-4", "0-5", "1-1", "1-2", "1-3", "1-B"]


def test_delayed_quiz_is_keyed_by_chapter(loaded: content.Content) -> None:
    assert list(loaded.delayed_quiz) == [0]
    assert len(loaded.delayed_quiz[0]) == 10


def test_content_root_comes_from_config() -> None:
    root = content.content_root({"content": {"path": "~/somewhere"}})
    assert root == Path.home() / "somewhere"


def test_config_without_content_path_is_env_error() -> None:
    with pytest.raises(EnvError, match="path"):
        content.content_root({})


def test_missing_content_toml_points_to_update(tmp_path: Path) -> None:
    with pytest.raises(EnvError, match="quest update"):
        content.load_content(tmp_path)


def test_broken_content_module_names_the_file(copy: Path) -> None:
    (copy / "content" / "ch02_broken.py").write_text("raise ValueError('x')\n", encoding="utf-8")
    with pytest.raises(EnvError, match="ch02_broken.py"):
        content.load_content(copy)


def test_module_without_missions_is_reported(copy: Path) -> None:
    (copy / "content" / "ch02_empty.py").write_text("X = 1\n", encoding="utf-8")
    with pytest.raises(EnvError, match="ch02_empty.py: MISSIONS"):
        content.load_content(copy)


def test_missing_requires_engine_says_missing(copy: Path) -> None:
    (copy / "content.toml").write_text("[tools]\n", encoding="utf-8")
    with pytest.raises(EnvError, match="requires_engine이 없습니다"):
        content.load_content(copy)


def test_two_delayed_quizzes_for_one_chapter_are_reported(copy: Path) -> None:
    shutil.copy(copy / "content" / "ch00_fake.py", copy / "content" / "ch00_more.py")
    with pytest.raises(EnvError, match="ch00_more.py: 0장 DELAYED_QUIZ"):
        content.load_content(copy)


def test_engine_too_old_is_refused() -> None:
    with pytest.raises(EnvError, match="엔진을 갱신"):
        content.load_content(FAKE, engine_version="0.0.9")


@pytest.mark.parametrize(
    ("spec", "engine", "expected"),
    [
        (">=0.1,<0.2", "0.1.0", True),
        (">=0.1,<0.2", "0.1.7", True),
        (">=0.1,<0.2", "0.2.0", False),
        (">=0.1,<0.2", "0.0.9", False),
        ("==0.3.1", "0.3.1", True),
        ("!=0.3.1", "0.3.1", False),
    ],
)
def test_satisfies(spec: str, engine: str, expected: bool) -> None:
    assert content.satisfies(spec, engine) is expected


@pytest.mark.parametrize("spec", ["", "~=0.1", ">=0.1;<0.2"])
def test_bad_requires_engine_is_env_error(spec: str) -> None:
    with pytest.raises(EnvError, match="requires_engine"):
        content.satisfies(spec, "0.1.0")


# ───────────── 검증: 어느 미션이 왜 틀렸는지 ─────────────

BAD_CARD = Card("c_bad", "concept", "앞", "Z", "choice", ("A",))
BAD_ITEM = Item(1, "문항", "essay", "평문")


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"key": "m_XYZ"}, "미션 키 형식"),
        ({"ch": 18}, "장 번호는 0~17"),
        ({"kind": "lecture"}, "알 수 없는 유형"),
        ({"ai": "auto"}, "AI 사용 방식"),
        ({"track": "bonus"}, "트랙"),
        ({"scaffold": "free"}, "스캐폴드"),
        ({"est_min": 0}, "est_min"),
        ({"hints": ("obf1:a",)}, "힌트는 3개"),
        ({"hints": ("a", "b", "c")}, "힌트는 난독화"),
        ({"solution": "평문"}, "모범 답안은 난독화"),
        ({"checks": ()}, "체크가 있어야"),
        ({"cards": (BAD_CARD,)}, "카드 키 형식"),
        ({"cards": (BAD_CARD,)}, "뒷면이 보기에 없습니다"),
        ({"explain": (BAD_ITEM,)}, "알 수 없는 문항 형식"),
        ({"explain": (BAD_ITEM,)}, "정답은 난독화"),
    ],
)
def test_invalid_mission_says_which_and_why(
    loaded: content.Content, changes: dict, reason: str
) -> None:
    bad = replace(loaded.missions[0], **changes)
    errors = content.validate([bad], {})
    assert any(e.startswith(f"{bad.key} (0-1): ") and reason in e for e in errors), errors


def test_item_kind_mission_needs_items(loaded: content.Content) -> None:
    quiz = replace(loaded.missions[1], items=())
    assert any("문항이 있어야" in e for e in content.validate([quiz], {}))


def test_numbering_must_start_at_one_without_gaps(loaded: content.Content) -> None:
    check = loaded.missions[0].checks[0]
    bad = replace(loaded.missions[0], checks=(check, replace(check, no=3)))
    assert any("체크 번호는 1부터" in e for e in content.validate([bad], {}))


def test_duplicate_keys_and_ids_are_reported(loaded: content.Content) -> None:
    first = loaded.missions[0]
    errors = content.validate([first, replace(first, id="0-9")], {})
    assert "미션 키 중복: m_f0000001" in errors
    assert "카드 키 중복: c_f0000001" in errors
    errors = content.validate([first, replace(first, key="m_f00000ff", cards=())], {})
    assert errors == ["화면 번호 중복: 0-1"]


def test_delayed_quiz_needs_ten_items(loaded: content.Content) -> None:
    errors = content.validate([], {0: loaded.delayed_quiz[0][:9]})
    assert errors == ["0장 DELAYED_QUIZ: 문항은 10개여야 합니다: 9개"]


def test_fake_content_has_no_errors(loaded: content.Content) -> None:
    assert content.validate(list(loaded.missions), loaded.delayed_quiz) == []
