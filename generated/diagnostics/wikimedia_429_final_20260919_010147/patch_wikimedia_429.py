from pathlib import Path
import ast
import sys

path = Path(sys.argv[1])

source = path.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(source)
lines = source.splitlines()

target = None

for node in ast.walk(tree):
    if (
        isinstance(node, ast.FunctionDef)
        and node.name == "_api"
    ):
        target = node
        break

if target is None:
    raise RuntimeError(
        "_api method not found"
    )

old = "\n".join(
    lines[
        target.lineno - 1:
        target.end_lineno
    ]
)

for marker in (
    "urllib.request.Request",
    "urllib.request.urlopen",
    "timeout=30",
    "json.loads",
):
    if marker not in old:
        raise RuntimeError(
            "Unexpected live _api; missing "
            + marker
        )

if "Retry-After" in old:
    raise RuntimeError(
        "_api already contains the intended "
        "Retry-After patch"
    )

new = r'''    def _api(
        self,
        params: dict[str, str],
    ) -> dict:
        """
        Wikimedia API request with bounded transient
        failure handling.

        Persistent provider throttling returns an empty
        provider result instead of terminating the full
        production pipeline.

        Licensing, relevance, authorization and other
        content-safety gates are unchanged.
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

replacement = new.splitlines()

patched_lines = (
    lines[:target.lineno - 1]
    + replacement
    + lines[target.end_lineno:]
)

patched = "\n".join(
    patched_lines
) + "\n"

ast.parse(patched)

# Verify exactly one implementation remains.
verify_tree = ast.parse(patched)

api_methods = [
    node
    for node in ast.walk(verify_tree)
    if (
        isinstance(node, ast.FunctionDef)
        and node.name == "_api"
    )
]

if len(api_methods) != 1:
    raise RuntimeError(
        f"Expected exactly one _api, found "
        f"{len(api_methods)}"
    )

api_source = ast.get_source_segment(
    patched,
    api_methods[0],
)

for marker in (
    "attempts = 3",
    "exc.code != 429",
    "Retry-After",
    "15.0",
    "time.sleep",
    "return {}",
    "urllib.error.URLError",
):
    if marker not in api_source:
        raise RuntimeError(
            "Patched _api missing "
            + marker
        )

path.write_text(
    patched,
    encoding="utf-8",
)

print("[PASS] Exact original _api located.")
print("[PASS] Exactly one _api implementation retained.")
print("[PASS] Maximum API attempts = 3.")
print("[PASS] HTTP 429 handled.")
print("[PASS] Retry-After handled.")
print("[PASS] Retry delay capped at 15 seconds.")
print("[PASS] Missing Retry-After uses bounded backoff.")
print("[PASS] Transport failures bounded.")
print("[PASS] Persistent throttling returns empty result.")
print("[PASS] Non-429 HTTP errors remain fail-loud.")
