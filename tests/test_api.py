from __future__ import annotations

import io
import struct
import zlib

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import auth, firebase
from backend.app.auth import User, require_user
from backend.app.main import app

PROTECTED = [
    ("post", "/predict"),
    ("post", "/explain"),
    ("post", "/ask"),
    ("post", "/feedback"),
    ("get", "/history"),
    ("delete", "/history"),
]

ADMIN_ONLY = [("get", "/stats"), ("get", "/analytics")]


@pytest.fixture(autouse=True)
def closed_firebase(monkeypatch):
    monkeypatch.setattr(firebase, "app", lambda: None)
    monkeypatch.setattr(firebase, "error", lambda: "FIREBASE_CREDENTIALS is not set")
    monkeypatch.setattr(auth, "DEMO_MODE", False)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def signed_in_client(client):
    app.dependency_overrides[require_user] = lambda: User(
        uid="u-test", email="visitor@example.com", name="Visitor", picture=None
    )
    yield client
    app.dependency_overrides.clear()


def png_bytes(width: int = 32, height: int = 32) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, format="PNG")
    return buffer.getvalue()


def bomb_bytes(side: int = 30_000) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\x00" * 32))
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize("method,path", PROTECTED + ADMIN_ONLY)
def test_every_protected_route_answers_401_without_a_verified_caller(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401, f"{method.upper()} {path} was not closed"


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_the_console_is_not_opened_by_a_user_level_session(signed_in_client, method, path):
    assert getattr(signed_in_client, method)(path).status_code == 401


@pytest.mark.parametrize("path", ["/health", "/classes", "/model"])
def test_public_routes_stay_public(client, path):
    assert client.get(path).status_code == 200


def test_health_reports_the_authentication_and_storage_posture(client):
    body = client.get("/health").json()
    assert body["auth"] == {
        "firebase": False,
        "demo_mode": False,
        "error": "FIREBASE_CREDENTIALS is not set",
    }
    assert "connected" in body["store"]
    assert "failed_writes" in body["store"]


def test_the_class_list_is_the_full_food_101_taxonomy(client):
    body = client.get("/classes").json()
    assert body["count"] == 101
    assert len(set(body["classes"])) == 101


def test_demo_mode_opens_the_user_routes_but_not_the_console(client, monkeypatch):
    monkeypatch.setattr(auth, "DEMO_MODE", True)
    assert client.get("/history").status_code == 200
    assert client.get("/stats").status_code == 401
    assert client.get("/analytics").status_code == 401


def test_an_unknown_food_class_is_rejected_by_ask(signed_in_client):
    response = signed_in_client.post(
        "/ask", json={"question": "How much sodium?", "food_class": "spaghetti_carbonara_deluxe"}
    )
    assert response.status_code == 400
    assert "Unknown food class" in response.json()["detail"]


def test_an_empty_question_is_rejected_before_retrieval(signed_in_client):
    assert signed_in_client.post("/ask", json={"question": "?"}).status_code == 422


def test_an_overlong_question_is_rejected_before_retrieval(signed_in_client):
    response = signed_in_client.post("/ask", json={"question": "a" * 401})
    assert response.status_code == 422


def test_feedback_must_name_a_known_dish(signed_in_client):
    response = signed_in_client.post(
        "/feedback", json={"food_class": "not_a_dish", "helpful": True}
    )
    assert response.status_code == 400


def test_feedback_requires_a_verdict(signed_in_client):
    assert signed_in_client.post("/feedback", json={"food_class": "pizza"}).status_code == 422


def test_a_file_that_is_not_an_image_never_reaches_the_model(signed_in_client):
    response = signed_in_client.post(
        "/predict", files={"image": ("dinner.txt", b"not an image", "text/plain")}
    )
    assert response.status_code == 415


def test_a_decompression_bomb_never_reaches_the_model(signed_in_client):
    response = signed_in_client.post(
        "/predict", files={"image": ("bomb.png", bomb_bytes(), "image/png")}
    )
    assert response.status_code == 413


def test_explain_applies_the_same_image_gate(signed_in_client):
    response = signed_in_client.post(
        "/explain", files={"image": ("bomb.png", bomb_bytes(), "image/png")}
    )
    assert response.status_code == 413


def test_predict_requires_a_file_at_all(signed_in_client):
    assert signed_in_client.post("/predict").status_code == 422


def test_history_is_scoped_to_the_caller(signed_in_client, monkeypatch):
    from backend.app.main import STORE

    asked: list[tuple] = []
    monkeypatch.setattr(
        STORE, "history", lambda session, limit=40: asked.append((session, limit)) or {}
    )
    signed_in_client.get("/history?limit=500")
    assert asked == [("u-test", 100)]


def test_erasing_history_is_scoped_to_the_caller(signed_in_client, monkeypatch):
    from backend.app.main import STORE

    erased: list[str] = []
    monkeypatch.setattr(STORE, "erase", lambda session: erased.append(session) or {})
    signed_in_client.delete("/history")
    assert erased == ["u-test"]


def test_me_reports_a_signed_out_caller_without_inventing_one(client):
    assert client.get("/me").json() == {"signed_in": False, "user": None}
