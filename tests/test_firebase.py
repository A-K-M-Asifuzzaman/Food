from __future__ import annotations

import json

import pytest

from backend.app import firebase


@pytest.fixture(autouse=True)
def unconfigured(monkeypatch):
    for name in firebase.INLINE_VARS + firebase.PATH_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(firebase, "_app", None)
    monkeypatch.setattr(firebase, "_attempted", False)
    monkeypatch.setattr(firebase, "_error", None)


def test_nothing_configured_is_reported_rather_than_assumed():
    assert firebase.configured() is False
    assert firebase.available() is False
    assert "no service-account credential set" in firebase.error()


@pytest.mark.parametrize("name", firebase.INLINE_VARS)
def test_a_credential_pasted_inline_is_recognised(monkeypatch, name):
    monkeypatch.setenv(name, json.dumps({"type": "service_account"}))
    assert firebase.configured() is True


def test_a_credential_on_disk_is_recognised(monkeypatch, tmp_path):
    key = tmp_path / "service-account.json"
    key.write_text(json.dumps({"type": "service_account"}))
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key))
    assert firebase.configured() is True


def test_a_broken_credential_fails_closed_and_says_why(monkeypatch):
    monkeypatch.setenv("FIREBASE_CREDENTIALS", "{not json")
    assert firebase.app() is None
    assert firebase.available() is False
    assert firebase.error().startswith("FIREBASE_CREDENTIALS:")


def test_initialisation_is_attempted_once_not_on_every_request(monkeypatch):
    monkeypatch.setenv("FIREBASE_CREDENTIALS", "{not json")
    attempts = []
    real = firebase._certificate
    monkeypatch.setattr(
        firebase, "_certificate", lambda *a: attempts.append(a) or real(*a)
    )
    for _ in range(3):
        firebase.app()
    assert len(attempts) == 1
