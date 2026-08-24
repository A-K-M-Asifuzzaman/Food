"""Constants the served model depends on."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

REPO_ROOT = Path(os.environ.get("FOODGENOME_ROOT", Path(__file__).resolve().parents[2]))
ARTIFACTS = REPO_ROOT / "artifacts"
REPORTS = ARTIFACTS / "reports"
CHECKPOINTS = ARTIFACTS / "checkpoints"
KB_PATH = Path(os.environ.get("FOODGENOME_KB", REPO_ROOT / "data" / "nutrition" / "kb.json"))

MEMBERS = ["siglip_so400m", "eva02_large"]

# Fallbacks, used only when the corresponding report is missing.
_DEFAULTS = {
    "temperature": 0.7621,
    "conformal_qhat": 0.98712,
    "conformal_alpha": 0.01,
    "conformal_coverage": 99.56,
    "ood_threshold": 0.4189,
    "test_top1": 97.156,
}


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def load_constants() -> dict:
    out = dict(_DEFAULTS)
    missing = []

    cal = _read(REPORTS / "calibration_ensemble_siglip_eva02.json")
    if cal:
        out["temperature"] = cal["temperature"]
        out["test_top1"] = cal["test_after"]["top1"]
    else:
        missing.append("calibration_ensemble_siglip_eva02.json")

    conf = _read(REPORTS / "conformal.json")
    if conf:
        row = next(
            (r for r in conf["results"] if abs(r["alpha"] - _DEFAULTS["conformal_alpha"]) < 1e-9),
            None,
        )
        if row:
            out["conformal_qhat"] = row["lac_top1"]["qhat"]
            out["conformal_coverage"] = row["lac_top1"]["coverage"]
    else:
        missing.append("conformal.json")

    if missing:
        log.warning(
            "Falling back to compiled-in constants; missing reports: %s. "
            "Numbers served will not reflect this build's artifacts.",
            ", ".join(missing),
        )
    out["missing_reports"] = missing
    return out


CONSTANTS = load_constants()

# LAC includes every class whose calibrated probability clears this, and the top-1 class
# unconditionally so a set is never empty.
SET_THRESHOLD = 1.0 - CONSTANTS["conformal_qhat"]
