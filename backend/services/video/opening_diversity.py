"""Prefer a visibly new opening shot only among near-equal strict matches."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image


@lru_cache(maxsize=512)
def frame_signature(path: str) -> int | None:
    """A small difference hash for obvious near-identical preview frames."""
    try:
        with Image.open(Path(path)) as image:
            pixels = image.convert("L").resize((9, 8)).tobytes()
        value = 0
        for row in range(8):
            for col in range(8):
                value = (value << 1) | int(pixels[row * 9 + col] > pixels[row * 9 + col + 1])
        return value
    except (OSError, ValueError):
        return None


def opening_choice(matches: list[tuple], recent_previews: list[str], *,
                   near_score: float = .025) -> tuple | None:
    """Return the strongest match unless a nearly equal distinct frame exists.

    Inputs have already passed the OpenCLIP positive/negative, identity and
    provenance gates and are ordered by final semantic score. Missing image
    signatures never displace the best candidate. The caller limits this to
    opening beats; source continuity later in the story remains untouched.
    """
    if not matches:
        return None
    best = matches[0]
    if not recent_previews:
        return best
    recent = [frame_signature(path) for path in recent_previews]
    recent = [value for value in recent if value is not None]
    if not recent:
        return best

    def repeated(match: tuple) -> bool:
        signature = frame_signature(match[0].preview_path)
        return signature is not None and any((signature ^ prior).bit_count() <= 5
                                             for prior in recent)

    if not repeated(best):
        return best
    for candidate in matches[1:]:
        if best[3] - candidate[3] > near_score:
            break
        if not repeated(candidate):
            return candidate
    return best
