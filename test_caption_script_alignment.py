import asyncio

import pytest

from backend.services.video.caption_aligner import CaptionAligner, CaptionAlignmentError


def timed(text, gap=0.04):
    return [{"text": word, "start_time": i * (0.25 + gap),
             "end_time": i * (0.25 + gap) + 0.25}
            for i, word in enumerate(text.split())]


def assert_grounded_and_bounded(script, observed, words):
    assert " ".join(word["text"] for word in words) == script
    assert words[0]["start_time"] >= observed[0]["start_time"]
    assert words[-1]["end_time"] <= observed[-1]["end_time"] + 1e-8
    assert all(word["start_time"] < word["end_time"] for word in words)
    assert all(a["end_time"] <= b["start_time"] for a, b in zip(words, words[1:]))


def test_webb_captions_retain_grounded_terms_and_numbers():
    script = ("NASA built its eighteen hexagonal mirror segments and tennis-court sunshield to fold for launch. "
              "This gives Webb a light-collecting area of about 25 m2 (270 sq ft).")
    observed = timed("NASA built its 18 hexagonal mirror segments and escorts sunshield to fold for launch. "
                     "This gives Webb a light collecting area of about twenty five square meters two hundred and seventy square feet.")
    words = CaptionAligner.align_script_words(script, observed)
    assert_grounded_and_bounded(script, observed, words)
    assert "escorts" not in [word["text"] for word in words]
    assert words[8]["text"] == "tennis-court"


def test_inserted_asr_claim_is_never_captioned():
    script = "Webb unfolds its mirror in space before collecting infrared light."
    observed = timed("Webb unfolds its very expensive mirror in space before collecting infrared light.")
    words = CaptionAligner.align_script_words(script, observed)
    assert_grounded_and_bounded(script, observed, words)
    assert "expensive" not in " ".join(word["text"] for word in words)


@pytest.mark.parametrize("gap", [0.0, 0.12])
def test_deleted_asr_word_uses_only_local_timing(gap):
    script = "Webb unfolds its giant mirror in space before collecting infrared light."
    observed = timed("Webb unfolds its mirror in space before collecting infrared light.", gap)
    words = CaptionAligner.align_script_words(script, observed)
    assert_grounded_and_bounded(script, observed, words)
    assert words[-1]["start_time"] == observed[-1]["start_time"]


def test_contractions_hyphenation_and_pause_are_preserved():
    script = "It's a light-collecting mirror. Engineers can't skip alignment."
    observed = timed("It is a light collecting mirror. Engineers can not skip alignment.")
    for word in observed[6:]:
        word["start_time"] += 0.8
        word["end_time"] += 0.8
    words = CaptionAligner.align_script_words(script, observed)
    assert_grounded_and_bounded(script, observed, words)
    assert words[4]["start_time"] - words[3]["end_time"] >= 0.8
    phrases = CaptionAligner()._group_phrases(words)
    assert not any("mirror. Engineers" in phrase["text"] for phrase in phrases)


def test_unrelated_transcript_fails_closed():
    with pytest.raises(CaptionAlignmentError, match="agreement"):
        CaptionAligner.align_script_words(
            "Webb unfolds its mirror in space before collecting infrared light.",
            timed("The bank opened another downtown branch before closing its restaurant."))


def test_long_missing_passage_fails_closed_despite_global_overlap():
    script = " ".join(["mirror"] * 40 + ["missing"] * 12 + ["sunshield"] * 40)
    with pytest.raises(CaptionAlignmentError, match="too long"):
        CaptionAligner.align_script_words(script, timed(" ".join(["mirror"] * 40 + ["sunshield"] * 40)))


@pytest.mark.parametrize("timestamp", [-1.0, float("nan"), float("inf")])
def test_invalid_timing_fails_closed(timestamp):
    observed = timed("Webb unfolds its mirror.")
    observed[0]["start_time"] = timestamp
    with pytest.raises(CaptionAlignmentError, match="timestamps"):
        CaptionAligner.align_script_words("Webb unfolds its mirror.", observed)


def test_async_api_uses_script_wording_without_loading_model(monkeypatch):
    aligner = CaptionAligner()
    script = "Webb uses eighteen segments in its golden mirror."

    async def cached_align(audio_path):
        assert audio_path == "cached.wav"
        return timed("Webb uses 18 segments in its golden mirror.")

    monkeypatch.setattr(aligner, "align", cached_align)
    phrases = asyncio.run(aligner.align_script_phrases("cached.wav", script))
    assert " ".join(phrase["text"] for phrase in phrases) == script
