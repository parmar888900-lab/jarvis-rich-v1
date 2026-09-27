from pathlib import Path
import shutil

import pytest

from scripts.refinish_audio import checked_stage, file_hash, refinish


def test_parent_checksum_and_narration_contract_fail_closed(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"not-a-render")
    args = dict(source=source, expected_sha256="0" * 64,
                output=tmp_path / "next.mp4", cue_times=[0.0])
    with pytest.raises(ValueError, match="narration-only"):
        refinish(**args, narration_only_confirmed=False)
    with pytest.raises(ValueError, match="checksum"):
        refinish(**args, narration_only_confirmed=True)
    assert not args["output"].exists()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="Real FFmpeg integration requires FFmpeg")
def test_audio_resume_preserves_video_packets_and_provenance(tmp_path):
    source = tmp_path / "parent.mp4"
    checked_stage(["ffmpeg", "-v", "error", "-nostdin", "-n", "-f", "lavfi",
                   "-i", "testsrc2=size=160x284:rate=30:duration=1",
                   "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=1",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)],
                  "integration-parent", 20, tmp_path / "parent.log")
    output = tmp_path / "finished.mp4"
    result = refinish(source=source, expected_sha256=file_hash(source), output=output,
                      cue_times=[0, 0.4, 0.8], narration_only_confirmed=True)
    assert result["video_packets_unchanged"] is True
    assert result["public_release"] is False
    assert result["quality_gate"] == "PENDING_REAL_RENDER_INSPECTION"
    assert result["sound_design"]["commercial_use_allowed"] is True
    assert result["output_sha256"] == file_hash(output)
    assert Path(result["sound_design"]["audio_path"]).exists()
    with pytest.raises(ValueError, match="never overwritten"):
        refinish(source=source, expected_sha256=file_hash(source), output=output,
                 cue_times=[0], narration_only_confirmed=True)
