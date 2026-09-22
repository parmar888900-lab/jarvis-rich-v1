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


def test_context_safe_visual_preserves_vertical_output_canvas():
    renderer = VideoRenderer()
    source = ColorClip(size=(1920, 1080), color=(30, 90, 160), duration=1.0)
    clip = renderer._fit_context_safe_visual(source, duration=1.0)

    try:
        assert clip.size == (renderer.WIDTH, renderer.HEIGHT)
        assert clip.duration == 1.0
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


def test_window_can_include_decode_timebase_padding():
    start, end = VideoRenderer._expand_source_window(
        start_time=10.0,
        end_time=12.0,
        source_duration=30.0,
        required_duration=2.80,
    )

    assert start == 10.0
    assert end == 12.8


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


def test_dense_single_source_matches_fill_isolated_gaps():
    matches = {
        index: {"beat_index": index, "source_path": "nasa.mp4"}
        for index in range(1, 9)
        if index not in {4, 7}
    }

    filled = VideoRenderer._fill_authoritative_video_gaps(
        matches,
        total_beats=8,
    )

    assert set(filled) == set(range(1, 9))
    assert filled[4]["match_mode"] == "authoritative_continuity_fill"
    assert filled[7]["source_path"] == "nasa.mp4"


def test_sparse_matches_do_not_fill_gaps():
    matches = {
        1: {"beat_index": 1, "source_path": "source.mp4"},
        4: {"beat_index": 4, "source_path": "source.mp4"},
    }

    assert VideoRenderer._fill_authoritative_video_gaps(
        matches,
        total_beats=8,
    ) == matches


def test_mixed_sources_do_not_fill_gaps():
    matches = {
        index: {
            "beat_index": index,
            "source_path": "a.mp4" if index < 5 else "b.mp4",
        }
        for index in range(1, 9)
        if index != 4
    }

    assert 4 not in VideoRenderer._fill_authoritative_video_gaps(
        matches,
        total_beats=8,
    )
