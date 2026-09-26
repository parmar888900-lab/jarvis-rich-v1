import asyncio
import json

from backend.services.content_generator import ContentGenerator


RESEARCH = " ".join([
    "In order to do groundbreaking science, NASA's James Webb Space Telescope must first unpack itself in deep space.",
    "In its full configuration, Webb would be too big to fit in any available rocket.",
    "So, engineers designed the observatory to fold up to a much smaller size during transport.",
    "After Webb launches, the observatory's delicate parts will unfold and arrange themselves through a series of carefully choreographed steps.",
    "When deployed, the secondary mirror will sit out in front of Webb's 18 primary mirrors, collect their light and focus it into a beam.",
    "Webb's primary mirror consists of 18 hexagonal mirror segments made of gold-plated beryllium, which together create a 6.5-meter-diameter mirror.",
    "It is the largest telescope in space.",
])


def test_short_grounded_science_draft_recovers_without_overlong_lines():
    draft = {
        "title": "Why Webb unfolds",
        "hashtags": ["#Science", "#Engineering", "#Space"],
        "script_lines": [
            "Webb's giant gold mirror cannot launch at its full size.",
            "The telescope folds inside its rocket before the trip into space.",
            "After launch, its mirror structure opens through a carefully controlled deployment.",
            "Those aligned mirrors collect infrared light from the distant universe.",
        ],
    }

    recovered = ContentGenerator()._recover_generation_length(
        data=draft,
        research=RESEARCH,
    )

    assert recovered is not None
    assert ContentGenerator()._is_valid_content(recovered)
    assert 75 <= ContentGenerator()._word_count(recovered) <= 110
    assert all(len(line.split()) <= 29 for line in recovered["script_lines"])
    assert recovered["script_lines"][0].startswith(draft["script_lines"][0])


def test_grounded_length_recovery_fails_closed_for_off_topic_material():
    draft = {
        "title": "Why Webb unfolds",
        "hashtags": ["#Science", "#Engineering", "#Space"],
        "script_lines": ["Webb mirror unfolds in space."] * 4,
    }
    unrelated = (
        "A chef prepared vegetables in a restaurant kitchen. "
        "The recipe used bread, herbs, and olive oil for dinner."
    )

    assert ContentGenerator()._recover_generation_length(
        data=draft,
        research=unrelated,
    ) is None


def test_main_path_recovers_first_short_draft_without_second_llm_call():
    class ShortDraftLLM:
        def __init__(self):
            self.calls = 0

        async def chat(self, *args, **kwargs):
            self.calls += 1
            return json.dumps({
                "title": "Why Webb unfolds",
                "hashtags": ["#Science", "#Engineering", "#Space"],
                "script_lines": [
                    "Webb's giant gold mirror cannot launch at its full size.",
                    "The telescope folds inside its rocket before the trip into space.",
                    "After launch, its mirror structure opens through a carefully controlled deployment.",
                    "Those aligned mirrors collect infrared light from the distant universe.",
                ],
            })

    generator = ContentGenerator()
    fake = ShortDraftLLM()
    generator.llm = fake

    result = asyncio.run(generator.generate({
        "title": "Why Webb's mirror must unfold",
        "research": RESEARCH,
        "content_format": {"format_name": "visual_explainer"},
    }))

    assert fake.calls == 1
    assert 75 <= sum(len(line.split()) for line in result.script_lines) <= 110
    assert all(len(line.split()) <= 29 for line in result.script_lines)


def test_recovery_repairs_typo_and_does_not_repeat_launch_fit_premise():
    draft = {
        "title": "Why Webb unfolds",
        "hashtags": ["#Science", "#Engineering", "#Space"],
        "script_lines": [
            "Webb's gold mirror is wider than any launch rocket can carry.",
            "NASA built its eighteen segments to fold for launch.",
            "After separation, motors and hinges deploy the observatory.",
            "Alignment lets Webb collect infrared light from deep space.",
        ],
    }
    research_with_typo = RESEARCH.replace("too big to fit", "too big too fit")

    recovered = ContentGenerator()._recover_generation_length(
        data=draft,
        research=research_with_typo,
    )

    assert recovered is not None
    script = " ".join(recovered["script_lines"]).lower()
    assert "too big too fit" not in script
    assert "in its full configuration" not in script
    assert "administrator of nasa" not in script
    assert script.count("hexagonal mirror segments") <= 1
    assert ContentGenerator._recovery_tokens("eighteen") == (
        ContentGenerator._recovery_tokens("18")
    )
