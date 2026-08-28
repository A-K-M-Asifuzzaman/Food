from __future__ import annotations

import io
import struct
import zlib

import pytest
from fastapi import HTTPException
from PIL import Image

from backend.app.images import MAX_BYTES, MAX_PIXELS, MAX_SIDE, decode


def real_png(width: int = 64, height: int = 48, mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), "red").save(buffer, format="PNG")
    return buffer.getvalue()


def chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def declared_png(width: int, height: int) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\x00" * 32))
        + chunk(b"IEND", b"")
    )


def test_a_normal_photograph_decodes_to_rgb():
    image = decode(real_png())
    assert image.mode == "RGB"
    assert image.size == (64, 48)


def test_a_greyscale_image_is_converted():
    assert decode(real_png(mode="L")).mode == "RGB"


def test_an_empty_body_is_a_bad_request():
    with pytest.raises(HTTPException) as raised:
        decode(b"")
    assert raised.value.status_code == 400


def test_a_file_that_is_not_an_image_is_rejected():
    with pytest.raises(HTTPException) as raised:
        decode(b"this is a text file, not a photograph of dinner")
    assert raised.value.status_code == 415


def test_a_truncated_image_is_rejected_rather_than_half_decoded():
    with pytest.raises(HTTPException) as raised:
        decode(real_png()[:40])
    assert raised.value.status_code == 415


def test_an_oversized_upload_is_refused_before_any_decoding():
    with pytest.raises(HTTPException) as raised:
        decode(b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_BYTES)
    assert raised.value.status_code == 413


def test_a_decompression_bomb_is_refused_on_its_declared_size():
    side = 30_000
    assert side * side > MAX_PIXELS
    bomb = declared_png(side, side)
    assert len(bomb) < 1024

    with pytest.raises(HTTPException) as raised:
        decode(bomb)
    assert raised.value.status_code == 413
    assert "megapixels" in raised.value.detail


def test_an_extreme_aspect_ratio_is_refused_on_its_longest_side():
    stripe = declared_png(MAX_SIDE + 1, 8)
    assert (MAX_SIDE + 1) * 8 < MAX_PIXELS

    with pytest.raises(HTTPException) as raised:
        decode(stripe)
    assert raised.value.status_code == 413


def test_a_plausible_size_passes_the_pixel_gate_and_fails_only_on_content():
    modest = declared_png(1024, 768)
    with pytest.raises(HTTPException) as raised:
        decode(modest)
    assert raised.value.status_code == 415
