from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.app import auth, firebase

ADMIN = "admin@example.com"
VISITOR = "visitor@example.com"


def make_request(token: str | None = None) -> Request:
    headers = [(b"authorization", f"Bearer {token}".encode())] if token else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


@pytest.fixture
def admins(monkeypatch):
    monkeypatch.setattr(auth, "ADMIN_EMAILS", {ADMIN})


@pytest.fixture
def no_firebase(monkeypatch):
    monkeypatch.setattr(firebase, "app", lambda: None)
    monkeypatch.setattr(firebase, "error", lambda: "FIREBASE_CREDENTIALS is not set")


@pytest.fixture
def signed_in(monkeypatch):
    from firebase_admin import auth as fb_auth

    tokens: dict[str, dict] = {
        "admin-token": {"uid": "u-admin", "email": ADMIN.upper(), "name": "Owner"},
        "visitor-token": {"uid": "u-visitor", "email": VISITOR, "name": "Visitor"},
    }

    monkeypatch.setattr(firebase, "app", lambda: object())

    def verify(token, app=None, **kwargs):
        if token not in tokens:
            raise ValueError("bad token")
        return tokens[token]

    monkeypatch.setattr(fb_auth, "verify_id_token", verify)


def test_no_token_is_rejected_when_demo_mode_is_off(monkeypatch, no_firebase):
    monkeypatch.setattr(auth, "DEMO_MODE", False)
    with pytest.raises(HTTPException) as raised:
        auth.require_user(make_request())
    assert raised.value.status_code == 401


def test_no_token_is_rejected_when_firebase_is_merely_broken(monkeypatch, no_firebase):
    monkeypatch.setattr(auth, "DEMO_MODE", False)
    with pytest.raises(HTTPException) as raised:
        auth.require_user(make_request("anything"))
    assert raised.value.status_code == 401


def test_demo_mode_is_the_only_route_to_an_anonymous_identity(monkeypatch, no_firebase):
    monkeypatch.setattr(auth, "DEMO_MODE", True)
    user = auth.require_user(make_request())
    assert user.uid == "demo"
    assert user.is_admin is False


def test_admin_never_falls_open_in_demo_mode(monkeypatch, no_firebase):
    monkeypatch.setattr(auth, "DEMO_MODE", True)
    with pytest.raises(HTTPException) as raised:
        auth.require_admin(make_request())
    assert raised.value.status_code == 401


def test_admin_never_falls_open_when_firebase_is_unavailable(monkeypatch, no_firebase, admins):
    monkeypatch.setattr(auth, "DEMO_MODE", False)
    with pytest.raises(HTTPException) as raised:
        auth.require_admin(make_request("admin-token"))
    assert raised.value.status_code == 401


def test_signed_in_non_admin_is_forbidden_from_the_console(signed_in, admins):
    user = auth.require_user(make_request("visitor-token"))
    assert user.uid == "u-visitor"
    with pytest.raises(HTTPException) as raised:
        auth.require_admin(make_request("visitor-token"))
    assert raised.value.status_code == 403


def test_admin_email_matches_case_insensitively(signed_in, admins):
    user = auth.require_admin(make_request("admin-token"))
    assert user.uid == "u-admin"
    assert user.email == ADMIN
    assert user.is_admin is True


def test_unverifiable_token_is_not_a_user(signed_in):
    assert auth.current_user(make_request("forged")) is None


def test_malformed_authorization_header_is_ignored(signed_in):
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"authorization", b"Basic admin-token")],
        }
    )
    assert auth.current_user(request) is None


def test_mode_reports_why_authentication_is_unavailable(monkeypatch, no_firebase):
    monkeypatch.setattr(auth, "DEMO_MODE", False)
    reported = auth.mode()
    assert reported["firebase"] is False
    assert reported["demo_mode"] is False
    assert reported["error"]
