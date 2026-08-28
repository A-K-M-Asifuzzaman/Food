from __future__ import annotations

import base64
import io
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import auth as auth_mode
from .auth import User, current_user, require_admin, require_user
from .config import CONSTANTS, KB_PATH, MEMBERS
from .images import decode
from .inference import CLASSIFIER, conformal_set
from .metrics import METRICS
from .store import STORE

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("foodgenome")

MODEL_NAME = "SigLIP-SO400M + EVA-02-L probability average"


@asynccontextmanager
async def lifespan(_: FastAPI):
    mode = auth_mode.mode()
    if mode["firebase"]:
        log.info("auth: firebase token verification active")
    elif mode["demo_mode"]:
        log.warning(
            "auth: FOODGENOME_DEMO_MODE is on and firebase is unavailable (%s); "
            "every caller shares one demo identity and the admin console stays closed",
            mode["error"],
        )
    else:
        log.error(
            "auth: firebase is unavailable (%s) and demo mode is off; "
            "every authenticated route will answer 401",
            mode["error"],
        )
    if not auth_mode.ADMIN_EMAILS:
        log.warning("auth: ADMIN_EMAILS is empty, so /stats and /analytics answer nobody")
    yield


app = FastAPI(
    title="FoodGenome AI",
    version="1.0.0",
    description="Food-101 classification with calibrated confidence, conformal "
    "prediction sets and USDA-grounded nutrition.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

@app.middleware("http")
async def track(request: Request, call_next):
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

CLASS_ORDER = [e["class"] for e in _kb["entries"]]
assert len(CLASS_ORDER) == 101, f"expected 101 classes, got {len(CLASS_ORDER)}"


def title_for(name: str) -> str:
    entry = ENTRIES.get(name)
    return entry["title"] if entry else name.replace("_", " ").title()


@app.post("/explain")
async def explain(
    image: UploadFile = File(...),
    food_class: str | None = None,
    user: User = Depends(require_user),
) -> dict:
    started = time.time()
    pil = decode(await image.read())

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
        "peak_fraction": round(result["peak_fraction"], 4),
        "method": "Grad-CAM on the final transformer block",
        "latency_ms": int((time.time() - started) * 1000),
    }


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=400)
    food_class: str | None = None


@app.post("/ask")
def ask(body: AskRequest, user: User = Depends(require_user)) -> dict:
    if body.food_class and body.food_class not in ENTRIES:
        raise HTTPException(400, f"Unknown food class: {body.food_class}")

    from nutrivision.rag.pipeline import answer

    result = answer(body.question, food_class=body.food_class)
    cost = result.usage.get("cost_usd", 0.0)
    METRICS.record_answer(mode=result.mode, grounded=result.grounded, cost=cost)
    STORE.record_question(
        session=user.uid, email=user.email, question=body.question,
        food_class=body.food_class, mode=result.mode, grounded=result.grounded,
        citations=len(result.citations), cost_usd=cost, ms=result.latency_ms,
    )
    payload = result.as_dict()
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
        "auth": auth_mode.mode(),
        "store": STORE.status(),
    }


@app.post("/warm")
def warm() -> dict:
    if CLASSIFIER.ready:
        return {"status": "ready"}
    threading.Thread(target=CLASSIFIER.load, daemon=True).start()
    return {"status": "warming"}


@app.get("/stats")
def stats(_: User = Depends(require_admin)) -> dict:
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
def feedback(body: Feedback, user: User = Depends(require_user)) -> dict:
    if body.food_class not in ENTRIES:
        raise HTTPException(400, f"Unknown food class: {body.food_class}")
    METRICS.record_feedback(
        food_class=body.food_class, helpful=body.helpful, note=body.note
    )
    STORE.record_feedback(
        session=user.uid, email=user.email, food_class=body.food_class,
        helpful=body.helpful, note=body.note,
    )
    return {"recorded": True}


@app.get("/history")
def history(limit: int = 40, user: User = Depends(require_user)) -> dict:
    return STORE.history(user.uid, limit=min(limit, 100))


@app.delete("/history")
def erase_history(user: User = Depends(require_user)) -> dict:
    return STORE.erase(user.uid)


@app.get("/analytics")
def analytics(days: int = 14, _: User = Depends(require_admin)) -> dict:
    return STORE.analytics(days=max(1, min(days, 90)))


@app.get("/me")
def me(request: Request) -> dict:
    user = current_user(request)
    return {"signed_in": bool(user), "user": user.as_dict() if user else None}


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
async def predict(
    image: UploadFile = File(...), user: User = Depends(require_user)
) -> dict:
    started = time.time()

    pil = decode(await image.read())

    calibrated, raw_probs = CLASSIFIER.probabilities(pil)

    top = int(calibrated.argmax())
    top_name = CLASS_ORDER[top]
    entry = ENTRIES[top_name]

    msp = float(calibrated.max())
    threshold = CONSTANTS["ood_threshold"]
    members = conformal_set(calibrated)

    LOST_SET_SIZE = 5
    uncertain = msp < threshold or len(members) >= LOST_SET_SIZE

    latency = int((time.time() - started) * 1000)
    METRICS.record_prediction(
        title=entry["title"], confidence=msp, set_size=len(members),
        abstained=uncertain, ms=latency,
    )
    STORE.record_prediction(
        session=user.uid, email=user.email, food_class=top_name, title=entry["title"],
        confidence=msp, set_size=len(members),
        candidates=[CLASS_ORDER[i] for i in members],
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
