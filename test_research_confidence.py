from backend.services.research.confidence import (
    ResearchConfidenceScorer,
)


scorer = ResearchConfidenceScorer()

topic = "Nepal flood"

high_quality = [
    {
        "title": "Nepal flood death toll rises",
        "publisher": "Reuters",
        "source": "Google News",
        "confidence": 0.9,
        "content": (
            "Rescue teams continue operations after "
            "severe flooding across Nepal."
        ),
    },
    {
        "title": "Nepal flood rescue operation expands",
        "publisher": "BBC",
        "source": "Google News",
        "confidence": 0.9,
        "content": (
            "Emergency crews are searching affected "
            "areas following major floods in Nepal."
        ),
    },
    {
        "title": "Nepal flood causes widespread damage",
        "publisher": "The Hindu",
        "source": "Google News",
        "confidence": 0.8,
        "content": (
            "Officials reported extensive damage while "
            "rescue operations continued."
        ),
    },
    {
        "title": "Nepal flood recovery efforts begin",
        "publisher": "AP",
        "source": "Google News",
        "confidence": 0.9,
        "content": (
            "Authorities have begun recovery work in "
            "communities affected by flooding."
        ),
    },
]

low_quality = [
    {
        "title": "Tourism grows across South Asia",
        "publisher": "Example News",
        "source": "Google News",
        "confidence": 0.8,
        "content": (
            "Tourism activity increased across several "
            "countries during the latest season."
        ),
    },
    {
        "title": "Mountain travel guide released",
        "publisher": "Example News",
        "source": "Google News",
        "confidence": 0.8,
        "content": (
            "A new travel guide covers destinations "
            "and routes throughout the mountains."
        ),
    },
    {
        "title": "Regional transport plans announced",
        "publisher": "Example News",
        "source": "Google News",
        "confidence": 0.8,
        "content": (
            "Officials announced several transport "
            "projects for the region."
        ),
    },
    {
        "title": "Weather outlook published",
        "publisher": "Example News",
        "source": "Google News",
        "confidence": 0.8,
        "content": (
            "Forecasters released a general weather "
            "outlook covering the coming week."
        ),
    },
]


high = scorer.score(
    topic,
    high_quality,
)

low = scorer.score(
    topic,
    low_quality,
)

print("HIGH QUALITY")
print(high)

print()
print("LOW QUALITY")
print(low)

print()
print(
    "SEPARATION:",
    round(
        high["score"] - low["score"],
        2,
    ),
)

assert high["score"] > low["score"]
assert high["relevance"] > low["relevance"]
assert high["diversity"] > low["diversity"]
assert high["score"] >= 75
assert low["score"] <= 60

print()
print(
    "PASS: research confidence distinguishes "
    "relevant independent evidence from weak results."
)
