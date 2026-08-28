from __future__ import annotations

import logging
import os

from fastapi import HTTPException, Request

from . import firebase

log = logging.getLogger("foodgenome.auth")

ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "zasif855@gmail.com").split(",")
    if e.strip()
}

DEMO_MODE = os.environ.get("FOODGENOME_DEMO_MODE", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)


class User:
    def __init__(self, uid: str, email: str | None, name: str | None, picture: str | None):
        self.uid = uid
        self.email = (email or "").lower() or None
        self.name = name
        self.picture = picture

    @property
    def is_admin(self) -> bool:
        return bool(self.email and self.email in ADMIN_EMAILS)

    def as_dict(self) -> dict:
        return {
            "uid": self.uid,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "admin": self.is_admin,
        }


def demo_user() -> User:
    return User(uid="demo", email=None, name="Demo visitor", picture=None)


def mode() -> dict:
    return {
        "firebase": firebase.available(),
        "demo_mode": DEMO_MODE,
        "error": firebase.error(),
    }


def current_user(request: Request) -> User | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    if not token:
        return None

    fb_app = firebase.app()
    if fb_app is None:
        log.warning("bearer token presented but firebase admin is unavailable: %s", firebase.error())
        return None

    try:
        from firebase_admin import auth as fb_auth

        claims = fb_auth.verify_id_token(token, app=fb_app)
    except Exception as exc:
        log.info("token rejected: %s", type(exc).__name__)
        return None

    return User(
        uid=claims["uid"],
        email=claims.get("email"),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )


def require_user(request: Request) -> User:
    user = current_user(request)
    if user:
        return user
    if DEMO_MODE:
        return demo_user()
    raise HTTPException(401, "Sign in to use this endpoint.")


def require_admin(request: Request) -> User:
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Sign in to use this endpoint.")
    if not user.is_admin:
        raise HTTPException(403, "This console is restricted.")
    return user
