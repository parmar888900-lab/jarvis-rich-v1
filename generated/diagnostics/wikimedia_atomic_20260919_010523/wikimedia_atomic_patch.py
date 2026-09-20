from __future__ import annotations

import ast
import json
import shutil
import sys
import traceback
import urllib.error

from email.message import Message
from pathlib import Path
from unittest.mock import patch


ROOT = Path.cwd()

SOURCE = (
    ROOT
    / "backend"
    / "services"
    / "video"
    / "media_sources"
    / "wikimedia.py"
)

STAMP = sys.argv[1]

BACKUP_DIR = (
    ROOT
    / "generated"
    / "backups"
    / f"wikimedia_429_atomic_{STAMP}"
)

BACKUP = (
    BACKUP_DIR
    / "wikimedia.py"
)

RESULT = (
    ROOT
    / "generated"
    / "diagnostics"
    / f"wikimedia_atomic_{STAMP}"
    / "result.json"
)

BACKUP_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

RESULT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

state = {
    "success": False,
    "patched": False,
    "rolled_back": False,
    "tests": [],
    "backup": str(BACKUP),
}


def record(name: str) -> None:
    state["tests"].append(name)
    print(
        f"[PASS] {name}",
        flush=True,
    )


def save_result() -> None:
    RESULT.write_text(
        json.dumps(
            state,
            indent=2,
        ),
        encoding="utf-8",
    )


def restore() -> None:
    if BACKUP.exists():
        shutil.copy2(
            BACKUP,
            SOURCE,
        )

        compile(
            SOURCE.read_text(
                encoding="utf-8-sig"
            ),
            str(SOURCE),
            "exec",
        )

        state["rolled_back"] = True

        print(
            "[PASS] Original Wikimedia source restored.",
            flush=True,
        )


