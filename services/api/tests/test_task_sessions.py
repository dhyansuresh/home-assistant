from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app, task_session_store
from app.schemas import TaskSessionMode
from app.task_sessions import TaskSessionStore

client = TestClient(app)


@pytest.mark.parametrize("mode", ["stationary_voice", "mobile_capture"])
def test_create_task_session(mode: str) -> None:
    response = client.post(
        "/api/v1/task-sessions",
        json={"mode": mode},
    )

    assert response.status_code == 201

    body = response.json()
    session_id = UUID(body["session_id"])
    stored = task_session_store.get(session_id)

    assert stored is not None
    assert stored.session_id == session_id
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


def test_task_session_store_remembers_created_session() -> None:
    store = TaskSessionStore()

    created = store.create(TaskSessionMode.MOBILE_CAPTURE)
    retrieved = store.get(created.session_id)

    assert retrieved == created


def test_task_session_store_returns_none_for_unknown_session() -> None:
    store = TaskSessionStore()

    retrieved = store.get(uuid4())

    assert retrieved is None
