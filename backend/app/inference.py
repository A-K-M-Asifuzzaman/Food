"""The served classifier: two frozen backbones, two MLP probes, averaged."""

from __future__ import annotations

import logging
import threading

import numpy as np
import timm
import torch
import torch.nn.functional as F
from PIL import Image

from nutrivision.config import FEATURE_BACKBONES, NUM_CLASSES
from nutrivision.models.heads import MLPProbe

from .config import CHECKPOINTS, CONSTANTS, MEMBERS, SET_THRESHOLD

log = logging.getLogger(__name__)

_SPECS = {b.key: b for b in FEATURE_BACKBONES}


def pick_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


class Classifier:
    """Lazily loaded so the process can answer /health before weights are in RAM."""

    def __init__(self) -> None:
        self.device = pick_device()
        self._lock = threading.Lock()
        self._ready = False
        self.backbones: dict[str, tuple] = {}
        self.probes: dict[str, MLPProbe] = {}
        self.classes: list[str] = []

    @property
    def ready(self) -> bool:
        return self._ready

    def load(self) -> None:
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            log.info("loading %d backbones onto %s", len(MEMBERS), self.device)
            for key in MEMBERS:
                spec = _SPECS[key]
                model = timm.create_model(spec.timm_name, pretrained=True, num_classes=0)
                model.eval().to(self.device)
                cfg = timm.data.resolve_data_config({}, model=model)
                transform = timm.data.create_transform(**cfg, is_training=False)
                self.backbones[key] = (model, transform)

                ckpt = torch.load(
                    CHECKPOINTS / f"probe_{key}.pt", map_location=self.device, weights_only=False
                )
                probe = MLPProbe(ckpt["dims"][0], NUM_CLASSES, ckpt["hidden"], ckpt["dropout"])
                probe.load_state_dict(ckpt["state_dict"])
                probe.eval().to(self.device)
                self.probes[key] = probe
                log.info("  %s ready (dim %d)", key, ckpt["dims"][0])

            self._ready = True

    @torch.no_grad()
    def probabilities(self, image: Image.Image) -> np.ndarray:
        """Calibrated class probabilities for one image."""
        self.load()
        stack = []
        for key in MEMBERS:
            model, transform = self.backbones[key]
            x = transform(image).unsqueeze(0).to(self.device)
            feats = model(x)
            # Must match training; see module docstring.
            feats = F.normalize(feats.float(), dim=-1)
            logits = self.probes[key](feats)
            stack.append(logits.softmax(dim=-1))

        mean = torch.stack(stack).mean(dim=0)
        # Temperature acts on the surrogate logits of the averaged probability, which is
        # how the constant was fitted offline.
        calibrated = (mean.clamp_min(1e-12).log() / CONSTANTS["temperature"]).softmax(dim=-1)
        return calibrated.squeeze(0).cpu().numpy(), mean.squeeze(0).cpu().numpy()


    def explain(self, image: Image.Image, class_index: int | None = None) -> dict:
        """Grad-CAM for the strongest single member."""
        from nutrivision.explain.gradcam import explain as run_gradcam

        self.load()
        key = MEMBERS[0]
        model, transform = self.backbones[key]
        result = run_gradcam(image, model, transform, self.probes[key], class_index)
        result["backbone"] = key
        return result


def conformal_set(probs: np.ndarray, k_max: int = 8) -> list[int]:
    """LAC with a forced top-1, the configuration measured at 99.56% coverage."""
    top = int(probs.argmax())
    idx = np.flatnonzero(probs >= SET_THRESHOLD)
    ordered = sorted(idx.tolist(), key=lambda i: -probs[i])
    if top not in ordered:
        ordered.insert(0, top)
    return ordered[:k_max]


CLASSIFIER = Classifier()
