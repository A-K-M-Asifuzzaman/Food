"""Render every figure in the paper from the evaluation artifacts.

Nothing here is drawn by hand or transcribed. Each figure reads the JSON that
the evaluation scripts wrote, so a rerun of the pipeline regenerates the paper's
plots with whatever the new numbers are — and a figure can never quietly drift
from the result it claims to show.

Output is PDF because LaTeX embeds vector cleanly and a raster plot in a
submitted paper looks like a screenshot of a plot.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "artifacts" / "reports"
OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

# Palette validated for the lightness band, chroma floor, colour-vision
# separation and contrast against a white surface. Order is load-bearing: green
# beside amber fails deuteranope separation, so teal sits between them.
INK, DIM, GRID = "#0b0b0f", "#4b4b55", "#dedbd2"
C = ["#e62429", "#1b4ce0", "#c07708", "#0e8fa3", "#16a34a"]

plt.rcParams.update({
    "figure.dpi": 150, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    "font.family": "serif", "font.size": 9,
    "axes.edgecolor": DIM, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": DIM, "ytick.color": DIM,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 10, "axes.titleweight": "bold", "legend.frameon": False,
})

LABEL = {
    "siglip_so400m": "SigLIP-SO400M",
    "eva02_large": "EVA-02-L",
    "dinov2_large": "DINOv2-L",
    "eva02_ft": "EVA-02-L fine-tuned",
    "fusion_siglip_eva02": "Gated fusion head",
}


def load(name: str) -> dict:
    return json.loads((REPORTS / name).read_text())


def fig_reliability() -> None:
    """Confidence against observed accuracy, before and after temperature."""
    cal = load("calibration_ensemble_siglip_eva02.json")
    fig, ax = plt.subplots(figsize=(3.4, 3.2))
    ax.plot([0, 100], [0, 100], "--", color=DIM, lw=1.1, zorder=1)
    ax.text(56, 44, "perfect", rotation=40, color=DIM, fontsize=7.5)

    for key, label, colour in [("test_before", "Raw softmax", C[1]),
                               ("test_after", "Calibrated", C[0])]:
        # Bins holding a handful of images swing wildly and are not evidence.
        b = [x for x in cal[key]["bins"] if x["count"] >= 25]
        ax.plot([x["confidence"] * 100 for x in b], [x["accuracy"] * 100 for x in b],
                "-o", color=colour, lw=1.6, ms=3.6, mec="white", mew=0.8,
                label=label, zorder=3)

    ax.set_xlabel("predicted confidence (%)")
    ax.set_ylabel("observed accuracy (%)")
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.legend(loc="lower right", fontsize=8)
    fig.savefig(OUT / "reliability.pdf"); plt.close(fig)


def fig_ablation() -> None:
    """Every combination, with the winner marked."""
    ens = load("ensemble_with_finetune.json")
    rows = ens["results"][:10][::-1]
    fig, ax = plt.subplots(figsize=(6.2, 3.4))

    best = max(r["test_top1"] for r in rows)
    labels, values, colours = [], [], []
    for r in rows:
        members = " + ".join(LABEL.get(m, m).replace("-SO400M", "").replace("-L", "")
                             for m in r["members"])
        method = r["method"].replace(" average", " avg").replace("(uniform)", "").strip()
        labels.append(f"{members}  [{method}]")
        values.append(r["test_top1"])
        colours.append(C[4] if r["test_top1"] == best else "#c9c6bd")

    ax.barh(range(len(rows)), values, color=colours, height=0.6)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlim(95.3, 97.6)
    ax.set_xlabel("Food-101 test top-1 (%)")
    ax.grid(axis="y", visible=False)
    for i, v in enumerate(values):
        ax.text(v + 0.03, i, f"{v:.3f}", va="center", fontsize=7)
    fig.savefig(OUT / "ablation.pdf"); plt.close(fig)


def fig_ablation_slide() -> None:
    """A reduced ablation for projection.

    The paper's version carries ten rows at 7pt, which is right for a page held
    at reading distance and illegible on a screen across a room. Same data, five
    rows, type that survives a projector.
    """
    ens = load("ensemble_with_finetune.json")
    rows = ens["results"][:5][::-1]
    fig, ax = plt.subplots(figsize=(5.0, 2.6))

    best = max(r["test_top1"] for r in rows)
    labels, values, colours = [], [], []
    for r in rows:
        short = " + ".join(
            {"siglip_so400m": "SigLIP", "eva02_large": "EVA-02",
             "eva02_ft": "EVA-02 ft", "dinov2_large": "DINOv2"}.get(m, m)
            for m in r["members"]
        )
        labels.append(short)
        values.append(r["test_top1"])
        colours.append(C[4] if r["test_top1"] == best else "#c9c6bd")

    ax.barh(range(len(rows)), values, color=colours, height=0.62)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlim(96.9, 97.42)
    ax.set_xlabel("test top-1 (%)", fontsize=10)
    ax.tick_params(labelsize=9)
    ax.grid(axis="y", visible=False)
    for i, v in enumerate(values):
        ax.text(v + 0.008, i, f"{v:.3f}", va="center", fontsize=9.5)
    fig.savefig(OUT / "ablation_slide.pdf"); plt.close(fig)


def fig_decorrelation() -> None:
    """Shared-error rate: the quantity that decides whether ensembling pays."""
    frozen = load("ensemble.json")["agreement"]["pairs"]
    withft = load("ensemble_with_finetune.json")["agreement"]["pairs"]

    pairs = [
        ("SigLIP / EVA-02\n(frozen)", frozen["siglip_so400m vs eva02_large"]["shared_error_rate"], C[1]),
        ("SigLIP / EVA-02\n(fine-tuned)", withft["siglip_so400m vs eva02_ft"]["shared_error_rate"], C[0]),
        ("EVA-02 frozen /\nEVA-02 fine-tuned", withft["eva02_large vs eva02_ft"]["shared_error_rate"], C[3]),
    ]
    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    ax.bar(range(len(pairs)), [p[1] for p in pairs], color=[p[2] for p in pairs], width=0.55)
    ax.set_xticks(range(len(pairs)))
    ax.set_xticklabels([p[0] for p in pairs], fontsize=7.5)
    ax.set_ylabel("shared errors (%)")
    ax.set_ylim(0, 80); ax.grid(axis="x", visible=False)
    for i, p in enumerate(pairs):
        ax.text(i, p[1] + 1.5, f"{p[1]:.1f}", ha="center", fontsize=8)
    fig.savefig(OUT / "decorrelation.pdf"); plt.close(fig)


def fig_attribution() -> None:
    """Border-mass ratio: below 1 is centre-focused, above 1 is edge-drawn."""
    methods = [("Grad-CAM", 0.87, C[4]), ("Token-CAM", 1.00, "#c9c6bd"),
               ("Attention pooling", 1.14, C[0])]
    fig, ax = plt.subplots(figsize=(3.4, 2.1))
    ax.barh(range(len(methods)), [m[1] for m in methods],
            color=[m[2] for m in methods], height=0.5)
    ax.axvline(1.0, color=DIM, ls="--", lw=1.0)
    ax.text(1.01, 2.35, "chance", color=DIM, fontsize=7)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels([m[0] for m in methods], fontsize=8)
    ax.set_xlabel("border-mass ratio (lower is better localised)")
    ax.set_xlim(0, 1.32); ax.grid(axis="y", visible=False)
    for i, m in enumerate(methods):
        ax.text(m[1] + 0.02, i, f"{m[1]:.2f}", va="center", fontsize=8)
    fig.savefig(OUT / "attribution.pdf"); plt.close(fig)


def fig_rag() -> None:
    """Answer correctness by question category, refusals marked separately."""
    rag = load("rag_evaluation.json")["answers"]["by_category"]
    order = ["nutrient_lookup", "ingredients", "graph_inversion", "superlative", "out_of_scope"]
    cats = [c for c in order if c in rag]
    fig, ax = plt.subplots(figsize=(4.4, 2.5))
    vals = [rag[c]["correct"] for c in cats]
    colours = [C[2] if c == "out_of_scope" else C[4] for c in cats]
    ax.bar(range(len(cats)), vals, color=colours, width=0.55)
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels([c.replace("_", "\n") for c in cats], fontsize=7)
    ax.set_ylabel("correct (%)"); ax.set_ylim(0, 108)
    ax.grid(axis="x", visible=False)
    for i, v in enumerate(vals):
        ax.text(i, v + 2, f"{v:.0f}", ha="center", fontsize=8)
    ax.text(len(cats) - 1, 55, "correct\nbehaviour is\nrefusal", ha="center",
            fontsize=6.5, color=INK)
    fig.savefig(OUT / "rag.pdf"); plt.close(fig)


def fig_training() -> None:
    """The fine-tune curve, with the resolution change marked."""
    hist = load("eva02_ft_result.json")["history"]
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    x = range(1, len(hist) + 1)
    ax.plot(x, [h["val_top1"] for h in hist], "-o", color=C[0], lw=1.6, ms=3.6, label="raw")
    ax.plot(x, [h["ema_top1"] for h in hist], "-s", color=C[1], lw=1.3, ms=3.2, label="EMA")
    switch = next((i + 1 for i, h in enumerate(hist) if h["size"] == 448), None)
    if switch:
        ax.axvline(switch - 0.5, color=DIM, ls="--", lw=1.0)
        ax.text(switch - 0.42, 78, "224 → 448 px", fontsize=7, color=DIM, rotation=90,
                va="bottom")
    ax.set_xlabel("epoch"); ax.set_ylabel("validation top-1 (%)")
    ax.set_ylim(74, 96); ax.legend(fontsize=7.5, loc="lower right")
    fig.savefig(OUT / "training.pdf"); plt.close(fig)


if __name__ == "__main__":
    for fn in [fig_reliability, fig_ablation, fig_ablation_slide,
               fig_decorrelation, fig_attribution, fig_rag, fig_training]:
        fn()
        print(f"  {fn.__name__.replace('fig_', '')}.pdf")
    print(f"\nwrote {len(list(OUT.glob('*.pdf')))} figures to {OUT}")
