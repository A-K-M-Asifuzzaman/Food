from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

for name in (
    "FIREBASE_CREDENTIALS",
    "FIREBASE_SERVICE_ACCOUNT_JSON",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "MONGODB_URI",
    "FOODGENOME_DEMO_MODE",
):
    os.environ.pop(name, None)


@pytest.fixture(autouse=True)
def clean_auth_env(monkeypatch):
    for name in ("FOODGENOME_DEMO_MODE", "REQUIRE_AUTH"):
        monkeypatch.delenv(name, raising=False)
