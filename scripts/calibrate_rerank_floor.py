#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import time

from nutrivision.config import DATA_DIR, REPORT_DIR
from nutrivision.rag.retrieve import get_retriever

GOLD_PATH = DATA_DIR / "nutrition" / "rag_gold.json"

FLOORS = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2]


def top(hits) -> float:
    return max((h.rerank_score or 0.0) for h in hits) if hits else -99.0


def measure(reranker: str | None, k: int) -> list[dict]:
    retriever = get_retriever(reranker)
    cases = json.loads(GOLD_PATH.read_text())
    rows = []

    for i, case in enumerate(cases, 1):
        for attempt in range(6):
            try:
                conditioned = top(
                    retriever.search(case["question"], food_class=case["food_class"], k=k)
                )
                relaxed = top(retriever.search(case["question"], food_class=None, k=k))
                break
            except Exception as exc:
                wait = 2**attempt
                print(f"  retry {attempt + 1} in {wait}s: {type(exc).__name__}", file=sys.stderr)
                time.sleep(wait)
        else:
            sys.exit(f"gave up on {case['id']}")

        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "must_refuse": case["must_refuse"],
                "conditioned": round(conditioned, 5),
                "relaxed": round(relaxed, 5),
                "best": round(max(conditioned, relaxed), 5),
            }
        )
        print(f"{i:>3}/{len(cases)}  {case['id']:<32} best={rows[-1]['best']:+.4f}")

    return rows


def report(rows: list[dict]) -> None:
    scoped = [r for r in rows if not r["must_refuse"]]
    unscoped = [r for r in rows if r["must_refuse"]]
    worst_in = min(r["best"] for r in scoped)
    best_out = max(r["best"] for r in unscoped)

    print(f"\nworst in-scope   {worst_in:+.4f}   ({len(scoped)} cases)")
    print(f"best out-of-scope {best_out:+.4f}   ({len(unscoped)} cases)")
    print("the gap is where the floor belongs" if worst_in > best_out
          else "NO GAP — no floor separates these cases")

    print(f"\n{'floor':>10} {'refusal acc':>12} {'false refusals':>15}")
    for floor in FLOORS:
        correct = sum(r["best"] < floor for r in unscoped)
        false = sum(r["best"] < floor for r in scoped)
        print(f"{floor:>10.4f} {correct / len(unscoped) * 100:>11.1f}% {false:>15}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Measure a reranker's relevance floor against the gold set."
    )
    p.add_argument("--reranker", default=None, help="cohere | cross-encoder")
    p.add_argument("--k", type=int, default=4)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    rows = measure(args.reranker, args.k)
    report(rows)

    name = (args.reranker or "default").replace("-", "_")
    out = args.out or REPORT_DIR / f"rag_reranker_floor_{name}.json"
    with open(out, "w") as fh:
        json.dump(rows, fh, indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
