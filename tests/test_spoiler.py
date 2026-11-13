"""난독화 시험(M0-09): obf1: + base64(zlib(UTF-8))."""

import base64
import zlib

import pytest

from quest.core import spoiler


def test_round_trip_keeps_korean_and_symbols() -> None:
    text = "git log --oneline | head -3  # 최근 커밋 3개 ✅"
    hidden = spoiler.obfuscate(text)
    assert hidden.startswith("obf1:") and "git" not in hidden
    assert spoiler.reveal(hidden) == text


def test_format_matches_spec() -> None:
    expected = "obf1:" + base64.b64encode(zlib.compress("답".encode())).decode()
    assert spoiler.obfuscate("답") == expected


NOT_ZLIB = "obf1:" + base64.b64encode(b"x").decode()


@pytest.mark.parametrize("bad", ["평문", "obf1:", "obf1:!!!", NOT_ZLIB])
def test_broken_text_does_not_decode(bad: str) -> None:
    assert spoiler.decodes(bad) is False


def test_plain_text_is_refused() -> None:
    with pytest.raises(ValueError, match="obf1"):
        spoiler.reveal("평문")
