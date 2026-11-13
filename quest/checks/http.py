"""HTTP 체크(표준 라이브러리 urllib·ssl, Plan: httpx는 쓰지 않는다). GET만 한다.

서버가 응답하지 않는 것(학습자의 서버가 아직 안 떠 있음)은 실패이지 환경 문제가 아니다.
인증서를 확인하지 못하는 것은 환경 문제(CheckEnvError)다.
"""

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass

from quest.checks import verdict
from quest.core.mission import CheckEnvError, Ctx, Result

TIMEOUT_SEC = 10
MISSING = object()


@dataclass(frozen=True)
class Response:
    status: int | None  # None: 응답 없음(연결 거부·시간 초과·주소 없음)
    body: str


def get(ctx: Ctx, url: str) -> Response:
    request = urllib.request.Request(url, headers={"User-Agent": "quest-check"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as resp:  # noqa: S310 - GET만
            return Response(resp.status, resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return Response(exc.code, exc.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLError):
            raise CheckEnvError(f"인증서를 확인하지 못했습니다: {exc.reason}") from exc
        return Response(None, "")
    except TimeoutError:
        return Response(None, "")


def status_is(ctx: Ctx, url: str, expected: int) -> Result:
    status = get(ctx, url).status
    return verdict(status == expected, f"HTTP {status if status is not None else '응답 없음'}")


def json_value(ctx: Ctx, url: str, keys: tuple[str | int, ...] = ()) -> object:
    """응답 JSON에서 keys 경로의 값. 응답이 없거나 JSON이 아니거나 키가 없으면 MISSING."""
    response = get(ctx, url)
    try:
        current = json.loads(response.body)
        for key in keys:
            current = current[key]
    except (ValueError, KeyError, IndexError, TypeError):
        return MISSING
    return current
