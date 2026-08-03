"""Firebase ID token verification.

Predictions are attributed to a signed-in account rather than to an anonymous
browser id. That is what makes a personal history trustworthy — a localStorage
key is lost the moment somebody clears site data or opens the page on their
phone, and it can be forged by anyone who reads the network tab.

The token is minted by Firebase in the browser and verified here against
Google's public keys. The client never tells us who it is; the signature does.
A caller can therefore claim any uid it likes and get a 401.

**Auth degrades, it does not fail closed by accident.** With no Firebase
credential configured the service runs open and says so on /health, because a
reviewer cloning this repo should get a working prediction endpoint without a
Google project. Set REQUIRE_AUTH=1 to refuse to serve unauthenticated requests
even when verification is unavailable — that is the correct setting for a
deployment, and it is what the Space runs with.
"""

from __future__ import annotations

import logging
import os

from fastapi import HTTPException, Request

log = logging.getLogger("foodgenome.auth")

# Accounts allowed into the admin console. Everyone else gets 403, including
# signed-in users — being authenticated is not being authorised.
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "zasif855@gmail.com").split(",")
    if e.strip()
}
REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "").strip() not in ("", "0", "false")


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


def _available() -> bool:
    """True once the Admin SDK has an initialised app to verify against."""
    try:
        import firebase_admin

        return bool(firebase_admin._apps)  # noqa: SLF001 — the only way to ask
    except Exception:  # noqa: BLE001
        return False


def current_user(request: Request) -> User | None:
    """The verified caller, or None when no usable token was presented."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    if not token or not _available():
        return None

    try:
        from firebase_admin import auth as fb_auth

        claims = fb_auth.verify_id_token(token)
    except Exception as exc:  # noqa: BLE001 — expired, malformed, wrong project
        log.info("token rejected: %s", type(exc).__name__)
        return None

    return User(
        uid=claims["uid"],
        email=claims.get("email"),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )


def require_user(request: Request) -> User:
    """A signed-in caller, or 401.

    When auth is not configured at all, this returns a stand-in rather than
    locking a self-hosted copy out of its own service — unless REQUIRE_AUTH is
    set, which is how the deployment runs.
    """
    user = current_user(request)
    if user:
        return user
    if REQUIRE_AUTH or _available():
        raise HTTPException(401, "Sign in to use this endpoint.")
    return User(uid="anonymous", email=None, name="Anonymous", picture=None)


def require_admin(request: Request) -> User:
    user = require_user(request)
    if _available() and not user.is_admin:
        raise HTTPException(403, "This console is restricted.")
    return user
