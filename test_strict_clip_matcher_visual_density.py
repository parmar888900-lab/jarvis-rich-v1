from PIL import Image, ImageDraw

from backend.services.video.strict_clip_matcher import StrictClipMatcher


def test_rejects_near_empty_documentary_title_card(tmp_path):
    path = tmp_path / "title-card.jpg"
    image = Image.new("RGB", (640, 360), "black")
    draw = ImageDraw.Draw(image)
    draw.rectangle((270, 40, 370, 320), fill=(38, 38, 38))
    image.save(path)

    assert not StrictClipMatcher._preview_has_usable_visual_density(
        str(path)
    )


def test_accepts_visually_dense_source_frame(tmp_path):
    path = tmp_path / "usable-frame.jpg"
    image = Image.new("RGB", (640, 360), (120, 95, 55))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 600, 320), fill=(220, 175, 60))
    image.save(path)

    assert StrictClipMatcher._preview_has_usable_visual_density(
        str(path)
    )


def test_rejects_missing_preview():
    assert not StrictClipMatcher._preview_has_usable_visual_density(
        "missing-preview.jpg"
    )
