from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

log = logging.getLogger("foodgenome.firebase")

INLINE_VARS = ("FIREBASE_CREDENTIALS", "FIREBASE_SERVICE_ACCOUNT_JSON")
PATH_VARS = ("GOOGLE_APPLICATION_CREDENTIALS",)

_lock = threading.Lock()
_app = None
_attempted = False
_error: str | None = None


def _source() -> tuple[str, str] | None:
    for name in INLINE_VARS:
        value = os.environ.get(name, "").strip()
        if value:
            return name, value
    for name in PATH_VARS:
        value = os.environ.get(name, "").strip()
        if value:
            return name, value
    return None


def configured() -> bool:
    return _source() is not None


def error() -> str | None:
    if _error:
        return _error
    if not configured():
        return "no service-account credential set (" + ", ".join(INLINE_VARS + PATH_VARS) + ")"
    return None


def _certificate(name: str, value: str):
    from firebase_admin import credentials

    if name in PATH_VARS:
        return credentials.Certificate(str(Path(value).expanduser()))
    return credentials.Certificate(json.loads(value))


def app():
    global _app, _attempted, _error
    if _attempted:
        return _app
    with _lock:
        if _attempted:
            return _app
        _attempted = True
        source = _source()
        if source is None:
            return None
        name, value = source
        try:
            import firebase_admin

            _app = firebase_admin.initialize_app(_certificate(name, value))
            log.info("firebase admin initialised from %s", name)
        except Exception as exc:
            _error = f"{name}: {type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
            log.error("firebase admin failed to initialise: %s", _error)
        return _app


def available() -> bool:
    return app() is not None
