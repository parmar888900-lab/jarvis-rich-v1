from __future__ import annotations

import ast
import importlib
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
    / f"wikimedia_429_discovered_{STAMP}"
)

BACKUP = (
    BACKUP_DIR
    / "wikimedia.py"
)

RESULT = (
    ROOT
    / "generated"
    / "diagnostics"
    / f"wikimedia_429_discovered_{STAMP}"
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
    "class_name": None,
    "tests": [],
    "backup": str(BACKUP),
}


def passed(message):
    state["tests"].append(
        message
    )

    print(
        f"[PASS] {message}",
        flush=True,
    )


def save():
    RESULT.write_text(
        json.dumps(
            state,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def restore():
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
            "wikimedia.py not found."
        )

    original = SOURCE.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        original
    )

    # ----------------------------------------
    # DISCOVER THE CLASS THAT OWNS _api
    # ----------------------------------------

    owners = []

    for node in tree.body:

        if not isinstance(
            node,
            ast.ClassDef,
        ):
            continue

        for child in node.body:

            if (
                isinstance(
                    child,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                )
                and child.name == "_api"
            ):
                owners.append(
                    (
                        node,
                        child,
                    )
                )

    if len(owners) != 1:

        raise RuntimeError(
            "Expected exactly one class owning _api; "
            f"found {len(owners)}."
        )

    class_node, api_node = owners[0]

    CLASS_NAME = class_node.name

    state[
        "class_name"
    ] = CLASS_NAME

    print(
        f"[INFO] Discovered provider class: "
        f"{CLASS_NAME}",
        flush=True,
    )

    passed(
        "Actual _api owner discovered from AST."
    )

    old_api = ast.get_source_segment(
        original,
        api_node,
    )

    if old_api is None:
        raise RuntimeError(
            "Could not extract live _api method."
        )

    for marker in (
        "urllib.request.Request",
        "urllib.request.urlopen",
        "timeout=30",
        "json.loads",
    ):

        if marker not in old_api:

            raise RuntimeError(
                "Unexpected live _api; missing "
                + marker
            )

    if "Retry-After" in old_api:

        raise RuntimeError(
            "Live _api already contains Retry-After "
            "handling. Refusing to stack patches."
        )

    shutil.copy2(
        SOURCE,
        BACKUP,
    )

    passed(
        "Current Wikimedia source backed up."
    )

    lines = original.splitlines()

    # ----------------------------------------
    # REPLACE ONLY _api
    # ----------------------------------------

    new_api = r'''    def _api(
        self,
        params: dict[str, str],
    ) -> dict:
        """
        Wikimedia API request with bounded handling for
        HTTP 429 and temporary transport failures.

        Persistent provider throttling becomes an empty
        provider result instead of terminating the full
        video pipeline.

        Licensing, relevance and authorization logic
        remain unchanged elsewhere.
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
        lines[:api_node.lineno - 1]
        + new_api.splitlines()
        + lines[api_node.end_lineno:]
    )

    patched = (
        "\n".join(
            patched_lines
        )
        + "\n"
    )

    # ----------------------------------------
    # VERIFY PATCH STRUCTURE BEFORE WRITE
    # ----------------------------------------

    patched_tree = ast.parse(
        patched
    )

    patched_owners = []

    for node in patched_tree.body:

        if not isinstance(
            node,
            ast.ClassDef,
        ):
            continue

        for child in node.body:

            if (
                isinstance(
                    child,
                    ast.FunctionDef,
                )
                and child.name == "_api"
            ):

                patched_owners.append(
                    (
                        node,
                        child,
                    )
                )

    if len(patched_owners) != 1:

        raise RuntimeError(
            "Patched source must contain exactly "
            "one class-owned _api."
        )

    patched_class, patched_api_node = (
        patched_owners[0]
    )

    if patched_class.name != CLASS_NAME:

        raise RuntimeError(
            "Patch changed _api ownership unexpectedly."
        )

    patched_api = ast.get_source_segment(
        patched,
        patched_api_node,
    )

    for marker in (
        "attempts = 3",
        "Retry-After",
        "exc.code != 429",
        "15.0",
        "urllib.error.URLError",
        "return {}",
    ):

        if marker not in patched_api:

            raise RuntimeError(
                "Patched _api missing "
                + marker
            )

    SOURCE.write_text(
        patched,
        encoding="utf-8",
    )

    state[
        "patched"
    ] = True

    passed(
        "_api patched structurally."
    )

    compile(
        SOURCE.read_text(
            encoding="utf-8-sig"
        ),
        str(SOURCE),
        "exec",
    )

    passed(
        "Patched Wikimedia source compiles."
    )

    # ----------------------------------------
    # IMPORT REAL DISCOVERED CLASS
    # ----------------------------------------

    sys.path.insert(
        0,
        str(ROOT),
    )

    MODULE_NAME = (
        "backend.services.video."
        "media_sources.wikimedia"
    )

    if MODULE_NAME in sys.modules:

        del sys.modules[
            MODULE_NAME
        ]

    module = importlib.import_module(
        MODULE_NAME
    )

    provider_class = getattr(
        module,
        CLASS_NAME,
        None,
    )

    if provider_class is None:

        raise RuntimeError(
            f"Discovered class {CLASS_NAME!r} "
            "was not present after import."
        )

    if not hasattr(
        provider_class,
        "_api",
    ):

        raise RuntimeError(
            f"{CLASS_NAME} has no _api after import."
        )

    passed(
        f"Imported actual provider class {CLASS_NAME}."
    )

    provider = provider_class.__new__(
        provider_class
    )

    # Use live class constants when present.
    if not hasattr(
        provider,
        "API_URL",
    ):

        provider.API_URL = (
            "https://commons.wikimedia.org/"
            "w/api.php"
        )

    if not hasattr(
        provider,
        "USER_AGENT",
    ):

        provider.USER_AGENT = (
            "Jarvis-Offline-429-Test/1.0"
        )


    def make_error(
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
            url=provider.API_URL,
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


    # ----------------------------------------
    # TEST 1 - PERSISTENT 429
    # ----------------------------------------

    count = {
        "value": 0
    }

    sleeps = []


    def always_429(
        *args,
        **kwargs,
    ):

        count[
            "value"
        ] += 1

        raise make_error(
            429,
            2,
        )


    def capture_sleep(
        seconds,
    ):

        sleeps.append(
            float(
                seconds
            )
        )


    with patch(
        MODULE_NAME
        + ".urllib.request.urlopen",
        side_effect=always_429,
    ), patch(
        MODULE_NAME
        + ".time.sleep",
        side_effect=capture_sleep,
    ):

        result = provider._api(
            {
                "action": "query",
                "format": "json",
            }
        )

    assert result == {}
    assert count["value"] == 3
    assert sleeps == [
        2.0,
        2.0,
    ]

    passed(
        "Persistent 429 -> 3 attempts -> empty result."
    )

    # ----------------------------------------
    # TEST 2 - 429 THEN SUCCESS
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


    def sequence_open(
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
        MODULE_NAME
        + ".urllib.request.urlopen",
        side_effect=sequence_open,
    ), patch(
        MODULE_NAME
        + ".time.sleep",
        side_effect=capture_sleep,
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

    passed(
        "429 followed by success recovers."
    )

    # ----------------------------------------
    # TEST 3 - RETRY-AFTER CAP
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
        MODULE_NAME
        + ".urllib.request.urlopen",
        side_effect=sequence_open,
    ), patch(
        MODULE_NAME
        + ".time.sleep",
        side_effect=capture_sleep,
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

    passed(
        "Retry-After capped at 15 seconds."
    )

    # ----------------------------------------
    # TEST 4 - NO RETRY-AFTER
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
        MODULE_NAME
        + ".urllib.request.urlopen",
        side_effect=sequence_open,
    ), patch(
        MODULE_NAME
        + ".time.sleep",
        side_effect=capture_sleep,
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

    passed(
        "Missing Retry-After uses bounded backoff."
    )

    # ----------------------------------------
    # TEST 5 - HTTP 500 STILL RAISES
    # ----------------------------------------

    raised_500 = False

    with patch(
        MODULE_NAME
        + ".urllib.request.urlopen",
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

    passed(
        "HTTP 500 remains fail-loud."
    )

    # ----------------------------------------
    # TEST 6 - URL ERROR
    # ----------------------------------------

    count = {
        "value": 0
    }


    def always_url_error(
        *args,
        **kwargs,
    ):

        count[
            "value"
        ] += 1

        raise urllib.error.URLError(
            "offline-test"
        )


    with patch(
        MODULE_NAME
        + ".urllib.request.urlopen",
        side_effect=always_url_error,
    ), patch(
        MODULE_NAME
        + ".time.sleep",
        return_value=None,
    ):

        result = provider._api(
            {
                "action": "query",
                "format": "json",
            }
        )

    assert result == {}
    assert count["value"] == 3

    passed(
        "URLError -> 3 attempts -> empty result."
    )

    # ----------------------------------------
    # PRESERVE EXISTING SAFETY/QUALITY STACK
    # ----------------------------------------

    final_wiki = SOURCE.read_text(
        encoding="utf-8-sig"
    )

    for marker in (
        "_license_allowed",
        "relevance < 65.0",
        "commercial_use_allowed=True",
        "attribution_required",
    ):

        if marker not in final_wiki:

            raise RuntimeError(
                "Wikimedia preservation failure: "
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
        "MAX_SEMANTIC_MEDIA_ENRICHMENTS = 6"
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

    passed(
        "Wikimedia license/relevance gates preserved."
    )

    passed(
        "Pipeline rights authorization preserved."
    )

    passed(
        "Evidence contract and script gates preserved."
    )

    passed(
        "Block 5 pipeline/renderer QA preserved."
    )

    state[
        "success"
    ] = True

    save()

    print()
    print("=" * 60)
    print("WIKIMEDIA 429 ATOMIC TEST PASSED")
    print("=" * 60)

    print(
        f"[PASS] Actual provider class: "
        f"{CLASS_NAME}"
    )

    print(
        "[PASS] Patch retained."
    )

    print(
        "[PASS] No network request."
    )

    print(
        "[PASS] No generation/render/upload."
    )


except BaseException as exc:

    state[
        "exception_type"
    ] = type(
        exc
    ).__name__

    state[
        "exception"
    ] = str(
        exc
    )

    state[
        "traceback"
    ] = traceback.format_exc()

    print()
    print("=" * 60)
    print("WIKIMEDIA 429 ATOMIC TEST FAILED")
    print("=" * 60)

    print(
        "TYPE:",
        type(
            exc
        ).__name__,
    )

    print(
        "REASON:",
        str(
            exc
        ),
    )

    print()
    print(
        traceback.format_exc()
    )

    try:
        restore()

    except BaseException:

        print(
            "[CRITICAL] Automatic restore failed."
        )

        print(
            traceback.format_exc()
        )

    save()

    sys.exit(
        1
    )
