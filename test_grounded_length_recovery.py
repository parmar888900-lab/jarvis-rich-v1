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
