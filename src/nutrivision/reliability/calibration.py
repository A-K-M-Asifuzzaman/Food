"""Confidence calibration for the classifier heads."""

from __future__ import annotations

import argparse
import json

import numpy as np
import torch
import torch.nn.functional as F

from nutrivision.config import REPORT_DIR

LOGIT_DIR = REPORT_DIR / "logits"


def load(name: str, split: str) -> tuple[torch.Tensor, torch.Tensor]:
    logits = np.load(LOGIT_DIR / f"probe_{name}_{split}.npy")
    y = np.load(LOGIT_DIR / f"{split}_y.npy")
    return torch.from_numpy(logits).float(), torch.from_numpy(y).long()


def expected_calibration_error(
    probs: torch.Tensor, y: torch.Tensor, bins: int = 15
) -> tuple[float, float, list[dict]]:
    """ECE and MCE over equal-width confidence bins."""
    conf, pred = probs.max(dim=-1)
    correct = pred.eq(y).float()

    edges = torch.linspace(0, 1, bins + 1)
    ece = 0.0
    mce = 0.0
    table = []
    n = len(y)
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (conf > lo) & (conf <= hi)
        count = int(mask.sum())
        if count == 0:
            continue
        acc = float(correct[mask].mean())
        avg_conf = float(conf[mask].mean())
        gap = abs(avg_conf - acc)
        ece += (count / n) * gap
        mce = max(mce, gap)
        table.append(
            {
                "bin": f"({lo:.2f}, {hi:.2f}]",
                "count": count,
                "confidence": round(avg_conf, 4),
                "accuracy": round(acc, 4),
                "gap": round(avg_conf - acc, 4),
            }
        )
    return ece, mce, table


def brier(probs: torch.Tensor, y: torch.Tensor) -> float:
    onehot = F.one_hot(y, probs.shape[-1]).float()
    return float(((probs - onehot) ** 2).sum(dim=-1).mean())


def negative_log_likelihood(logits: torch.Tensor, y: torch.Tensor) -> float:
    return float(F.cross_entropy(logits, y))


def fit_temperature(logits: torch.Tensor, y: torch.Tensor, max_iter: int = 200) -> float:
    """Optimise a single scalar T minimising NLL on the validation split."""
    log_t = torch.zeros(1, requires_grad=True)  # optimise in log space to keep T > 0
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=max_iter)

    def closure():
        opt.zero_grad()
        loss = F.cross_entropy(logits / log_t.exp(), y)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.exp().item())


def summarise(logits: torch.Tensor, y: torch.Tensor, bins: int) -> dict:
    probs = logits.softmax(dim=-1)
    ece, mce, table = expected_calibration_error(probs, y, bins)
    pred = probs.argmax(dim=-1)
    return {
        "top1": round(float(pred.eq(y).float().mean()) * 100, 3),
        "ece": round(ece, 5),
        "mce": round(mce, 5),
        "brier": round(brier(probs, y), 5),
        "nll": round(negative_log_likelihood(logits, y), 5),
        "mean_confidence": round(float(probs.max(dim=-1).values.mean()), 5),
        "bins": table,
    }


def load_ensemble(members: list[str], split: str) -> tuple[torch.Tensor, torch.Tensor]:
    """Surrogate logits for a probability-averaged ensemble."""
    probs = None
    y = None
    for name in members:
        logits, y = load(name, split)
        p = logits.softmax(dim=-1)
        probs = p if probs is None else probs + p
    assert probs is not None and y is not None
    return (probs / len(members)).clamp_min(1e-12).log(), y


def main() -> None:
    ap = argparse.ArgumentParser(description="Calibrate a trained head or ensemble")
    ap.add_argument("--name", required=True, help="head name, or a label for --members")
    ap.add_argument(
        "--members",
        nargs="+",
        default=None,
        help="calibrate the probability average of these heads instead of one head",
    )
    ap.add_argument("--bins", type=int, default=15)
    args = ap.parse_args()

    if args.members:
        val_logits, val_y = load_ensemble(args.members, "val")
        test_logits, test_y = load_ensemble(args.members, "test")
    else:
        val_logits, val_y = load(args.name, "val")
        test_logits, test_y = load(args.name, "test")

    temperature = fit_temperature(val_logits, val_y)

    before = summarise(test_logits, test_y, args.bins)
    after = summarise(test_logits / temperature, test_y, args.bins)

    result = {
        "name": args.name,
        "members": args.members,
        "temperature": round(temperature, 4),
        "val_samples": int(len(val_y)),
        "test_samples": int(len(test_y)),
        "test_before": before,
        "test_after": after,
    }
    out = REPORT_DIR / f"calibration_{args.name}.json"
    out.write_text(json.dumps(result, indent=2))

    print(f"head          {args.name}")
    print(f"temperature   {temperature:.4f}   (fitted on {len(val_y)} validation samples)")
    print()
    print(f"{'metric':18s} {'before':>10s} {'after':>10s}")
    print("-" * 40)
    for key in ("top1", "ece", "mce", "brier", "nll", "mean_confidence"):
        print(f"{key:18s} {before[key]:10.5f} {after[key]:10.5f}")
    print()
    print(f"written to    {out}")


if __name__ == "__main__":
    main()
