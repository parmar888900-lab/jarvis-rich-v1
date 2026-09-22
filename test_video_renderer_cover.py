from PIL import Image
from moviepy import ColorClip

from backend.services.video_renderer.renderer import VideoRenderer


def test_cover_image_clip_is_cropped_to_output_canvas(tmp_path):
    image_path = tmp_path / "landscape.jpg"
    Image.new("RGB", (1920, 1080), (180, 120, 40)).save(image_path)

    renderer = VideoRenderer()
    clip = renderer._cover_image_clip(image_path, duration=1.0)

    try:
        assert clip.size == (renderer.WIDTH, renderer.HEIGHT)
    finally:
        clip.close()


def test_fit_visual_is_cropped_to_output_canvas():
    renderer = VideoRenderer()
    source = ColorClip(size=(1920, 1080), color=(30, 90, 160), duration=1.0)
    clip = renderer._fit_visual(source, duration=1.0)

    try:
        assert clip.size == (renderer.WIDTH, renderer.HEIGHT)
    finally:
        clip.close()
        source.close()


def test_short_match_extends_forward_to_fill_beat():
    start, end = VideoRenderer._expand_source_window(
        start_time=10.0,
        end_time=12.0,
        source_duration=30.0,
        required_duration=2.75,
    )

    assert start == 10.0
    assert end == 12.75


def test_match_near_source_end_backfills_required_duration():
    start, end = VideoRenderer._expand_source_window(
        start_time=28.0,
        end_time=30.0,
        source_duration=30.0,
        required_duration=3.0,
    )

    assert start == 27.0
    assert end == 30.0


def test_too_short_source_window_remains_bounded():
    start, end = VideoRenderer._expand_source_window(
        start_time=0.25,
        end_time=1.0,
        source_duration=1.0,
        required_duration=2.5,
    )

    assert start == 0.0
    assert end == 1.0
