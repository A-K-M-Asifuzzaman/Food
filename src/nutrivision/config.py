from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import torch


def _project_root() -> Path:
    env = os.environ.get("NUTRIVISION_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


ROOT = _project_root()
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts"

os.environ.setdefault("HF_HOME", str(DATA_DIR / "hf"))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

RAW_DIR = DATA_DIR / "raw"
IMAGE_DIR = DATA_DIR / "food101"
FEATURE_DIR = ARTIFACT_DIR / "features"
CHECKPOINT_DIR = ARTIFACT_DIR / "checkpoints"
EXPORT_DIR = ARTIFACT_DIR / "export"
REPORT_DIR = ARTIFACT_DIR / "reports"
KB_DIR = ROOT / "src" / "nutrivision" / "rag" / "corpus"
INDEX_DIR = ARTIFACT_DIR / "index"

for _d in (RAW_DIR, IMAGE_DIR, FEATURE_DIR, CHECKPOINT_DIR, EXPORT_DIR, REPORT_DIR, INDEX_DIR):
    _d.mkdir(parents=True, exist_ok=True)

HF_DATASET = "ethz/food101"
NUM_CLASSES = 101
SEED = 1337


def pick_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


DEVICE = pick_device()


@dataclass(frozen=True)
class BackboneSpec:

    key: str
    timm_name: str
    image_size: int
    dim: int
    notes: str = ""


FEATURE_BACKBONES: tuple[BackboneSpec, ...] = (
    BackboneSpec(
        key="siglip_so400m",
        timm_name="vit_so400m_patch14_siglip_384.webli",
        image_size=384,
        dim=1152,
        notes="Contrastive web-scale pretraining, strongest single feature extractor we can run locally.",
    ),
    BackboneSpec(
        key="dinov2_large",
        timm_name="vit_large_patch14_dinov2.lvd142m",
        image_size=518,
        dim=1024,
        notes="Self-supervised, texture and part sensitive. Decorrelated from the contrastive models.",
    ),
    BackboneSpec(
        key="eva02_large",
        timm_name="eva02_large_patch14_448.mim_m38m_ft_in22k_in1k",
        image_size=448,
        dim=1024,
        notes="Supervised IN-22k finetune, strong fine grained prior.",
    ),
)


@dataclass
class FinetuneConfig:
    backbone: str = "eva02_base_patch14_448.mim_in22k_ft_in22k_in1k"
    image_size: int = 448
    batch_size: int = 8
    grad_accum: int = 4
    epochs: int = 8
    base_lr: float = 1e-4
    head_lr_mult: float = 10.0
    weight_decay: float = 0.05
    layer_decay: float = 0.75
    warmup_epochs: float = 0.5
    label_smoothing: float = 0.1
    mixup_alpha: float = 0.8
    cutmix_alpha: float = 1.0
    mix_prob: float = 0.5
    drop_path: float = 0.2
    ema_decay: float = 0.9998
    num_workers: int = 6
    channels_last: bool = False
    resume: str | None = None
    out_name: str = "eva02_base_448"
    val_fraction: float = 0.04
    log_every: int = 50


@dataclass
class ProbeConfig:
    hidden: int = 1536
    dropout: float = 0.3
    epochs: int = 40
    batch_size: int = 512
    lr: float = 2e-3
    weight_decay: float = 1e-4
    label_smoothing: float = 0.1
    backbones: list[str] = field(default_factory=lambda: [b.key for b in FEATURE_BACKBONES])
