"""Choose one representative photograph per dish and export it for the web."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from tqdm import tqdm

from nutrivision.config import FEATURE_DIR, ROOT
from nutrivision.data.dataset import Food101Folder, load_classes

OUT_DIR = ROOT / "web" / "public" / "dishes"
MANIFEST = ROOT / "web" / "data" / "dish-images.json"


def centroid_pick(backbone: str, shortlist: int) -> dict[int, list[tuple[int, float]]]:
    x = np.load(FEATURE_DIR / backbone / "train_x.npy").astype(np.float32)
    y = np.load(FEATURE_DIR / backbone / "train_y.npy")

    x /= np.linalg.norm(x, axis=1, keepdims=True) + 1e-8

    picks: dict[int, list[tuple[int, float]]] = {}
    for label in range(int(y.max()) + 1):
        idx = np.flatnonzero(y == label)
        feats = x[idx]
        centroid = feats.mean(axis=0)
        centroid /= np.linalg.norm(centroid) + 1e-8
        sims = feats @ centroid
        order = np.argsort(-sims)[:shortlist]
        picks[label] = [(int(idx[o]), float(sims[o])) for o in order]
    return picks


def export(path: Path, dest: Path, size: int, quality: int) -> tuple[int, int]:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        side = min(im.size)
        left = (im.width - side) // 2
        top = (im.height - side) // 2
        im = im.crop((left, top, left + side, top + side))
        if im.width > size:
            im = im.resize((size, size), Image.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "WEBP", quality=quality, method=6)
        return im.size


def main() -> None:
    p = argparse.ArgumentParser(description="Export one representative image per dish")
    p.add_argument("--backbone", default="siglip_so400m")
    p.add_argument("--size", type=int, default=512)
    p.add_argument("--quality", type=int, default=76)
    p.add_argument("--shortlist", type=int, default=5)
    p.add_argument("--rank", type=int, default=0, help="which shortlist entry to use")
    args = p.parse_args()

    classes = load_classes()
    ds = Food101Folder(split="train", val_fraction=0.0)
    if len(ds) != len(np.load(FEATURE_DIR / args.backbone / "train_y.npy")):
        raise SystemExit("feature bank and image folder disagree on length; re-extract features")

    picks = centroid_pick(args.backbone, args.shortlist)
    manifest: dict[str, dict] = {}
    total_bytes = 0

    for label, slug in enumerate(tqdm(classes, desc="export", unit="dish")):
        row, sim = picks[label][args.rank]
        src = ds.samples[row].path
        if ds.samples[row].label != label:
            raise SystemExit(f"ordering mismatch at row {row}; feature bank is stale")

        dest = OUT_DIR / f"{slug}.webp"
        w, h = export(src, dest, args.size, args.quality)
        total_bytes += dest.stat().st_size
        manifest[slug] = {
            "file": f"/dishes/{slug}.webp",
            "width": w,
            "height": h,
            "source": src.name,
            "similarity": round(sim, 4),
            "alternates": [ds.samples[r].path.name for r, _ in picks[label][1:]],
        }

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"{len(manifest)} images, {total_bytes / 1e6:.1f} MB total -> {OUT_DIR}")
    print(f"manifest -> {MANIFEST}")


if __name__ == "__main__":
    main()
