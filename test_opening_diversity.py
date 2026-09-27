"""An opening can change frames without compromising strict semantic rank."""
from types import SimpleNamespace

from PIL import Image

from backend.services.video.opening_diversity import frame_signature, opening_choice


def _frame(path, *, reverse=False, offset=0):
    image = Image.new("L", (90, 80))
    image.putdata([min(255, max(0, (8 - x // 10 if reverse else x // 10) * 24 + offset))
                   for y in range(80) for x in range(90)])
    image.save(path)
    return str(path)


def test_near_equal_distinct_frame_replaces_repeated_opening(tmp_path):
    first = _frame(tmp_path / "first.png")
    repeated = _frame(tmp_path / "repeated.png", offset=2)
    distinct = _frame(tmp_path / "distinct.png", reverse=True)
    assert (frame_signature(first) ^ frame_signature(repeated)).bit_count() <= 5
    assert (frame_signature(first) ^ frame_signature(distinct)).bit_count() > 5
    best = (SimpleNamespace(preview_path=repeated), .45, .02, .42)
    alternative = (SimpleNamespace(preview_path=distinct), .43, .02, .405)
    assert opening_choice([best, alternative], [first]) == alternative
    assert opening_choice([best, alternative], []) == best
    assert opening_choice([best, (alternative[0], .43, .02, .36)], [first]) == best
    assert opening_choice([best, alternative], ["missing.png"]) == best
