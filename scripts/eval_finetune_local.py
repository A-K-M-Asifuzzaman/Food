from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import timm
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

from nutrivision.config import CHECKPOINT_DIR, DEVICE, IMAGE_DIR, NUM_CLASSES, REPORT_DIR, SEED
from nutrivision.data.dataset import holdout_mask, load_classes

BACKBONE = "eva02_large_patch14_448.mim_m38m_ft_in22k_in1k"


class Folder(Dataset):
    def __init__(self, paths, labels, transform):
        self.paths, self.labels, self.transform = paths, labels, transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        return self.transform(Image.open(self.paths[i]).convert("RGB")), int(self.labels[i])


def build_lists(classes: list[str], val_fraction: float):
    train_paths, train_labels = [], []
    for label, cls in enumerate(classes):
        for p in sorted((IMAGE_DIR / "train" / cls).glob("*.jpg")):
            train_paths.append(p)
            train_labels.append(label)
    test_paths, test_labels = [], []
    for label, cls in enumerate(classes):
        for p in sorted((IMAGE_DIR / "test" / cls).glob("*.jpg")):
            test_paths.append(p)
            test_labels.append(label)

    train_labels = np.array(train_labels)
    is_val = holdout_mask(train_labels, len(classes), val_fraction, SEED)
    val_paths = [p for p, v in zip(train_paths, is_val, strict=True) if v]
    return val_paths, train_labels[is_val], test_paths, np.array(test_labels)


@torch.no_grad()
def infer(model, loader) -> np.ndarray:
    model.eval()
    out = []
    for x, _ in tqdm(loader, unit="batch"):
        x = x.to(DEVICE, non_blocking=True)
        with torch.autocast(DEVICE.type, dtype=torch.float16):
            out.append(model(x).float().cpu())
    return torch.cat(out).numpy().astype(np.float32)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Evaluate a fine-tune checkpoint on the held-out splits and export its logits."
    )
    p.add_argument("--checkpoint", default=str(CHECKPOINT_DIR / "eva02_large_448_last.pt"))
    p.add_argument("--name", default="eva02_ft_s1", help="logit file stem")
    p.add_argument("--size", type=int, default=224, help="must match the stage the checkpoint ended on")
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--weights", choices=["model", "ema", "auto"], default="auto")
    args = p.parse_args()

    ck = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    history = ck.get("history", [])
    last = history[-1] if history else {}
    print(f"checkpoint : stage={ck.get('stage')} epoch={ck.get('epoch')}")
    print(f"last epoch : val {last.get('val_top1')}  ema {last.get('ema_top1')}")

    choice = args.weights
    if choice == "auto":
        choice = "ema" if (last.get("ema_top1") or 0) > (last.get("val_top1") or 0) else "model"
    print(f"using      : {choice} weights at {args.size}px")

    classes = load_classes()
    model = timm.create_model(
        BACKBONE, pretrained=False, num_classes=NUM_CLASSES, img_size=args.size
    )
    model.load_state_dict(ck[choice])
    model.to(DEVICE)

    transform = timm.data.create_transform(
        input_size=(3, args.size, args.size),
        is_training=False,
        interpolation="bicubic",
        crop_pct=1.0,
        mean=timm.data.IMAGENET_DEFAULT_MEAN,
        std=timm.data.IMAGENET_DEFAULT_STD,
    )

    val_paths, val_y, test_paths, test_y = build_lists(classes, 0.04)
    print(f"val {len(val_paths)}  test {len(test_paths)}")

    kw = dict(batch_size=args.batch_size, num_workers=args.workers, pin_memory=True)
    started = time.time()

    print("\nvalidation")
    val_logits = infer(model, DataLoader(Folder(val_paths, val_y, transform), **kw))
    val_acc = float((val_logits.argmax(1) == val_y).mean() * 100)
    print(f"  val top-1 {val_acc:.3f}   (checkpoint reported {last.get('val_top1')})")

    print("\ntest")
    test_logits = infer(model, DataLoader(Folder(test_paths, test_y, transform), **kw))
    test_acc = float((test_logits.argmax(1) == test_y).mean() * 100)
    top5 = float(
        (np.argsort(-test_logits, 1)[:, :5] == test_y[:, None]).any(1).mean() * 100
    )

    out = REPORT_DIR / "logits"
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / f"probe_{args.name}_val.npy", val_logits)
    np.save(out / f"probe_{args.name}_test.npy", test_logits)

    result = {
        "name": args.name,
        "checkpoint": Path(args.checkpoint).name,
        "stage": ck.get("stage"),
        "epoch": ck.get("epoch"),
        "weights": choice,
        "image_size": args.size,
        "val_top1": round(val_acc, 3),
        "test_top1": round(test_acc, 3),
        "test_top5": round(top5, 3),
        "minutes": round((time.time() - started) / 60, 2),
        "history": history,
    }
    (REPORT_DIR / f"{args.name}_result.json").write_text(json.dumps(result, indent=2))

    print(f"\nTEST top-1 {test_acc:.3f}   top-5 {top5:.3f}")
    print("frozen ensemble is 97.156 — that is the bar")
    print(f"\nwrote logits as probe_{args.name}_{{val,test}}.npy")


if __name__ == "__main__":
    main()
