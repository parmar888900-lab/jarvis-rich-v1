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
