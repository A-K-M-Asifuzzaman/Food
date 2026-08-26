from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

from nutrivision.config import IMAGE_DIR, SEED

Image.MAX_IMAGE_PIXELS = None


def load_classes(root: Path = IMAGE_DIR) -> list[str]:
    meta = root / "meta.json"
    if meta.exists():
        return json.loads(meta.read_text())["classes"]
    return sorted(p.name for p in (root / "train").iterdir() if p.is_dir())


@dataclass
class Sample:
    path: Path
    label: int


def holdout_mask(
    targets: np.ndarray, num_classes: int, val_fraction: float, seed: int = SEED
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    is_val = np.zeros(len(targets), dtype=bool)
    for label in range(num_classes):
        idx = np.flatnonzero(targets == label)
        rng.shuffle(idx)
        n_val = max(1, int(round(len(idx) * val_fraction)))
        is_val[idx[:n_val]] = True
    return is_val


class Food101Folder(Dataset):

    def __init__(
        self,
        split: str = "train",
        root: Path = IMAGE_DIR,
        transform=None,
        val_fraction: float = 0.04,
        seed: int = SEED,
        return_path: bool = False,
    ):
        if split not in {"train", "val", "test", "trainval"}:
            raise ValueError(f"unknown split {split!r}")

        self.root = Path(root)
        self.classes = load_classes(self.root)
        self.class_to_idx = {c: i for i, c in enumerate(self.classes)}
        self.transform = transform
        self.return_path = return_path
        self.split = split

        disk_split = "test" if split == "test" else "train"
        items: list[Sample] = []
        for cls in self.classes:
            label = self.class_to_idx[cls]
            folder = self.root / disk_split / cls
            for p in sorted(folder.glob("*.jpg")):
                items.append(Sample(p, label))

        if split in {"train", "val"} and val_fraction > 0:
            labels = np.array([s.label for s in items])
            is_val = holdout_mask(labels, len(self.classes), val_fraction, seed)
            keep = is_val if split == "val" else ~is_val
            items = [s for s, k in zip(items, keep, strict=True) if k]

        self.samples = items
        self.targets = np.array([s.label for s in items], dtype=np.int64)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, i: int):
        sample = self.samples[i]
        image = Image.open(sample.path).convert("RGB")
        if self.transform is not None:
            image = self.transform(image)
        if self.return_path:
            return image, sample.label, str(sample.path)
        return image, sample.label


def class_weights(targets: np.ndarray, num_classes: int) -> torch.Tensor:
    counts = np.bincount(targets, minlength=num_classes).astype(np.float64)
    counts[counts == 0] = 1.0
    w = counts.sum() / (num_classes * counts)
    return torch.tensor(w, dtype=torch.float32)
