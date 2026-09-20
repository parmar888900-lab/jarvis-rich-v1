import asyncio
import inspect as pyinspect
import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

TOPIC = "Why movie sound effects are often recorded separately"


def serial(value):

    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): serial(child)
            for key, child in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return [
            serial(child)
            for child in value
        ]

    if hasattr(value, "model_dump"):
        try:
            return serial(
                value.model_dump()
            )
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return serial(
                vars(value)
            )
        except Exception:
            pass

    return repr(value)


async def main():

    print(
        "[INFO] Topic:",
        TOPIC,
        flush=True,
    )

    from backend.services.pipelines.video_pipeline import (
        VideoPipeline,
    )

    pipeline = VideoPipeline()

    research_service = None
    research_attr = None

    # First: locate the evergreen research service.
    for name, value in vars(pipeline).items():

        class_name = (
            type(value).__name__.lower()
        )

        if (
            "evergreen" in class_name
            and "research" in class_name
        ):
            research_service = value
            research_attr = name
            break

    # Second: bounded fallback discovery.
    if research_service is None:

        for name, value in vars(pipeline).items():

            class_name = (
                type(value).__name__.lower()
            )

            if "research" in class_name:
                research_service = value
                research_attr = name
                break

    if research_service is None:
        raise RuntimeError(
            "Pipeline research service was not found."
        )

    print(
        "[PASS] Research service:",
        research_attr,
        type(research_service).__name__,
        flush=True,
    )

    method = getattr(
        research_service,
        "research",
        None,
    )

    if method is None:
        raise RuntimeError(
            "Research service has no research() method."
        )

    signature = pyinspect.signature(
        method
    )

    print(
        "[INFO] research() signature:",
        signature,
        flush=True,
    )

    kwargs = {}

    for name, parameter in (
        signature.parameters.items()
    ):

        if name == "topic":
            kwargs[name] = TOPIC

        elif name in {
            "genre",
            "format_name",
            "reference_format",
        }:
            kwargs[name] = "movie_facts"

        elif (
            parameter.default
            is pyinspect.Parameter.empty
        ):
            raise RuntimeError(
                "Unsupported required research argument: "
                + name
            )

    print(
        "[INFO] Calling research service only...",
        flush=True,
    )

    result = method(
        **kwargs
    )

    if pyinspect.isawaitable(
        result
    ):
        result = await result

    print(
        "[PASS] Research returned.",
        flush=True,
    )

    converted = serial(
        result
    )

    print()
    print("=" * 72)
    print("RAW OBJECT TYPE")
    print("=" * 72)
    print(
        type(result).__name__
    )

    print()
    print("=" * 72)
    print("EXACT RESEARCH PAYLOAD")
    print("=" * 72)

    if isinstance(result, str):

        research_text = result
        print(result)

    else:

        research_text = json.dumps(
            converted,
            indent=2,
            ensure_ascii=False,
        )

        print(
            research_text
        )

    print()
    print("=" * 72)
    print("EVIDENCE TOKEN ANALYSIS")
    print("=" * 72)

    patterns = {
        "bracket_E": r"\[E\d+\]",
        "plain_E": r"\bE\d+\b",
        "bracket_number": r"\[\d+\]",
        "fact_number": r"(?i)\bfact[_\s-]*\d+\b",
        "source_number": r"(?i)\bsource[_\s-]*\d+\b",
    }

    all_matches = {}

    for label, pattern in (
        patterns.items()
    ):

        matches = re.findall(
            pattern,
            research_text,
        )

        unique = []

        for match in matches:

            value = (
                match
                if isinstance(
                    match,
                    str,
                )
                else str(match)
            )

            if value not in unique:
                unique.append(
                    value
                )

        all_matches[label] = unique

        print()
        print(
            f"{label}: {len(unique)} unique"
        )

        for value in unique[:50]:
            print(
                "  ",
                repr(value),
            )

    print()
    print("=" * 72)
    print("LINES CONTAINING EVIDENCE-LIKE TERMS")
    print("=" * 72)

    terms = (
        "evidence",
        "source",
        "fact",
        "claim",
        "citation",
        "id",
    )

    evidence_lines = []

    for number, line in enumerate(
        research_text.splitlines(),
        start=1,
    ):

        lower = line.lower()

        if any(
            term in lower
            for term in terms
        ):
            evidence_lines.append(
                (number, line)
            )

    if evidence_lines:

        for number, line in (
            evidence_lines[:150]
        ):
            print(
                f"{number:5}: {line}"
            )

    else:

        print(
            "[INFO] No evidence/source/fact/"
            "claim/citation/id lines found."
        )

    print()
    print("=" * 72)
    print("STRUCTURED KEY ANALYSIS")
    print("=" * 72)

    found_keys = 0

    def walk(value, path="root"):

        nonlocal found_keys

        if isinstance(
            value,
            dict,
        ):

            for key, child in (
                value.items()
            ):

                key_text = str(
                    key
                )

                child_path = (
                    f"{path}.{key_text}"
                )

                if any(
                    token in key_text.lower()
                    for token in (
                        "id",
                        "evidence",
                        "source",
                        "fact",
                        "claim",
                        "citation",
                    )
                ):
                    found_keys += 1

                    print(
                        child_path,
                        "=",
                        repr(child)[:800],
                    )

                walk(
                    child,
                    child_path,
                )

        elif isinstance(
            value,
            list,
        ):

            for index, child in enumerate(
                value
            ):
                walk(
                    child,
                    f"{path}[{index}]",
                )

    walk(
        converted
    )

    if found_keys == 0:
        print(
            "[INFO] No structured evidence-like "
            "keys found."
        )

    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    for label, matches in (
        all_matches.items()
    ):
        print(
            f"{label}: {matches}"
        )

    print()
    print("[PASS] Research inspection completed.")
    print("[PASS] No ContentGenerator call.")
    print("[PASS] No media acquisition.")
    print("[PASS] No render.")
    print("[PASS] No upload.")
    print("[PASS] No source modification.")
    print("[PASS] No restart.")


asyncio.run(
    main()
)
