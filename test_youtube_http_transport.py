from fastapi.testclient import TestClient

from backend.app import app
from backend.database import get_db
import backend.routes.commander as commander_route


class FakeDB:
    pass


async def override_get_db():
    yield FakeDB()


class CaptureCommander:
    def __init__(self):
        self.calls = 0
        self.received_payload = None
        self.received_db = None

    async def receive(self, db, payload):
        self.calls += 1
        self.received_db = db
        self.received_payload = payload

        return {
            "status": "accepted",
            "command_id": "http-test-001",
        }


fake_commander = CaptureCommander()

original_commander = commander_route.commander

app.dependency_overrides[get_db] = override_get_db
commander_route.commander = fake_commander

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

try:
    with TestClient(app) as client:
        response = client.post(
            "/command",
            json=payload,
        )

    assert response.status_code == 200

    body = response.json()

    assert body == {
        "status": "accepted",
        "command_id": "http-test-001",
    }

    assert fake_commander.calls == 1

    request = fake_commander.received_payload

    assert request.agent == "youtube"
    assert request.task == "create_video"

    trend = request.parameters["trend"]

    assert trend == payload["parameters"]["trend"]

    assert trend["knowledge"]["score"] == 90

    assert (
        trend["knowledge"]["sources"][1]["source"]
        == "Publisher B"
    )

    assert (
        trend["production_selection"]
        ["production_score"]
        == 85.15
    )

    print("=" * 70)
    print("REAL HTTP /command TRANSPORT TEST")
    print()
    print("HTTP STATUS:", response.status_code)
    print("COMMANDER CALLS:", fake_commander.calls)
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
        "PASS: POST /command preserves the "
        "complete nested create_video trend payload."
    )

finally:
    commander_route.commander = original_commander
    app.dependency_overrides.clear()
