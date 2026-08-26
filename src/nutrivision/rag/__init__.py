"""Retrieval-augmented generation over the USDA-derived nutrition knowledge base."""

from __future__ import annotations

import os
import pathlib

ENV_PATH = pathlib.Path(__file__).resolve().parents[3] / ".env"


def load_env(path: pathlib.Path = ENV_PATH) -> None:
    """Read `.env` into the environment without overriding what is already set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
