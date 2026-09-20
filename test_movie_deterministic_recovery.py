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
    result = recover_movie_script(data, topic="workshop metal costume components", research=RESEARCH)
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
    assert recover_movie_script(data, topic="workshop metal components", research=RESEARCH) == data


@pytest.mark.parametrize("research", ["", "Unlabelled prose is not a cited evidence packet.",
                                       "[E1] A tiny fact.", '[E1] {"url": "https://example.com"}'])
def test_insufficient_evidence_fails_closed(research):
    assert recover_movie_script({}, topic="movie", research=research) is None


def test_invented_ids_are_replaced_only_with_actual_source_ids():
    data = candidate()
    data["evidence_ids"] = [["E999"]] * 4
    result = recover_movie_script(data, topic="workshop metal components", research=RESEARCH)
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
    result = asyncio.run(generator.generate({"title": "Workshop metal components", "research": RESEARCH,
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
        asyncio.run(g.generate({"title": "Workshop metal components", "research": RESEARCH,
            "content_format": {"format_name": "famous_movie_commentary"}}))


def test_first_suit_vocabulary_recovers_without_other_armor_drift():
    facts = [
        "Stark and Yinsen secretly build an arc reactor and construct a prototype armored suit from salvaged materials to aid in their escape from captivity.",
        "Yinsen helps Tony Stark build the first Iron Man suit while they are held captive in a cave surrounded by the group's weapons.",
        "Stan Winston and his company built separate metal and rubber versions of the armor so the production could photograph different physical requirements.",
        "The Embassy created a digital version of the Mark I armor for additional visual effects work used alongside the physical armor versions.",
    ]
    research = "\n\n".join(f"[E{i}] {fact}" for i, fact in enumerate(facts, 1))
    result = recover_movie_script(
        {"title": "First suit", "hashtags": ["#film", "#movies", "#craft"],
         "script_lines": ["Too short."] * 4,
         "evidence_ids": [[f"E{i}"] for i in range(1, 5)]},
        topic="Why Iron Man's first suit-building scene became iconic",
        research=research,
    )
    assert result is not None
    assert 75 <= sum(len(line.split()) for line in result["script_lines"]) <= 110


def test_first_suit_angle_rejects_other_armor_only_packet():
    research = "\n\n".join([
        "[E1] Stan Winston built the Iron Monger armor for the film's final battle sequence.",
        "[E2] War Machine used a separate armored suit with mounted weapons in a later film.",
        "[E3] The Mark III armor used a red and gold finish after Stark returned home.",
        "[E4] The Mark IV suit appeared after the cave escape had already ended.",
    ])
    assert recover_movie_script(
        {}, topic="Why Iron Man's first suit-building scene became iconic", research=research,
    ) is None
