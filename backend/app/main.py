"""FastAPI service for FoodGenome AI.

Implements the contract the frontend already consumes — see `web/lib/types.ts`.
Setting FOODGENOME_API to this service's base URL is the only change the web app
needs to switch from its demo responses to real predictions.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import threading
import time

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from fastapi import Request

from .config import CONSTANTS, KB_PATH, MEMBERS
from .inference import CLASSIFIER, conformal_set
from .metrics import METRICS

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("foodgenome")

MAX_BYTES = 12 * 1024 * 1024
MODEL_NAME = "SigLIP-SO400M + EVA-02-L probability average"

app = FastAPI(
    title="FoodGenome AI",
    version="1.0.0",
    description="Food-101 classification with calibrated confidence, conformal "
    "prediction sets and USDA-grounded nutrition.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.middleware("http")
async def track(request: Request, call_next):
    """Time every request. The route template is recorded rather than the raw
    path so that 101 dish lookups do not become 101 separate series."""
    started = time.time()
    try:
        response = await call_next(request)
    except Exception:
        METRICS.record_request(request.url.path, (time.time() - started) * 1000, ok=False)
        raise
    METRICS.record_request(
        request.url.path, (time.time() - started) * 1000, ok=response.status_code < 500
    )
    return response


_kb = json.loads(KB_PATH.read_text())
ENTRIES = {e["class"]: e for e in _kb["entries"]}

# Class index order comes from the knowledge base's own entry order, which was
# built against the dataset's label order and is verified equal to it.
#
# Do not substitute sorted(): the canonical order is NOT Python's string sort.
# "cheesecake" precedes "cheese_plate" in the dataset, while sorted() reverses
# them because "_" (0x5F) sorts before "c" (0x63). That single transposition
# would make the API report cheesecake as a cheese plate, confidently, with the
# right probability attached to the wrong name.
CLASS_ORDER = [e["class"] for e in _kb["entries"]]
assert len(CLASS_ORDER) == 101, f"expected 101 classes, got {len(CLASS_ORDER)}"


def title_for(name: str) -> str:
    entry = ENTRIES.get(name)
    return entry["title"] if entry else name.replace("_", " ").title()


@app.post("/explain")
async def explain(image: UploadFile = File(...), food_class: str | None = None) -> dict:
    """Grad-CAM overlay for an uploaded image, returned inline as a data URI.

    The overlay is composited server-side rather than shipping a raw heatmap for
    the browser to colour. The colour ramp encodes the finding — monotonic in
    lightness so the hottest region reads as hottest — and duplicating that in
    client code is how the two drift apart.
    """
    started = time.time()
    raw = await image.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Image too large.")
    try:
        pil = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "Could not decode that file as an image.")

    index = CLASS_ORDER.index(food_class) if food_class in ENTRIES else None
    result = CLASSIFIER.explain(pil, class_index=index)

    from nutrivision.explain.gradcam import overlay

    display = pil.copy()
    display.thumbnail((640, 640))
    composed = overlay(display, result["cam"])

    buffer = io.BytesIO()
    composed.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode()

    return {
        "overlay": f"data:image/png;base64,{encoded}",
        "class": CLASS_ORDER[result["class_index"]],
        "title": title_for(CLASS_ORDER[result["class_index"]]),
        "backbone": result["backbone"],
        "grid": result["grid"],
        # Share of the map above half intensity. A map spread across the whole
        # frame is not an explanation, and this is the number that admits it.
        "peak_fraction": round(result["peak_fraction"], 4),
        "method": "Grad-CAM on the final transformer block",
        "latency_ms": int((time.time() - started) * 1000),
    }


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=400)
    # Supplied by the client after a prediction. The vision model has already
    # named the dish, so the question does not have to; see rag/retrieve.py.
    food_class: str | None = None


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    if request.food_class and request.food_class not in ENTRIES:
        raise HTTPException(400, f"Unknown food class: {request.food_class}")

    from nutrivision.rag.generate import answer

    result = answer(request.question, food_class=request.food_class)
    METRICS.record_answer(
        mode=result.mode, grounded=result.grounded,
        cost=result.usage.get("cost_usd", 0.0),
    )
    payload = result.as_dict()
    # The retrieved documents are large and only useful for debugging; the
    # citations carry everything the interface needs to attribute a claim.
    payload.pop("retrieved", None)
    return payload


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_loaded": CLASSIFIER.ready,
        "device": str(CLASSIFIER.device),
        "missing_reports": CONSTANTS["missing_reports"],
        "uptime_seconds": METRICS.snapshot()["uptime_seconds"],
    }


@app.post("/warm")
def warm() -> dict:
    """Start loading the backbones without waiting for them.

    A free Space sleeps, and the first request after that pays roughly thirty
    seconds of model download. Letting the client trigger the load on page open
    means the wait happens behind a progress indicator rather than behind an
    apparently frozen upload button.
    """
    if CLASSIFIER.ready:
        return {"status": "ready"}
    threading.Thread(target=CLASSIFIER.load, daemon=True).start()
    return {"status": "warming"}


@app.get("/stats")
def stats() -> dict:
    """Operational counters for the admin console.

    In-process, so they cover the current container only — which the payload
    states rather than leaving a reader to assume otherwise.
    """
    snap = METRICS.snapshot()
    snap["model"] = {
        "name": MODEL_NAME,
        "loaded": CLASSIFIER.ready,
        "device": str(CLASSIFIER.device),
        "test_top1": CONSTANTS["test_top1"],
        "temperature": CONSTANTS["temperature"],
    }
    return snap


class Feedback(BaseModel):
    food_class: str
    helpful: bool
    note: str | None = Field(default=None, max_length=200)


@app.post("/feedback")
def feedback(body: Feedback) -> dict:
    """Thumbs up or down on a prediction.

    A thumbs-down on a confident prediction is precisely the case worth
    re-examining, and it appears in no accuracy metric computed on a labelled
    split. Stored in the rolling feed rather than a database, so it survives the
    container and no longer.
    """
    if body.food_class not in ENTRIES:
        raise HTTPException(400, f"Unknown food class: {body.food_class}")
    METRICS.record_feedback(
        food_class=body.food_class, helpful=body.helpful, note=body.note
    )
    return {"recorded": True}


@app.get("/classes")
def classes() -> dict:
    return {"count": len(CLASS_ORDER), "classes": CLASS_ORDER}


@app.get("/model")
def model_info() -> dict:
    return {
        "name": MODEL_NAME,
        "ensemble": MEMBERS,
        "test_top1": CONSTANTS["test_top1"],
        "temperature": CONSTANTS["temperature"],
        "conformal": {
            "alpha": CONSTANTS["conformal_alpha"],
            "qhat": CONSTANTS["conformal_qhat"],
            "measured_coverage": CONSTANTS["conformal_coverage"],
        },
        "ood_threshold": CONSTANTS["ood_threshold"],
    }


@app.post("/predict")
async def predict(image: UploadFile = File(...)) -> dict:
    started = time.time()

    raw = await image.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, f"Image larger than {MAX_BYTES // 1024 // 1024} MB.")
    try:
        pil = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "Could not decode that file as an image.")

    calibrated, raw_probs = CLASSIFIER.probabilities(pil)

    top = int(calibrated.argmax())
    top_name = CLASS_ORDER[top]
    entry = ENTRIES[top_name]

    msp = float(calibrated.max())
    threshold = CONSTANTS["ood_threshold"]
    members = conformal_set(calibrated)

    # Abstention combines two signals, because neither is sufficient alone.
    # Maximum softmax probability catches noise but a flat colour field scored
    # 0.43 and slipped past. Conformal set size caught it at 8 candidates, while
    # every correctly classified dish tested returned 1.
    #
    # Measured on the 25,250-image test split: the combined rule flags 2.28% of
    # real food, and accuracy on what it keeps rises from 97.16% to 97.94%. MSP
    # alone flags 0.72% and reaches only 97.6%.
    #
    # This is still an abstention rule, not a trained OOD detector — it reports
    # "the model is lost here", which correlates with but is not the same as
    # "this is not food". A real detector needs non-food negatives, which is
    # stage 5's remaining work.
    LOST_SET_SIZE = 5
    uncertain = msp < threshold or len(members) >= LOST_SET_SIZE

    latency = int((time.time() - started) * 1000)
    METRICS.record_prediction(
        title=entry["title"], confidence=msp, set_size=len(members),
        abstained=uncertain, ms=latency,
    )

    return {
        "source": "model",
        "latency_ms": latency,
        "model": {
            "name": MODEL_NAME,
            "test_top1": CONSTANTS["test_top1"],
            "ensemble": MEMBERS,
        },
        "prediction": {
            "class": top_name,
            "title": entry["title"],
            "confidence": msp,
            "raw_confidence": float(raw_probs.max()),
        },
        "conformal": {
            "alpha": CONSTANTS["conformal_alpha"],
            "candidates": [
                {
                    "class": CLASS_ORDER[i],
                    "title": title_for(CLASS_ORDER[i]),
                    "probability": float(calibrated[i]),
                }
                for i in members
            ],
            "guarantee": (
                f"Measured over 25,250 held-out images, the true dish falls inside "
                f"this set {CONSTANTS['conformal_coverage']:.1f}% of the time."
            ),
        },
        "ood": {
            "is_food": not uncertain,
            "score": msp,
            "threshold": threshold,
            "set_size": len(members),
            "method": "abstention: max-softmax-probability or conformal set size",
        },
        "nutrition": {
            "entry": entry,
            "per_serving": entry["nutrients_per_serving"],
            "per_100g": entry["nutrients_per_100g"],
            "serving_label": entry["serving_label"],
            "components": entry.get("components"),
        },
    }
