"""Offline regression tests. Evidence below is synthetic, not film research."""
import asyncio
import json

import pytest

from backend.services.content_generator import ContentGenerator
from backend.services.intelligence.movie_script_recovery import recover_movie_script
from backend.services.intelligence.semantic_claim_evidence_validator import SemanticClaimEvidenceValidator

FACTS = [
    "The workshop sequence shows the inventor assembling metal components by hand while another character monitors the equipment beside the crowded workbench inside.",
    "The practical costume used separate metal panels around the shoulders and chest, allowing the performer to move during the workshop sequence on set.",
    "The lighting team placed small lamps beside the workbench to illuminate the metal components while leaving the background of the workshop in shadow.",
    "The final escape sequence returns to the metal components established earlier, connecting the assembly process with the finished costume seen outside the workshop.",
]
RESEARCH = "\n\n".join(f"[E{i}] {s}" for i, s in enumerate(FACTS, 1))


def candidate(lines=None):
    return {"title": "The workshop", "hashtags": ["#film", "#craft", "#movies"],
            "script_lines": FACTS[:] if lines is None else lines,
            "evidence_ids": [[f"E{i}"] for i in range(1, 5)]}


@pytest.mark.parametrize("lines", [["Too short."] * 4, ["Overlong " * 40] * 4,
                                   ["Wrong structure."], [], None])
def test_recovery_handles_invalid_lengths_and_shapes_without_llm(lines):
    data = candidate(lines or [])
    before = json.dumps(data)
    result = recover_movie_script(data, topic="workshop metal costume", research=RESEARCH)
    assert result is not None
    assert len(result["script_lines"]) == 4
    assert 75 <= sum(len(x.split()) for x in result["script_lines"]) <= 110
    assert all(len(x.split()) <= 29 for x in result["script_lines"])
    for text, ids in zip(result["script_lines"], result["evidence_ids"]):
        assert text in FACTS
        assert ids == [f"E{FACTS.index(text) + 1}"]
    assert json.dumps(data) == before


def test_valid_creative_order_is_preserved():
    data = candidate()
    assert recover_movie_script(data, topic="workshop", research=RESEARCH) == data


@pytest.mark.parametrize("research", ["", "Unlabelled prose is not a cited evidence packet.",
                                       "[E1] A tiny fact.", '[E1] {"url": "https://example.com"}'])
def test_insufficient_evidence_fails_closed(research):
    assert recover_movie_script({}, topic="movie", research=research) is None


def test_invented_ids_are_replaced_only_with_actual_source_ids():
    data = candidate()
    data["evidence_ids"] = [["E999"]] * 4
    result = recover_movie_script(data, topic="workshop", research=RESEARCH)
    assert result and all("E999" not in row for row in result["evidence_ids"])


def test_main_path_retains_semantic_gate_after_deterministic_recovery():
    class FakeLLM:
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return json.dumps(candidate(["Too short."] * 4))
            return json.dumps({"valid": True, "issues": [], "line_results": [
                {"line": i, "supported": True, "unsupported_claims": []} for i in range(1, 5)]})

    generator = ContentGenerator()
    llm = FakeLLM()
    generator.llm = llm
    generator.semantic_claim_evidence_validator = SemanticClaimEvidenceValidator(llm=llm)
    result = asyncio.run(generator.generate({"title": "Workshop costume", "research": RESEARCH,
        "content_format": {"format_name": "famous_movie_commentary"}}))
    assert len(result.script_lines) == 4
    assert llm.calls == 2  # creative generation + semantic validation; zero length repair calls


def test_main_path_does_not_accept_semantically_rejected_recovery():
    class Reject:
        async def validate(self, **kwargs):
            from backend.services.intelligence.semantic_claim_evidence_validator import SemanticClaimEvidenceResult
            return SemanticClaimEvidenceResult(False, ["unsupported"], [
                {"line": i, "supported": False, "unsupported_claims": ["unsupported"]} for i in range(1, 5)])
    class LLM:
        async def chat(self, *args, **kwargs):
            return json.dumps(candidate())
    g = ContentGenerator()
    g.llm = LLM()
    g.semantic_claim_evidence_validator = Reject()
    with pytest.raises(RuntimeError, match="semantic"):
        asyncio.run(g.generate({"title": "Workshop", "research": RESEARCH,
            "content_format": {"format_name": "famous_movie_commentary"}}))
