from __future__ import annotations

import argparse
import itertools
import json

import numpy as np
from scipy.special import softmax
from scipy.stats import binomtest

from nutrivision.config import REPORT_DIR

DEFAULT_MEMBERS = ["siglip_so400m", "eva02_large", "dinov2_large"]


def load_logits(tag: str, split: str) -> np.ndarray:
    path = REPORT_DIR / "logits" / f"probe_{tag}_{split}.npy"
    if not path.exists():
        raise FileNotFoundError(f"no cached logits for '{tag}' ({split}) — train that probe first")
    return np.load(path).astype(np.float64)


def load_labels(split: str) -> np.ndarray:
    return np.load(REPORT_DIR / "logits" / f"{split}_y.npy")


def top1(pred: np.ndarray, y: np.ndarray) -> float:
    return float((pred == y).mean() * 100)


def top5(scores: np.ndarray, y: np.ndarray) -> float:
    top = np.argpartition(-scores, 5, axis=1)[:, :5]
    return float((top == y[:, None]).any(axis=1).mean() * 100)


def combine(members: list[np.ndarray], weights: np.ndarray, space: str) -> np.ndarray:
    parts = [softmax(m, axis=1) if space == "prob" else m for m in members]
    return sum(w * p for w, p in zip(weights, parts))


def mcnemar(a_correct: np.ndarray, b_correct: np.ndarray) -> dict:
    b = int((a_correct & ~b_correct).sum())
    c = int((~a_correct & b_correct).sum())
    if b + c == 0:
        return {"a_only": 0, "b_only": 0, "p": 1.0, "significant": False}
    p = float(binomtest(b, b + c, 0.5).pvalue)
    return {"a_only": b, "b_only": c, "p": round(p, 6), "significant": p < 0.05}


def simplex_grid(k: int, step: float = 0.05) -> list[np.ndarray]:
    ticks = int(round(1 / step))
    out = []
    for cut in itertools.combinations(range(ticks + k - 1), k - 1):
        prev, w = -1, []
        for c in cut:
            w.append(c - prev - 1)
            prev = c
        w.append(ticks + k - 2 - prev)
        out.append(np.array(w, dtype=float) / ticks)
    return out


def evaluate_subsets(tags: list[str], val: dict, test: dict, val_y, test_y) -> list[dict]:
    rows = []
    for size in range(1, len(tags) + 1):
        for subset in itertools.combinations(tags, size):
            members_test = [test[t] for t in subset]
            uniform = np.full(len(subset), 1 / len(subset))
            for space in ("prob", "logit") if size > 1 else ("prob",):
                scores = combine(members_test, uniform, space)
                rows.append(
                    {
                        "members": list(subset),
                        "method": "solo" if size == 1 else f"{space} average (uniform)",
                        "weights": [round(w, 3) for w in uniform],
                        "test_top1": round(top1(scores.argmax(1), test_y), 3),
                        "test_top5": round(top5(scores, test_y), 3),
                    }
                )
            if size > 1:
                members_val = [val[t] for t in subset]
                best_w, best_acc = None, -1.0
                for w in simplex_grid(size):
                    acc = top1(combine(members_val, w, "prob").argmax(1), val_y)
                    if acc > best_acc:
                        best_w, best_acc = w, acc
                scores = combine(members_test, best_w, "prob")
                rows.append(
                    {
                        "members": list(subset),
                        "method": "prob average (val-tuned)",
                        "weights": [round(float(w), 3) for w in best_w],
                        "val_top1": round(best_acc, 3),
                        "test_top1": round(top1(scores.argmax(1), test_y), 3),
                        "test_top5": round(top5(scores, test_y), 3),
                    }
                )
    return rows


