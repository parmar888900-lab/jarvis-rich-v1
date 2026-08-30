from backend.services.intelligence.scorer import TrendScorer


scorer = TrendScorer()


def show(name, trend):
    score = scorer.score(trend)
    print(f"{name}: {score}")
    return score


print("=== PROVIDER SCALE TEST ===")

youtube_huge = show(
    "YouTube huge raw score",
    {
        "title": "Topic A",
        "source": "YouTube",
        "score": 553,
        "views": 5_000_000,
        "likes": 200_000,
    },
)

youtube_medium = show(
    "YouTube medium raw score",
    {
        "title": "Topic B",
        "source": "YouTube",
        "score": 102,
        "views": 800_000,
        "likes": 40_000,
    },
)

news_high = show(
    "News high raw score",
    {
        "title": "Topic C",
        "source": "Google News RSS",
        "score": 80,
    },
)

news_lower = show(
    "News lower raw score",
    {
        "title": "Topic D",
        "source": "Google News RSS",
        "score": 72,
    },
)

print()
print("=== RESEARCH TEST ===")

without_research = show(
    "Without research",
    {
        "title": "Research Topic",
        "source": "Google News RSS",
        "score": 75,
    },
)

with_research = show(
    "With research",
    {
        "title": "Research Topic",
        "source": "Google News RSS",
        "score": 75,
        "knowledge": {
            "facts": [
                "Fact one",
                "Fact two",
                "Fact three",
            ],
            "sources": [
                {"source": "A"},
                {"source": "B"},
                {"source": "C"},
            ],
        },
    },
)

print()
print("=== CURRENT BEHAVIOR ===")
print(
    "YouTube raw-score separation:",
    youtube_huge - youtube_medium,
)
print(
    "News raw-score separation:",
    news_high - news_lower,
)
print(
    "Research bonus:",
    with_research - without_research,
)
