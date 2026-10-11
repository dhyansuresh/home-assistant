from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.parametrize("mode", ["stationary_voice", "mobile_capture"])
def test_create_task_session(mode: str) -> None:
    response = client.post(
        "/api/v1/task-sessions",
        json={"mode": mode},
    )

    assert response.status_code == 201

    body = response.json()
    UUID(body["session_id"])
    assert body["mode"] == mode
    assert body["state"] == "collecting"
    assert body["revision"] == 0
    assert body["expires_at"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"mode": "camera"},
        {"mode": "stationary_voice", "unexpected": True},
    ],
)
def test_create_task_session_rejects_invalid_body(body: dict[str, object]) -> None:
    response = client.post("/api/v1/task-sessions", json=body)

    assert response.status_code == 422
