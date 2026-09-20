import sys
import urllib.error

from email.message import Message
from pathlib import Path
from unittest.mock import patch

ROOT = Path.cwd()

sys.path.insert(
    0,
    str(ROOT),
)

from backend.services.video.media_sources.wikimedia import (
    WikimediaMediaSource,
)


def make_http_error(
    code,
    retry_after=None,
):

    headers = Message()

    if retry_after is not None:
        headers[
            "Retry-After"
        ] = str(
            retry_after
        )

    return urllib.error.HTTPError(
        url=(
            "https://commons.wikimedia.org/"
            "w/api.php"
        ),
        code=code,
        msg="offline-test",
        hdrs=headers,
        fp=None,
    )


class FakeResponse:

    def __init__(
        self,
        payload,
    ):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False

    def read(self):
        return self.payload


provider = WikimediaMediaSource.__new__(
    WikimediaMediaSource
)

provider.API_URL = (
    "https://commons.wikimedia.org/"
    "w/api.php"
)

provider.USER_AGENT = (
    "Jarvis-Offline-Test/1.0"
)


# TEST A:
# Persistent 429 must not escape.

count = 0
sleeps = []


def always_429(
    *args,
    **kwargs,
):
    global count

    count += 1

    raise make_http_error(
        429,
        "2",
    )


def fake_sleep(
    seconds,
):
    sleeps.append(
        float(seconds)
    )


with patch(
    "backend.services.video.media_sources."
    "wikimedia.urllib.request.urlopen",
    side_effect=always_429,
), patch(
    "backend.services.video.media_sources."
    "wikimedia.time.sleep",
    side_effect=fake_sleep,
):

    result = provider._api(
        {
            "action": "query",
            "format": "json",
        }
    )

assert result == {}
assert count == 3
assert sleeps == [
    2.0,
    2.0,
]

print(
    "[PASS] Persistent 429 -> exactly "
    "3 attempts -> {}."
)


# TEST B:
# First 429 then valid response.

sequence = [
    make_http_error(
        429,
        "1",
    ),
    FakeResponse(
        b'{"query":{"pages":[]}}'
    ),
]

sleeps = []


def recover(
    *args,
    **kwargs,
):

    item = sequence.pop(0)

    if isinstance(
        item,
        BaseException,
    ):
        raise item

    return item


with patch(
    "backend.services.video.media_sources."
    "wikimedia.urllib.request.urlopen",
    side_effect=recover,
), patch(
    "backend.services.video.media_sources."
    "wikimedia.time.sleep",
    side_effect=fake_sleep,
):

    result = provider._api(
        {
            "action": "query",
            "format": "json",
        }
    )

assert result == {
    "query": {
        "pages": []
    }
}

assert sleeps == [
    1.0
]

print(
    "[PASS] 429 then success recovers."
)


# TEST C:
# Extreme Retry-After is capped.

sequence = [
    make_http_error(
        429,
        "9999",
    ),
    FakeResponse(
        b'{"ok":true}'
    ),
]

sleeps = []


with patch(
    "backend.services.video.media_sources."
    "wikimedia.urllib.request.urlopen",
    side_effect=recover,
), patch(
    "backend.services.video.media_sources."
    "wikimedia.time.sleep",
    side_effect=fake_sleep,
):

    result = provider._api(
        {
            "action": "query",
            "format": "json",
        }
    )

assert result == {
    "ok": True
}

assert sleeps == [
    15.0
]

print(
    "[PASS] Retry-After capped at 15 seconds."
)


# TEST D:
# No Retry-After uses fallback 2 sec.

sequence = [
    make_http_error(
        429,
        None,
    ),
    FakeResponse(
        b'{"ok":true}'
    ),
]

sleeps = []


with patch(
    "backend.services.video.media_sources."
    "wikimedia.urllib.request.urlopen",
    side_effect=recover,
), patch(
    "backend.services.video.media_sources."
    "wikimedia.time.sleep",
    side_effect=fake_sleep,
):

    result = provider._api(
        {
            "action": "query",
            "format": "json",
        }
    )

assert result == {
    "ok": True
}

assert sleeps == [
    2.0
]

print(
    "[PASS] Missing Retry-After -> "
    "bounded fallback."
)


# TEST E:
# HTTP 500 must still escape.

raised = False

with patch(
    "backend.services.video.media_sources."
    "wikimedia.urllib.request.urlopen",
    side_effect=make_http_error(
        500
    ),
):

    try:

        provider._api(
            {
                "action": "query",
                "format": "json",
            }
        )

    except urllib.error.HTTPError as exc:

        raised = (
            exc.code == 500
        )

assert raised

print(
    "[PASS] HTTP 500 remains fail-loud."
)


# TEST F:
# Transport failure exhausts safely.

count = 0


def transport_failure(
    *args,
    **kwargs,
):
    global count

    count += 1

    raise urllib.error.URLError(
        "offline-test"
    )


with patch(
    "backend.services.video.media_sources."
    "wikimedia.urllib.request.urlopen",
    side_effect=transport_failure,
), patch(
    "backend.services.video.media_sources."
    "wikimedia.time.sleep",
    return_value=None,
):

    result = provider._api(
        {
            "action": "query",
            "format": "json",
        }
    )

assert result == {}
assert count == 3

print(
    "[PASS] Transport failure -> "
    "3 attempts -> {}."
)

print(
    "[PASS] ALL OFFLINE 429 TESTS PASSED."
)
