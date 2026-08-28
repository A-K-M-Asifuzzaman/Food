from __future__ import annotations

import io
import warnings

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

MAX_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_SIDE = 12_000
DECODE_TO = 2048

Image.MAX_IMAGE_PIXELS = MAX_PIXELS

BOMB = (Image.DecompressionBombWarning, Image.DecompressionBombError)
UNREADABLE = (UnidentifiedImageError, OSError, ValueError)


def decode(raw: bytes) -> Image.Image:
    if not raw:
        raise HTTPException(400, "No image supplied.")
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, f"Image larger than {MAX_BYTES // 1024 // 1024} MB.")

    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            image = Image.open(io.BytesIO(raw))
            width, height = image.size
        except BOMB as exc:
            raise HTTPException(413, _too_many_pixels()) from exc
        except UNREADABLE as exc:
            raise HTTPException(415, _unreadable()) from exc

        if width < 1 or height < 1:
            raise HTTPException(415, _unreadable())
        if width > MAX_SIDE or height > MAX_SIDE or width * height > MAX_PIXELS:
            raise HTTPException(413, _too_many_pixels())

        try:
            image.draft("RGB", (DECODE_TO, DECODE_TO))
            image = image.convert("RGB")
        except BOMB as exc:
            raise HTTPException(413, _too_many_pixels()) from exc
        except UNREADABLE as exc:
            raise HTTPException(415, _unreadable()) from exc

    return image


def _unreadable() -> str:
    return "Could not decode that file as an image."


def _too_many_pixels() -> str:
    return (
        f"Image expands to more than {MAX_PIXELS // 1_000_000} megapixels "
        f"({MAX_SIDE} px per side), which will not be decoded."
    )
