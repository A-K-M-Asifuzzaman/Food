from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from nutrivision.config import (
    CHECKPOINT_DIR,
    DEVICE,
    FEATURE_DIR,
    NUM_CLASSES,
    REPORT_DIR,
    SEED,
)
from nutrivision.data.dataset import holdout_mask, load_classes
from nutrivision.models.heads import (
    GatedFusionProbe,
    MLPProbe,
    mixup_features,
    soft_target_cross_entropy,
)


def load_features(backbones: list[str], split: str) -> tuple[list[np.ndarray], np.ndarray]:
    xs, y_ref = [], None
    for key in backbones:
        d = FEATURE_DIR / key
        x = np.load(d / f"{split}_x.npy")
        y = np.load(d / f"{split}_y.npy")
        if y_ref is None:
            y_ref = y
        elif not np.array_equal(y_ref, y):
            raise RuntimeError(f"label order mismatch between backbones for split {split}")
        xs.append(x)
    return xs, y_ref


def to_tensor(x: np.ndarray) -> torch.Tensor:
    t = torch.from_numpy(x).float()
    return F.normalize(t, dim=-1)


@torch.no_grad()
def evaluate(model, xs: list[torch.Tensor], y: torch.Tensor, batch: int = 1024):
    model.eval()
    logits = []
    for i in range(0, xs[0].shape[0], batch):
        chunk = [x[i : i + batch].to(DEVICE) for x in xs]
        out = model(chunk) if len(chunk) > 1 else model(chunk[0])
        logits.append(out.float().cpu())
    logits = torch.cat(logits)
    pred = logits.argmax(dim=-1)
    top5 = logits.topk(5, dim=-1).indices
    acc1 = (pred == y).float().mean().item()
    acc5 = (top5 == y.unsqueeze(1)).any(dim=1).float().mean().item()
    return acc1, acc5, logits


def train(args) -> dict:
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    classes = load_classes()
    train_xs_np, train_y_np = load_features(args.backbones, "train")
    test_xs_np, test_y_np = load_features(args.backbones, "test")

    is_val = holdout_mask(train_y_np, NUM_CLASSES, args.val_fraction, SEED)
    tr_xs = [to_tensor(x[~is_val]) for x in train_xs_np]
    va_xs = [to_tensor(x[is_val]) for x in train_xs_np]
    te_xs = [to_tensor(x) for x in test_xs_np]
    tr_y = torch.from_numpy(train_y_np[~is_val])
    va_y = torch.from_numpy(train_y_np[is_val])
    te_y = torch.from_numpy(test_y_np)

    dims = [x.shape[1] for x in tr_xs]
    single = len(dims) == 1
    if single:
        model = MLPProbe(dims[0], NUM_CLASSES, args.hidden, args.dropout).to(DEVICE)
    else:
        model = GatedFusionProbe(dims, NUM_CLASSES, args.proj, args.hidden, args.dropout).to(DEVICE)

    params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    n = tr_xs[0].shape[0]
    steps_per_epoch = math.ceil(n / args.batch_size)
    total_steps = steps_per_epoch * args.epochs
    warmup = max(1, int(0.05 * total_steps))

    def lr_at(step: int) -> float:
        if step < warmup:
            return step / warmup
        p = (step - warmup) / max(1, total_steps - warmup)
        return 0.5 * (1 + math.cos(math.pi * p))

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_at)

    tag = args.name or "+".join(args.backbones)
    best = {"val_acc1": 0.0}
    step = 0
    started = time.time()

    for epoch in range(args.epochs):
        model.train()
        perm = torch.randperm(n)
        running = 0.0
        for i in range(0, n, args.batch_size):
            idx = perm[i : i + args.batch_size]
            xb = [x[idx].to(DEVICE) for x in tr_xs]
            yb = tr_y[idx].to(DEVICE)

            if single:
                xm, tm = mixup_features(xb[0], yb, NUM_CLASSES, args.mixup, args.label_smoothing)
                logits = model(xm)
            else:
                lam_seed = torch.randperm(xb[0].size(0), device=DEVICE)
                lam = (
                    float(torch.distributions.Beta(args.mixup, args.mixup).sample())
                    if args.mixup > 0
                    else 1.0
                )
                xm = [lam * x + (1 - lam) * x[lam_seed] for x in xb]
                off = args.label_smoothing / NUM_CLASSES
                base = torch.full((yb.size(0), NUM_CLASSES), off, device=DEVICE)
                base.scatter_(1, yb.unsqueeze(1), 1.0 - args.label_smoothing + off)
                tm = lam * base + (1 - lam) * base[lam_seed]
                logits = model(xm)

            loss = soft_target_cross_entropy(logits, tm)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            running += loss.item()
            step += 1

        val1, val5, _ = evaluate(model, va_xs, va_y)
        if val1 > best["val_acc1"]:
            best = {"val_acc1": val1, "val_acc5": val5, "epoch": epoch}
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "backbones": args.backbones,
                    "dims": dims,
                    "arch": "mlp" if single else "gated_fusion",
                    "hidden": args.hidden,
                    "proj": args.proj,
                    "dropout": args.dropout,
                },
                CHECKPOINT_DIR / f"probe_{tag}.pt",
            )
        print(
            f"epoch {epoch + 1:2d}/{args.epochs}  loss {running / steps_per_epoch:.4f}  "
            f"val top1 {val1 * 100:.2f}  top5 {val5 * 100:.2f}"
        )

    ckpt = torch.load(CHECKPOINT_DIR / f"probe_{tag}.pt", map_location=DEVICE, weights_only=False)
    model.load_state_dict(ckpt["state_dict"])
    test1, test5, test_logits = evaluate(model, te_xs, te_y)

    logit_dir = REPORT_DIR / "logits"
    logit_dir.mkdir(parents=True, exist_ok=True)
    np.save(logit_dir / f"probe_{tag}_test.npy", test_logits.numpy().astype(np.float32))
    _, _, val_logits = evaluate(model, va_xs, va_y)
    np.save(logit_dir / f"probe_{tag}_val.npy", val_logits.numpy().astype(np.float32))
    np.save(logit_dir / "val_y.npy", va_y.numpy())
    np.save(logit_dir / "test_y.npy", te_y.numpy())

    result = {
        "name": tag,
        "backbones": args.backbones,
        "arch": "mlp" if single else "gated_fusion",
        "params": params,
        "train_samples": int(n),
        "val_top1": round(best["val_acc1"] * 100, 3),
        "val_top5": round(best.get("val_acc5", 0) * 100, 3),
        "test_top1": round(test1 * 100, 3),
        "test_top5": round(test5 * 100, 3),
        "best_epoch": best.get("epoch"),
        "minutes": round((time.time() - started) / 60, 2),
        "num_classes": len(classes),
    }
    out = REPORT_DIR / f"probe_{tag}.json"
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="Train a head on cached features")
    p.add_argument("--backbones", nargs="+", required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--lr", type=float, default=2e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--hidden", type=int, default=1536)
    p.add_argument("--proj", type=int, default=1024)
    p.add_argument("--dropout", type=float, default=0.3)
    p.add_argument("--mixup", type=float, default=0.4)
    p.add_argument("--label-smoothing", type=float, default=0.1)
    p.add_argument("--val-fraction", type=float, default=0.04)
    train(p.parse_args())


if __name__ == "__main__":
    main()
