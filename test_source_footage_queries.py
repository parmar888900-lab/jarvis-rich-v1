from backend.services.video.source_footage_resolver import SourceFootageResolver


def test_science_topic_title_is_normalized_for_archive_search():
    queries = SourceFootageResolver._queries(
        format_name="science_explainer",
        topic=(
            "Why the James Webb Telescope's Gold Mirror "
            "Must Unfold in Space"
        ),
    )

    assert queries[0] == (
        "James Webb Space Telescope mirror unfolding"
    )
    assert "James Webb Space Telescope mirror alignment" in queries
    assert "Webb secondary mirror deploy" in queries
    assert "James Webb Space Telescope launch deployment" in queries
    assert len(queries) == len(set(query.lower() for query in queries))


def test_science_hook_strips_leading_nasa_possessive_for_catalogue_search():
    queries = SourceFootageResolver._queries(
        format_name="science_explainer",
        topic="Why NASA's James Webb Space Telescope unfolds in space",
    )

    assert queries[0] == "James Webb Space Telescope unfolding"


def test_non_science_topic_queries_are_preserved():
    queries = SourceFootageResolver._queries(
        format_name="business_wealth",
        topic="How Costco Makes Money",
    )

    assert queries[0] == "How Costco Makes Money"
