"""Compute the classification metrics the course report asks for."""

from __future__ import annotations

import json

import numpy as np
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from nutrivision.config import REPORT_DIR
from nutrivision.data.dataset import load_classes

LOGITS = REPORT_DIR / "logits"
MEMBERS = ["siglip_so400m", "eva02_large"]


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def main() -> None:
    classes = load_classes()
    y = np.load(LOGITS / "test_y.npy")

    # The shipping model: a uniform probability average over the two members.
    probs = np.mean([softmax(np.load(LOGITS / f"probe_{m}_test.npy")) for m in MEMBERS], axis=0)
    pred = probs.argmax(1)

    top5 = np.argsort(-probs, axis=1)[:, :5]
    acc1 = float((pred == y).mean())
    acc5 = float((top5 == y[:, None]).any(1).mean())

    out: dict = {
        "model": "ensemble: " + " + ".join(MEMBERS) + " (uniform probability average)",
        "n_test": int(len(y)),
        "num_classes": len(classes),
        "accuracy": round(acc1 * 100, 3),
        "top5_accuracy": round(acc5 * 100, 3),
        "macro": {
            "precision": round(precision_score(y, pred, average="macro", zero_division=0) * 100, 3),
            "recall": round(recall_score(y, pred, average="macro", zero_division=0) * 100, 3),
            "f1": round(f1_score(y, pred, average="macro", zero_division=0) * 100, 3),
        },
        "weighted": {
            "precision": round(precision_score(y, pred, average="weighted", zero_division=0) * 100, 3),
            "recall": round(recall_score(y, pred, average="weighted", zero_division=0) * 100, 3),
            "f1": round(f1_score(y, pred, average="weighted", zero_division=0) * 100, 3),
        },
    }

    # Per-class accuracy.
    cm = confusion_matrix(y, pred, labels=range(len(classes)))
    per_class = cm.diagonal() / cm.sum(axis=1)
    order = np.argsort(per_class)
    out["worst_classes"] = [
        {"class": classes[i], "accuracy": round(float(per_class[i]) * 100, 1),
         "n": int(cm[i].sum())}
        for i in order[:12]
    ]
    out["best_classes"] = [
        {"class": classes[i], "accuracy": round(float(per_class[i]) * 100, 1)}
        for i in order[::-1][:8]
    ]

    # The pairs the model actually confuses, which is what error analysis needs.
    off = cm.copy()
    np.fill_diagonal(off, 0)
    pairs = []
    for a, b in zip(*np.unravel_index(np.argsort(-off, axis=None)[:20], off.shape)):
        pairs.append({
            "true": classes[a], "predicted": classes[b],
            "count": int(off[a, b]),
            "pct_of_class": round(off[a, b] / cm[a].sum() * 100, 1),
        })
    out["top_confusions"] = pairs

    per_class_report = classification_report(
        y, pred, target_names=classes, output_dict=True, zero_division=0
    )
    (REPORT_DIR / "per_class_metrics.json").write_text(json.dumps(per_class_report, indent=1))
    np.save(REPORT_DIR / "confusion_matrix.npy", cm)
    (REPORT_DIR / "report_metrics.json").write_text(json.dumps(out, indent=2))

    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("worst_classes", "best_classes", "top_confusions")}, indent=2))
    print("\nworst 6 classes:")
    for r in out["worst_classes"][:6]:
        print(f"  {r['class']:26s} {r['accuracy']:5.1f}%")
    print("\ntop 6 confusions:")
    for r in out["top_confusions"][:6]:
        print(f"  {r['true']:22s} -> {r['predicted']:22s} {r['count']:3d}  ({r['pct_of_class']}%)")


if __name__ == "__main__":
    main()
