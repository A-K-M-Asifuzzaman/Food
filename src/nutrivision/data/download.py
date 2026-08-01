"""Materialise Food-101 from the Hub into a plain image folder tree.

Parquet is great for transfer and terrible for the random access pattern of
multi-epoch training with worker processes, so we pay a one-off decode cost and
write JPEGs to disk once.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tqdm import tqdm

from nutrivision.config import HF_DATASET, IMAGE_DIR, RAW_DIR

SPLIT_ALIASES = {"train": "train", "test": "validation", "validation": "validation"}


def _target_split(split: str) -> str:
    return "train" if split == "train" else "test"


def export_split(ds, split: str, out_root: Path, quality: int = 95) -> int:
    labels = ds.features["label"].names
    out_split = out_root / _target_split(split)
    written = 0

    for name in labels:
        (out_split / name).mkdir(parents=True, exist_ok=True)

    for idx, row in enumerate(tqdm(ds, desc=f"export {split}", unit="img")):
        name = labels[row["label"]]
        path = out_split / name / f"{name}_{idx:06d}.jpg"
        if path.exists():
            continue
        image = row["image"]
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(path, "JPEG", quality=quality, optimize=True)
        written += 1

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and unpack Food-101")
    parser.add_argument("--out", type=Path, default=IMAGE_DIR)
    parser.add_argument("--quality", type=int, default=95)
    args = parser.parse_args()

    from datasets import load_dataset

    args.out.mkdir(parents=True, exist_ok=True)
    summary: dict[str, int] = {}
    label_names: list[str] = []

    for split, hub_split in SPLIT_ALIASES.items():
        if split == "validation":
            continue
        ds = load_dataset(HF_DATASET, split=hub_split, cache_dir=str(RAW_DIR))
        label_names = ds.features["label"].names
        summary[_target_split(split)] = len(ds)
        export_split(ds, split, args.out, quality=args.quality)

    meta = {
        "dataset": HF_DATASET,
        "num_classes": len(label_names),
        "classes": label_names,
        "counts": summary,
    }
    (args.out / "meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps({k: v for k, v in meta.items() if k != "classes"}, indent=2))


if __name__ == "__main__":
    main()
