"""힌트·모범 답안·정답의 난독화(Spec "힌트와 모범 답안").

보안이 아니라 우연히 보는 것을 막는 용도다.
"""

import base64
import binascii
import zlib

PREFIX = "obf1:"


def obfuscate(text: str) -> str:
    return PREFIX + base64.b64encode(zlib.compress(text.encode("utf-8"))).decode("ascii")


def reveal(text: str) -> str:
    if not text.startswith(PREFIX):
        raise ValueError("obf1: 형식이 아닙니다")
    raw = base64.b64decode(text[len(PREFIX):], validate=True)
    return zlib.decompress(raw).decode("utf-8")


def decodes(text: str) -> bool:
    """콘텐츠 검증용: 형식이 맞고 실제로 풀리는지."""
    try:
        reveal(text)
    except (ValueError, binascii.Error, zlib.error, UnicodeDecodeError):
        return False
    return True