try:

    if not SOURCE.exists():
        raise RuntimeError(
            "wikimedia.py not found"
        )

    original = SOURCE.read_text(
        encoding="utf-8-sig"
    )

    # Verify original before backup.
    tree = ast.parse(
        original
    )

    methods = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name == "_api"
        )
    ]

    if len(methods) != 1:
        raise RuntimeError(
            f"Expected exactly one _api; "
            f"found {len(methods)}"
        )

    target = methods[0]

    old_api = ast.get_source_segment(
        original,
        target,
    )

    if old_api is None:
        raise RuntimeError(
            "Could not extract _api source"
        )

    for required in (
        "urllib.request.Request",
        "urllib.request.urlopen",
        "timeout=30",
        "json.loads",
    ):
        if required not in old_api:
            raise RuntimeError(
                "Unexpected original _api; "
                f"missing {required}"
            )

    if "Retry-After" in old_api:
        raise RuntimeError(
            "Retry-After handling already exists; "
            "atomic block will not stack patches"
        )

    shutil.copy2(
        SOURCE,
        BACKUP,
    )

    record(
        "Current Wikimedia source backed up."
    )

    lines = original.splitlines()

    new_api = r'''    def _api(
        self,
        params: dict[str, str],
    ) -> dict:
        """
        Wikimedia API request with bounded handling for
        provider throttling and temporary transport failure.

        Persistent 429/transport exhaustion returns an empty
        provider result. Licensing, relevance and rights
        authorization remain unchanged elsewhere.
        """

        url = (
            self.API_URL
            + "?"
            + urllib.parse.urlencode(
                params
            )
        )

        attempts = 3

        for attempt in range(
            1,
            attempts + 1,
        ):

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.USER_AGENT,
                },
            )

            try:

                with urllib.request.urlopen(
                    request,
                    timeout=30,
                ) as response:

                    return json.loads(
                        response.read().decode(
                            "utf-8"
                        )
                    )

            except urllib.error.HTTPError as exc:

                if exc.code != 429:
                    raise

                if attempt >= attempts:
                    return {}

                retry_after = None

                if exc.headers is not None:
                    try:
                        retry_after = (
                            exc.headers.get(
                                "Retry-After"
                            )
                        )
                    except Exception:
                        retry_after = None

                wait_seconds = None

                if retry_after:
                    try:
                        wait_seconds = float(
                            str(
                                retry_after
                            ).strip()
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        wait_seconds = None

                if wait_seconds is None:
                    wait_seconds = min(
                        2.0 ** attempt,
                        8.0,
                    )

                wait_seconds = max(
                    1.0,
                    min(
                        float(
                            wait_seconds
                        ),
                        15.0,
                    ),
                )

                time.sleep(
                    wait_seconds
                )

            except (
                urllib.error.URLError,
                TimeoutError,
            ):

                if attempt >= attempts:
                    return {}

                time.sleep(
                    min(
                        1.5 * attempt,
                        4.5,
                    )
                )

        return {}'''

    patched_lines = (
        lines[:target.lineno - 1]
        + new_api.splitlines()
        + lines[target.end_lineno:]
    )

    patched = (
        "\n".join(
            patched_lines
        )
        + "\n"
    )

    # Syntax check before writing.
    patched_tree = ast.parse(
        patched
    )

    patched_methods = [
        node
        for node in ast.walk(
            patched_tree
        )
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name == "_api"
        )
    ]

    if len(patched_methods) != 1:
        raise RuntimeError(
            "Patched source does not contain "
            "exactly one _api"
        )

    patched_api = ast.get_source_segment(
        patched,
        patched_methods[0],
    )

    for required in (
        "attempts = 3",
        "Retry-After",
        "exc.code != 429",
        "15.0",
        "urllib.error.URLError",
        "return {}",
    ):
        if required not in patched_api:
            raise RuntimeError(
                "Patched _api missing "
                f"{required}"
            )

    SOURCE.write_text(
        patched,
        encoding="utf-8",
    )

    state["patched"] = True

    record(
        "_api patched structurally."
    )

    # Compile from disk.
    compile(
        SOURCE.read_text(
            encoding="utf-8-sig"
        ),
        str(SOURCE),
        "exec",
    )

    record(
        "Patched Wikimedia source compiles."
    )

    # Import the newly written implementation.
    sys.path.insert(
        0,
        str(ROOT),
    )

    module_name = (
        "backend.services.video."
        "media_sources.wikimedia"
    )

    if module_name in sys.modules:
        del sys.modules[
            module_name
        ]

    from backend.services.video.media_sources.wikimedia import (
        WikimediaMediaSource,
    )

    provider = (
        WikimediaMediaSource.__new__(
            WikimediaMediaSource
        )
    )

    provider.API_URL = (
        "https://commons.wikimedia.org/"
        "w/api.php"
    )

    provider.USER_AGENT = (
        "Jarvis-Offline-429-Test/1.0"
    )


    def make_error(
        code: int,
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
            url=provider.API_URL,
            code=code,
            msg="offline-test",
            hdrs=headers,
            fp=None,
        )


    class FakeResponse:

        def __init__(
            self,
            payload: bytes,
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


    # ----------------------------------------
    # TEST 1: persistent 429
    # ----------------------------------------

    request_count = {
        "value": 0
    }

    sleeps = []


    def always_429(
        *args,
        **kwargs,
    ):
        request_count[
            "value"
        ] += 1

        raise make_error(
            429,
            2,
        )


    def capture_sleep(
        value,
    ):
        sleeps.append(
            float(value)
        )


    with patch(
        f"{module_name}."
        "urllib.request.urlopen",
        side_effect=always_429,
    ), patch(
        f"{module_name}."
        "time.sleep",
        side_effect=capture_sleep,
    ):

        value = provider._api(
            {
                "action": "query",
                "format": "json",
            }
        )

    assert value == {}, value

    assert (
        request_count["value"]
        == 3
    ), request_count

    assert sleeps == [
        2.0,
        2.0,
    ], sleeps

    record(
        "Persistent 429 -> 3 attempts -> empty result."
    )


    # ----------------------------------------
    # TEST 2: 429 then success
    # ----------------------------------------

    sequence = [
        make_error(
            429,
            1,
        ),
        FakeResponse(
            b'{"query":{"pages":[]}}'
        ),
    ]

    sleeps = []


    def sequence_urlopen(
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
        f"{module_name}."
        "urllib.request.urlopen",
        side_effect=sequence_urlopen,
    ), patch(
        f"{module_name}."
        "time.sleep",
        side_effect=capture_sleep,
    ):

        value = provider._api(
            {
                "action": "query",
                "format": "json",
            }
        )

    assert value == {
        "query": {
            "pages": []
        }
    }, value

    assert sleeps == [
        1.0
    ], sleeps

    record(
        "429 then success recovers."
    )


    # ----------------------------------------
    # TEST 3: Retry-After cap
    # ----------------------------------------

    sequence = [
        make_error(
            429,
            9999,
        ),
        FakeResponse(
            b'{"ok":true}'
        ),
    ]

    sleeps = []

    with patch(
        f"{module_name}."
        "urllib.request.urlopen",
        side_effect=sequence_urlopen,
    ), patch(
        f"{module_name}."
        "time.sleep",
        side_effect=capture_sleep,
    ):

        value = provider._api(
            {
                "action": "query",
                "format": "json",
            }
        )

    assert value == {
        "ok": True
    }, value

    assert sleeps == [
        15.0
    ], sleeps

    record(
        "Retry-After capped at 15 seconds."
    )


    # ----------------------------------------
    # TEST 4: no Retry-After
    # ----------------------------------------

    sequence = [
        make_error(
            429,
            None,
        ),
        FakeResponse(
            b'{"ok":true}'
        ),
    ]

    sleeps = []

    with patch(
        f"{module_name}."
        "urllib.request.urlopen",
        side_effect=sequence_urlopen,
    ), patch(
        f"{module_name}."
        "time.sleep",
        side_effect=capture_sleep,
    ):

        value = provider._api(
            {
                "action": "query",
                "format": "json",
            }
        )

    assert value == {
        "ok": True
    }, value

    assert sleeps == [
        2.0
    ], sleeps

    record(
        "Missing Retry-After uses 2-second fallback."
    )


    # ----------------------------------------
    # TEST 5: non-429 stays fail-loud
    # ----------------------------------------

    raised_500 = False

    with patch(
        f"{module_name}."
        "urllib.request.urlopen",
        side_effect=make_error(
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

            raised_500 = (
                exc.code == 500
            )

    assert raised_500

    record(
        "HTTP 500 remains fail-loud."
    )


    # ----------------------------------------
    # TEST 6: URLError exhaustion
    # ----------------------------------------

    request_count = {
        "value": 0
    }


    def always_url_error(
        *args,
        **kwargs,
    ):

        request_count[
            "value"
        ] += 1

        raise urllib.error.URLError(
            "offline-test"
        )


    with patch(
        f"{module_name}."
        "urllib.request.urlopen",
        side_effect=always_url_error,
    ), patch(
        f"{module_name}."
        "time.sleep",
        return_value=None,
    ):

        value = provider._api(
            {
                "action": "query",
                "format": "json",
            }
        )

    assert value == {}, value

    assert (
        request_count["value"]
        == 3
    ), request_count

    record(
        "URLError -> 3 attempts -> empty result."
    )


    # ----------------------------------------
    # PRESERVATION
    # ----------------------------------------

    final_source = SOURCE.read_text(
        encoding="utf-8-sig"
    )

    for marker in (
        "_license_allowed",
        "relevance < 65.0",
        "commercial_use_allowed=True",
        "attribution_required",
    ):
        if marker not in final_source:
            raise RuntimeError(
                "Preservation failure: "
                + marker
            )

    pipeline = (
        ROOT
        / "backend"
        / "services"
        / "pipelines"
        / "video_pipeline.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    generator = (
        ROOT
        / "backend"
        / "services"
        / "content_generator.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    renderer = (
        ROOT
        / "backend"
        / "services"
        / "video_renderer"
        / "renderer.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert (
        "BLOCK5_VISUAL_QA_BEGIN"
        in pipeline
    )

    assert (
        "authorize("
        in pipeline
    )

    assert (
        "claim_evidence_validator.validate"
        in generator
    )

    assert (
        "MIN_WORDS = 75"
        in generator
    )

    assert (
        "MAX_WORDS = 110"
        in generator
    )

    assert (
        "BLOCK5_RENDERER_QA_BEGIN"
        in renderer
    )

    record(
        "Rights/relevance metadata preserved."
    )

    record(
        "Evidence gates preserved."
    )

    record(
        "Block 5 pipeline and renderer gates preserved."
    )

    state["success"] = True

    save_result()

    print()
    print("=" * 60)
    print("ATOMIC PATCH SUCCESS")
    print("=" * 60)
    print(
        "[PASS] Patch retained."
    )
    print(
        "[PASS] No rollback required."
    )
    print(
        "[PASS] No network request was made."
    )
    print(
        "[PASS] No generation/render/upload."
    )


except BaseException as exc:

    state[
        "exception_type"
    ] = type(exc).__name__

    state[
        "exception"
    ] = str(exc)

    state[
        "traceback"
    ] = traceback.format_exc()

    print()
    print("=" * 60)
    print("ATOMIC PATCH FAILED")
    print("=" * 60)

    print(
        "TYPE:",
        type(exc).__name__,
    )

    print(
        "REASON:",
        str(exc),
    )

    print()
    print(
        traceback.format_exc()
    )

    try:
        restore()
    except BaseException:
        print(
            "[CRITICAL] Automatic restore failed:"
        )
        print(
            traceback.format_exc()
        )

    save_result()

    sys.exit(1)
