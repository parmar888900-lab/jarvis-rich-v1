from backend.models.command import CommandSubmitRequest


payload = {
    "agent": "youtube",
    "task": "create_video",
    "priority": "normal",
    "parameters": {
        "trend": {
            "title": (
                "Why researchers discovered "
                "a major new technology"
            ),
            "source": "Google News RSS",
            "final_score": 80,
            "knowledge": {
                "score": 90,
                "summary": "Research summary.",
                "facts": [
                    "Fact one.",
                    "Fact two.",
                ],
                "sources": [
                    {
                        "source": "Publisher A",
                        "url": "https://example.com/a",
                    },
                    {
                        "source": "Publisher B",
                        "url": "https://example.com/b",
                    },
                ],
            },
            "production_selection": {
                "eligible": True,
                "selected": True,
                "production_score": 85.15,
            },
        }
    },
}


request = CommandSubmitRequest.model_validate(
    payload
)

trend = request.parameters["trend"]

assert request.agent == "youtube"
assert request.task == "create_video"

assert trend["title"] == (
    "Why researchers discovered "
    "a major new technology"
)

assert trend["knowledge"]["score"] == 90

assert (
    trend["knowledge"]["sources"][1]
    ["source"]
    == "Publisher B"
)

assert (
    trend["production_selection"]
    ["production_score"]
    == 85.15
)

serialized = request.model_dump(
    mode="json"
)

assert (
    serialized["parameters"]["trend"]
    == payload["parameters"]["trend"]
)

print("=" * 70)
print("COMMAND REQUEST MODEL TEST")
print()
print("AGENT:", request.agent)
print("TASK:", request.task)
print("TITLE:", trend["title"])
print(
    "RESEARCH CONFIDENCE:",
    trend["knowledge"]["score"],
)
print(
    "PRODUCTION SCORE:",
    trend[
        "production_selection"
    ]["production_score"],
)
print()
print(
    "PASS: CommandSubmitRequest preserves "
    "the complete nested trend payload."
)
