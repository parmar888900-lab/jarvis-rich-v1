from backend.services.video.media_asset import MediaAsset, media_provenance_identity


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
