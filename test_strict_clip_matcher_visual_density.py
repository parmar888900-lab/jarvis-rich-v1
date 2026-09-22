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


def test_edge_annotations_trigger_context_safe_presentation():
    tsv = "\n".join([
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
        "5\t1\t1\t1\t1\t1\t20\t12\t80\t20\t92\tMIRROR",
        "5\t1\t1\t1\t1\t2\t110\t12\t90\t20\t88\tDEPLOYMENT",
    ])

    assert StrictClipMatcher._annotation_risk_from_tsv(
        tsv,
        width=640,
        height=360,
    )


def test_center_label_does_not_trigger_context_safe_presentation():
    tsv = "\n".join([
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
        "5\t1\t1\t1\t1\t1\t220\t165\t80\t20\t92\tPRIMARY",
        "5\t1\t1\t1\t1\t2\t310\t165\t70\t20\t88\tMIRROR",
    ])

    assert not StrictClipMatcher._annotation_risk_from_tsv(
        tsv,
        width=640,
        height=360,
    )
