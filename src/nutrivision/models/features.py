from __future__ import annotations

import argparse
import json
import time

import numpy as np
import timm
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from nutrivision.config import (
    DEVICE,
    FEATURE_BACKBONES,
    FEATURE_DIR,
    IMAGE_DIR,
    BackboneSpec,
)
from nutrivision.data.dataset import Food101Folder

BACKBONES = {b.key: b for b in FEATURE_BACKBONES}


def build_backbone(spec: BackboneSpec, image_size: int | None = None):
    model = timm.create_model(spec.timm_name, pretrained=True, num_classes=0)
    model.eval().to(DEVICE)

    cfg = timm.data.resolve_data_config({}, model=model)
    if image_size:
        cfg["input_size"] = (3, image_size, image_size)
        cfg["crop_pct"] = 1.0
    transform = timm.data.create_transform(**cfg, is_training=False)
    return model, transform, cfg


@torch.no_grad()
def extract(
    spec: BackboneSpec,
    split: str,
    batch_size: int,
    workers: int,
    image_size: int | None,
    flip: bool,
    limit: int | None = None,
) -> dict:
    model, transform, cfg = build_backbone(spec, image_size)
    ds = Food101Folder(split=split, root=IMAGE_DIR, transform=transform, val_fraction=0.0)
    if limit:
        ds.samples = ds.samples[:limit]
        ds.targets = ds.targets[:limit]

    loader = DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=DEVICE.type == "cuda",
        persistent_workers=workers > 0,
    )

    feats = np.zeros((len(ds), spec.dim), dtype=np.float16)
    labels = np.zeros(len(ds), dtype=np.int64)
    cursor = 0
    started = time.time()

    autocast = torch.autocast(device_type=DEVICE.type, dtype=torch.float16, enabled=DEVICE.type != "cpu")
    for images, target in tqdm(loader, desc=f"{spec.key}/{split}", unit="batch"):
        images = images.to(DEVICE, non_blocking=True)
        with autocast:
            out = model(images)
            if flip:
                out = out + model(torch.flip(images, dims=[3]))
                out = out / 2
        n = out.shape[0]
        feats[cursor : cursor + n] = out.float().cpu().numpy().astype(np.float16)
        labels[cursor : cursor + n] = target.numpy()
        cursor += n

    elapsed = time.time() - started
    meta = {
        "backbone": spec.key,
        "timm_name": spec.timm_name,
        "split": split,
        "count": int(cursor),
        "dim": int(spec.dim),
        "image_size": int(cfg["input_size"][-1]),
        "flip_tta": bool(flip),
        "seconds": round(elapsed, 1),
        "images_per_second": round(cursor / max(elapsed, 1e-6), 2),
    }

    out_dir = FEATURE_DIR / spec.key
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / f"{split}_x.npy", feats)
    np.save(out_dir / f"{split}_y.npy", labels)
    (out_dir / f"{split}_meta.json").write_text(json.dumps(meta, indent=2))

    del model
    if DEVICE.type == "mps":
        torch.mps.empty_cache()
    return meta


def benchmark(keys: list[str], batch_size: int, image_size: int | None, n: int = 64) -> None:
    for key in keys:
        spec = BACKBONES[key]
        model, transform, cfg = build_backbone(spec, image_size)
        size = cfg["input_size"][-1]
        x = torch.randn(batch_size, 3, size, size, device=DEVICE)
        autocast = torch.autocast(device_type=DEVICE.type, dtype=torch.float16, enabled=DEVICE.type != "cpu")
        with torch.no_grad(), autocast:
            for _ in range(2):
                model(x)
            if DEVICE.type == "mps":
                torch.mps.synchronize()
            t0 = time.time()
            steps = max(1, n // batch_size)
            for _ in range(steps):
                model(x)
            if DEVICE.type == "mps":
                torch.mps.synchronize()
            dt = time.time() - t0
        ips = steps * batch_size / dt
        params = sum(p.numel() for p in model.parameters()) / 1e6
        eta = 101_000 / ips / 60
        print(f"{key:16s} {size}px  {params:7.1f}M  {ips:6.1f} img/s  full corpus ~{eta:.0f} min")
        del model, x
        if DEVICE.type == "mps":
            torch.mps.empty_cache()


def main() -> None:
    p = argparse.ArgumentParser(description="Build the frozen feature bank")
    p.add_argument("--backbones", nargs="+", default=list(BACKBONES))
    p.add_argument("--splits", nargs="+", default=["train", "test"])
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--image-size", type=int, default=None)
    p.add_argument("--flip", action="store_true", help="average features with the horizontal flip")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--benchmark", action="store_true")
    args = p.parse_args()

    unknown = set(args.backbones) - set(BACKBONES)
    if unknown:
        raise SystemExit(f"unknown backbones: {sorted(unknown)}")

    if args.benchmark:
        benchmark(args.backbones, args.batch_size, args.image_size)
        return

    for key in args.backbones:
        for split in args.splits:
            meta = extract(
                BACKBONES[key],
                split,
                args.batch_size,
                args.workers,
                args.image_size,
                args.flip,
                args.limit,
            )
            print(json.dumps(meta))


if __name__ == "__main__":
    main()
