"""Commander system tests."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_submit_command_success(client):
    response = await client.post(
        "/command",
        json={"agent": "youtube", "task": "create_video"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert "command_id" in data


@pytest.mark.asyncio
async def test_submit_command_unknown_agent(client):
    response = await client.post(
        "/command",
        json={"agent": "nonexistent", "task": "do_something"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "agent_not_found"


@pytest.mark.asyncio
async def test_submit_command_unsupported_task(client):
    response = await client.post(
        "/command",
        json={"agent": "youtube", "task": "fly_to_moon"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "task_not_supported"


@pytest.mark.asyncio
async def test_get_command_status(client):
    submit = await client.post(
        "/command",
        json={"agent": "youtube", "task": "upload_video"},
    )
    command_id = submit.json()["command_id"]

    status = await client.get(f"/command/{command_id}")
    assert status.status_code == 200
    data = status.json()
    assert data["id"] == command_id
    assert data["agent"] == "youtube"
    assert data["task"] == "upload_video"
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_get_command_not_found(client):
    response = await client.get("/command/does-not-exist")
    assert response.status_code == 404
