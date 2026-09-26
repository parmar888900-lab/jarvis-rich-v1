from backend.services.video.media_asset import MediaAsset, media_provenance_identity
from backend.services.pipelines.video_pipeline import VideoPipeline
from backend.services.video_renderer.renderer import VideoRenderer


def test_duplicate_downloads_keep_one_provenance_identity():
    first = MediaAsset(
        asset_id="download-a", asset_type="image", file_path="/tmp/a.jpg",
        source_url="https://commons.wikimedia.org/wiki/File:JWST.jpg",
        source_name="Wikimedia Commons",
    )
    second = MediaAsset(
        asset_id="download-b", asset_type="image", file_path="/tmp/b.jpg",
        source_url="https://commons.wikimedia.org/wiki/File:JWST.jpg",
        source_name="Wikimedia Commons",
    )
    assert media_provenance_identity(first) == media_provenance_identity(second)


def test_distinct_sources_remain_distinct():
    first = {"source_url": "https://example.test/a", "file_path": "/tmp/x.jpg"}
    second = {"source_url": "https://example.test/b", "file_path": "/tmp/x.jpg"}
    assert media_provenance_identity(first) != media_provenance_identity(second)


def test_visual_gate_counts_matched_shots_instead_of_hidden_fallbacks():
    fallback = {
        "source_url": "https://example.test/one-fallback",
        "file_path": "/tmp/fallback.jpg",
    }
    beat_assets = [fallback] * 4
    video_matches = [
        {
            "beat_index": index,
            "clip_id": f"shot-{index}",
            "source_path": "/tmp/nasa.mp4",
            "start_time": float(index * 3),
            "end_time": float(index * 3 + 3),
        }
        for index in range(1, 5)
    ]

    identities = VideoPipeline._final_visual_identities(
        beat_assets=beat_assets,
        video_matches=video_matches,
    )

    assert len(set(identities)) == 4
    assert all(identity.startswith("video::") for identity in identities)


def test_renderer_gate_counts_final_matched_shots_too():
    fallback = {
        "source_url": "https://example.test/one-fallback",
        "file_path": "/tmp/fallback.jpg",
    }
    matches = {
        index: {
            "beat_index": index,
            "clip_id": f"shot-{index}",
            "source_path": "/tmp/nasa.mp4",
            "start_time": float(index * 3),
            "end_time": float(index * 3 + 3),
        }
        for index in range(1, 5)
    }

    identities = VideoRenderer._final_visual_identities(
        beat_images=[fallback] * 4,
        video_lookup=matches,
    )

    assert len(set(identities)) == 4
    assert all(identity.startswith("video::") for identity in identities)
