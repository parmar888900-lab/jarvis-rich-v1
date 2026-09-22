from backend.services.video_renderer.subtitle_renderer import SubtitleRenderer


def test_short_caption_has_benchmark_scale_and_safe_width():
    renderer = SubtitleRenderer()
    clip = renderer.create_clip(
        text="mirror unfolds",
        start_time=0.0,
        end_time=1.0,
    )

    try:
        assert renderer.FONT_SIZE >= 96
        assert renderer.STROKE_WIDTH >= 7
        assert clip.w <= renderer.WIDTH
        assert clip.h > 60
    finally:
        clip.close()
