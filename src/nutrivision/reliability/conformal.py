"""Split-conformal prediction sets over the shipping ensemble.

A top-1 label with a confidence attached is a claim about one image. A conformal
set is a claim about the procedure: over repeated use, the true class lands inside
the set at least (1 - alpha) of the time, and that holds without assuming anything
about the model, the architecture or the shape of the score distribution. The only
requirement is that calibration and test data are exchangeable.

That is why the guarantee is worth showing to a user. "94% confident" is a number
the model asserts about itself; "the right answer is in this set 95% of the time"
is a number we have measured and can be held to.

Two score functions are implemented because they trade off different things:

- **LAC** (least ambiguous set-valued classifier) uses 1 - p(true class). It gives
  the smallest average set size for a target coverage, but its coverage is only
  marginal — averaged over all inputs, easy and hard alike.
- **APS** (adaptive prediction sets) accumulates sorted probability mass until the
  true class is reached. Sets are larger, but they grow on genuinely ambiguous
  images and shrink on easy ones, which is the behaviour a user actually wants
  from an interface that shows the set.

Both calibrate on the held-out validation slice; the test split is only ever used
to report empirical coverage.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
from scipy.special import softmax

from nutrivision.config import REPORT_DIR

LOGIT_DIR = REPORT_DIR / "logits"

DEFAULT_MEMBERS = ["siglip_so400m", "eva02_large"]


def load_probs(members: list[str], split: str, temperature: float = 1.0) -> np.ndarray:
    """Probability average of the ensemble members, optionally temperature-scaled."""
    stack = []
    for name in members:
        logits = np.load(LOGIT_DIR / f"probe_{name}_{split}.npy").astype(np.float64)
        stack.append(softmax(logits / temperature, axis=1))
    return np.mean(stack, axis=0)


def load_labels(split: str) -> np.ndarray:
    return np.load(LOGIT_DIR / f"{split}_y.npy")


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """The finite-sample corrected quantile.

    The (n + 1) correction is not cosmetic: without it the guarantee holds only
    asymptotically, and at n = 3030 the difference is large enough to under-cover.
    """
    n = len(scores)
    level = np.ceil((n + 1) * (1 - alpha)) / n
    if level > 1:
        # Too few calibration points to certify this alpha at all.
        return float(scores.max())
    return float(np.quantile(scores, level, method="higher"))


# Calibration and deployment must apply the *identical* rule. Forcing the top-1
# class into the set at test time while scoring without it during calibration
# voids the guarantee — measured here as 99.1% empirical coverage against a 90%
# target, because the forced class silently rescued the ~13% of images whose top
# score exceeded qhat. Each score function below therefore takes the same
# force_top1 flag as its set constructor, and both must be passed the same value.


def lac_scores(probs: np.ndarray, y: np.ndarray, force_top1: bool = False) -> np.ndarray:
    scores = 1.0 - probs[np.arange(len(y)), y]
    if force_top1:
        # Under the forced rule the true class is covered for free whenever it is
        # already the argmax, so those points score zero.
        scores = np.where(probs.argmax(axis=1) == y, 0.0, scores)
    return scores


def aps_scores(
    probs: np.ndarray,
    y: np.ndarray,
    rng: np.random.Generator,
    force_top1: bool = False,
) -> np.ndarray:
    """Cumulative mass up to and including the true class, randomised.

    The uniform term breaks the discreteness of the cumulative sum; without it
    coverage overshoots the target and sets come out needlessly large.
    """
    order = np.argsort(-probs, axis=1)
    sorted_p = np.take_along_axis(probs, order, axis=1)
    cumulative = np.cumsum(sorted_p, axis=1)

    rank = np.argmax(order == y[:, None], axis=1)
    rows = np.arange(len(y))
    upto = cumulative[rows, rank]
    at_true = sorted_p[rows, rank]
    scores = upto - rng.uniform(size=len(y)) * at_true
    if force_top1:
        scores = np.where(rank == 0, 0.0, scores)
    return scores


def lac_sets(probs: np.ndarray, qhat: float, force_top1: bool = False) -> np.ndarray:
    sets = probs >= 1.0 - qhat
    if force_top1:
        sets[np.arange(len(probs)), probs.argmax(axis=1)] = True
    return sets


def aps_sets(
    probs: np.ndarray,
    qhat: float,
    rng: np.random.Generator,
    force_top1: bool = False,
) -> np.ndarray:
    order = np.argsort(-probs, axis=1)
    sorted_p = np.take_along_axis(probs, order, axis=1)
    cumulative = np.cumsum(sorted_p, axis=1)

    noise = rng.uniform(size=(len(probs), 1))
    include = (cumulative - noise * sorted_p) <= qhat
    if force_top1:
        include[:, 0] = True

    out = np.zeros_like(include)
    np.put_along_axis(out, order, include, axis=1)
    return out


def evaluate(sets: np.ndarray, y: np.ndarray) -> dict:
    sizes = sets.sum(axis=1)
    covered = sets[np.arange(len(y)), y]
    hist = {int(k): int(v) for k, v in zip(*np.unique(sizes, return_counts=True))}
    return {
        "coverage": round(float(covered.mean()) * 100, 3),
        "avg_set_size": round(float(sizes.mean()), 3),
        "median_set_size": int(np.median(sizes)),
        "max_set_size": int(sizes.max()),
        "singleton_rate": round(float((sizes == 1).mean()) * 100, 3),
        "empty_rate": round(float((sizes == 0).mean()) * 100, 3),
        "size_histogram": dict(sorted(hist.items())[:10]),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Split-conformal prediction sets")
    p.add_argument("--members", nargs="+", default=DEFAULT_MEMBERS)
    p.add_argument("--alphas", type=float, nargs="+", default=[0.10, 0.05, 0.01])
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--name", default="conformal")
    args = p.parse_args()

    rng = np.random.default_rng(args.seed)

    val_p = load_probs(args.members, "val", args.temperature)
    test_p = load_probs(args.members, "test", args.temperature)
    val_y, test_y = load_labels("val"), load_labels("test")

    results = []
    for alpha in args.alphas:
        row = {"alpha": alpha, "target_coverage": round((1 - alpha) * 100, 2)}
        for force in (False, True):
            suffix = "_top1" if force else ""

            lac_q = conformal_quantile(lac_scores(val_p, val_y, force), alpha)
            row[f"lac{suffix}"] = {
                "qhat": round(lac_q, 5),
                **evaluate(lac_sets(test_p, lac_q, force), test_y),
            }

            aps_q = conformal_quantile(aps_scores(val_p, val_y, rng, force), alpha)
            row[f"aps{suffix}"] = {
                "qhat": round(aps_q, 5),
                **evaluate(aps_sets(test_p, aps_q, rng, force), test_y),
            }
        results.append(row)

    report = {
        "members": args.members,
        "temperature": args.temperature,
        "calibration_samples": int(len(val_y)),
        "test_samples": int(len(test_y)),
        "results": results,
    }
    out = REPORT_DIR / f"{args.name}.json"
    out.write_text(json.dumps(report, indent=2))

    print(f"calibration n={len(val_y)}   test n={len(test_y)}   members={'+'.join(args.members)}\n")
    header = (
        f"{'target':>7}  {'method':<9}  {'coverage':>9}  {'avg size':>9}  "
        f"{'singletons':>11}  {'empty':>7}  {'max':>4}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        for method in ("lac", "aps", "lac_top1", "aps_top1"):
            m = r[method]
            print(
                f"{r['target_coverage']:6.1f}%  {method.upper():<9}  {m['coverage']:8.2f}%  "
                f"{m['avg_set_size']:9.3f}  {m['singleton_rate']:10.1f}%  "
                f"{m['empty_rate']:6.1f}%  {m['max_set_size']:4d}"
            )
        print()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