def agreement(tags: list[str], test: dict, test_y) -> dict:
    correct = {t: test[t].argmax(1) == test_y for t in tags}
    oracle = np.zeros_like(test_y, dtype=bool)
    for c in correct.values():
        oracle |= c
    pairs = {}
    for a, b in itertools.combinations(tags, 2):
        wrong_a, wrong_b = ~correct[a], ~correct[b]
        shared = int((wrong_a & wrong_b).sum())
        pairs[f"{a} vs {b}"] = {
            "both_correct": round(float((correct[a] & correct[b]).mean() * 100), 3),
            "only_first": round(float((correct[a] & wrong_b).mean() * 100), 3),
            "only_second": round(float((wrong_a & correct[b]).mean() * 100), 3),
            "both_wrong": round(float((wrong_a & wrong_b).mean() * 100), 3),
            "shared_error_rate": round(shared / max(1, int(wrong_a.sum())) * 100, 3),
        }
    return {
        "oracle_top1": round(float(oracle.mean() * 100), 3),
        "all_wrong": round(float((~oracle).mean() * 100), 3),
        "pairs": pairs,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Ensemble cached probe logits")
    p.add_argument("--members", nargs="+", default=DEFAULT_MEMBERS)
    p.add_argument("--name", default="ensemble")
    args = p.parse_args()

    tags = args.members
    val_y, test_y = load_labels("val"), load_labels("test")
    val = {t: load_logits(t, "val") for t in tags}
    test = {t: load_logits(t, "test") for t in tags}

    rows = evaluate_subsets(tags, val, test, val_y, test_y)
    rows.sort(key=lambda r: r["test_top1"], reverse=True)

    best = rows[0]
    best_solo = max((r for r in rows if r["method"] == "solo"), key=lambda r: r["test_top1"])
    best_scores = combine(
        [test[t] for t in best["members"]],
        np.array(best["weights"]),
        "logit" if "logit" in best["method"] else "prob",
    )
    solo_scores = test[best_solo["members"][0]]
    tests = {
        f"{best['method']} {'+'.join(best['members'])} vs best solo {best_solo['members'][0]}": (
            mcnemar(best_scores.argmax(1) == test_y, solo_scores.argmax(1) == test_y)
        )
    }

    full_uniform = [r for r in rows if len(r["members"]) == len(tags) and "uniform" in r["method"]]
    if len(full_uniform) == 2:
        prob_row = next(r for r in full_uniform if r["method"].startswith("prob"))
        logit_row = next(r for r in full_uniform if r["method"].startswith("logit"))
        w = np.array(prob_row["weights"])
        tests["prob average vs logit average (all members)"] = mcnemar(
            combine([test[t] for t in tags], w, "prob").argmax(1) == test_y,
            combine([test[t] for t in tags], w, "logit").argmax(1) == test_y,
        )

    report = {
        "members": tags,
        "n_test": int(test_y.shape[0]),
        "n_val": int(val_y.shape[0]),
        "results": rows,
        "best": best,
        "mcnemar": tests,
        "agreement": agreement(tags, test, test_y),
    }
    out = REPORT_DIR / f"{args.name}.json"
    out.write_text(json.dumps(report, indent=2))

    width = max(len(", ".join(r["members"])) for r in rows)
    print(f"{'members'.ljust(width)}  {'method'.ljust(26)}  top-1    top-5")
    for r in rows:
        print(
            f"{', '.join(r['members']).ljust(width)}  {r['method'].ljust(26)}  "
            f"{r['test_top1']:6.3f}  {r['test_top5']:6.3f}"
        )
    print()
    for label, t in tests.items():
        verdict = "significant" if t["significant"] else "NOT significant"
        print(f"McNemar  {label}\n         p = {t['p']:.6f} — {verdict} "
              f"(first-only {t['a_only']}, second-only {t['b_only']})")
    print()
    ag = report["agreement"]
    print(f"oracle (any member correct) {ag['oracle_top1']:.3f}   all members wrong {ag['all_wrong']:.3f}")
    for k, v in ag["pairs"].items():
        print(f"  {k}: {v['shared_error_rate']:.1f}% of the first model's errors are shared")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
