import os

from fastapi.testclient import TestClient
from shared.config import ROOM_IDS


os.environ["EMBEDDED_SENSOR"] = "0"

from backend.app import app  # noqa: E402
from backend.app import list_rooms  # noqa: E402


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


def test_list_rooms_function_returns_configured_ids() -> None:
    rooms = list_rooms()
    assert isinstance(rooms, list)
    assert rooms == ROOM_IDS
