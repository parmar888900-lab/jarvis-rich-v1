from backend.services.content_generator import ContentGenerator


def test_script_key_drift_is_normalized_without_rewriting_lines():
    lines = [
        "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen",
        "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen",
        "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen",
        "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen",
    ]
    normalized = ContentGenerator._normalize_response_schema(
        {"script": lines, "word_count": 76},
        topic="A grounded science topic",
    )

    assert normalized["script_lines"] == lines
    assert normalized["title"] == "A grounded science topic"
    assert normalized["hashtags"] == [
        "#Science",
        "#Engineering",
        "#Shorts",
    ]
    assert ContentGenerator()._is_valid_content(normalized)


def test_overlong_narration_line_is_rejected_even_when_total_is_valid():
    lines = [
        "word " * 30,
        "word " * 15,
        "word " * 15,
        "word " * 15,
    ]
    data = {
        "title": "Test",
        "hashtags": ["#one", "#two", "#three"],
        "script_lines": lines,
    }

    assert ContentGenerator()._is_valid_content(data) is False
