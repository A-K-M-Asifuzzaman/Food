"""Score the RAG pipeline against the gold set."""

from __future__ import annotations

import argparse
import json
import time

from nutrivision.config import DATA_DIR, REPORT_DIR

from .ground import extract_quantities
from .retrieve import get_retriever

GOLD_PATH = DATA_DIR / "nutrition" / "rag_gold.json"


def dcg(relevances: list[int]) -> float:
    import math

    return sum(r / math.log2(i + 2) for i, r in enumerate(relevances))


def answer_bearing(doc, case: dict) -> bool:
    """Does this document actually contain what the question asks for?"""
    if doc.doc_id in set(case["expected_doc_ids"]):
        return True
    if case["food_class"] and doc.food_class != case["food_class"]:
        return False
    expected = case.get("expected_values") or []
    if not expected:
        return False
    values = [v for v, _ in extract_quantities(doc.text)]
    return any(
        any(abs(v - e) <= max(abs(e) * 0.02, 0.51) for v in values) for e in expected
    )


def score_retrieval(cases: list[dict], k: int = 5) -> dict:
    retriever = get_retriever()
    per_category: dict[str, list[dict]] = {}

    for case in cases:
        if case["must_refuse"]:
            continue
        hits = retriever.search(case["question"], food_class=case["food_class"], k=k)
        docs = [h.document for h in hits]
        ids = [d.doc_id for d in docs]
        expected = set(case["expected_doc_ids"])

        rank = next((i for i, d in enumerate(ids) if d in expected), None)
        relevances = [1 if d in expected else 0 for d in ids]
        useful = [answer_bearing(d, case) for d in docs]
        per_category.setdefault(case["category"], []).append(
            {
                "hit@1": bool(ids and ids[0] in expected),
                "hit@k": rank is not None,
                "useful@1": bool(useful and useful[0]),
                "rr": 0.0 if rank is None else 1.0 / (rank + 1),
                "ndcg": dcg(relevances) / (dcg(sorted(relevances, reverse=True)) or 1.0),
            }
        )

    summary = {}
    for category, rows in per_category.items():
        n = len(rows)
        summary[category] = {
            "n": n,
            "recall@1": round(sum(r["hit@1"] for r in rows) / n * 100, 2),
            f"recall@{k}": round(sum(r["hit@k"] for r in rows) / n * 100, 2),
            "answerable@1": round(sum(r["useful@1"] for r in rows) / n * 100, 2),
            "mrr": round(sum(r["rr"] for r in rows) / n, 4),
            "ndcg": round(sum(r["ndcg"] for r in rows) / n, 4),
        }
    return summary


def numeric_match(answer: str, expected: list[float], tolerance: float = 0.02) -> bool:
    """True when the answer states one of the acceptable figures."""
    if not expected:
        return True
    values = [v for v, _ in extract_quantities(answer)]
    return any(
        any(abs(v - e) <= max(abs(e) * tolerance, 0.51) for v in values) for e in expected
    )


def score_answers(cases: list[dict], limit: int | None = None) -> dict:
    from .generate import answer as generate_answer

    rows = []
    started = time.time()
    for case in cases[:limit] if limit else cases:
        result = generate_answer(case["question"], food_class=case["food_class"])
        refused = result.mode == "insufficient"
        correct = (
            refused
            if case["must_refuse"]
            else (not refused and numeric_match(result.text, case.get("expected_values", [])))
        )
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "mode": result.mode,
                "refused": refused,
                "correct": correct,
                "grounded": result.grounded,
                "cost": result.usage.get("cost_usd", 0.0),
                "latency_ms": result.latency_ms,
            }
        )

    by_category: dict[str, list[dict]] = {}
    for r in rows:
        by_category.setdefault(r["category"], []).append(r)

    summary = {}
    for category, group in by_category.items():
        n = len(group)
        summary[category] = {
            "n": n,
            "correct": round(sum(r["correct"] for r in group) / n * 100, 2),
            "refused": round(sum(r["refused"] for r in group) / n * 100, 2),
            "grounded": round(sum(r["grounded"] for r in group) / n * 100, 2),
            "median_ms": sorted(r["latency_ms"] for r in group)[n // 2],
        }

    scoped = [r for r in rows if r["category"] != "out_of_scope"]
    unscoped = [r for r in rows if r["category"] == "out_of_scope"]
    return {
        "by_category": summary,
        "overall": {
            "answered_correct": round(
                sum(r["correct"] for r in scoped) / max(1, len(scoped)) * 100, 2
            ),
            "refusal_accuracy": round(
                sum(r["correct"] for r in unscoped) / max(1, len(unscoped)) * 100, 2
            ),
            "false_refusals": sum(r["refused"] for r in scoped),
            "grounded_rate": round(sum(r["grounded"] for r in rows) / len(rows) * 100, 2),
            "total_cost_usd": round(sum(r["cost"] for r in rows), 5),
            "wall_seconds": round(time.time() - started, 1),
        },
        "rows": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate the RAG pipeline")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--retrieval-only", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    cases = json.loads(GOLD_PATH.read_text())
    print(f"gold set: {len(cases)} cases\n")

    retrieval = score_retrieval(cases, k=args.k)
    print("── retrieval ──")
    head = (f"{'category':<18} {'n':>3} {'R@1':>7} {'R@' + str(args.k):>7} "
            f"{'answerable@1':>13} {'MRR':>7} {'nDCG':>7}")
    print(head)
    print("-" * len(head))
    for category, m in sorted(retrieval.items()):
        print(
            f"{category:<18} {m['n']:>3} {m['recall@1']:>6.1f}% "
            f"{m[f'recall@{args.k}']:>6.1f}% {m['answerable@1']:>12.1f}% "
            f"{m['mrr']:>7.3f} {m['ndcg']:>7.3f}"
        )

    report = {"gold_cases": len(cases), "retrieval": retrieval}

    if not args.retrieval_only:
        answers = score_answers(cases, limit=args.limit)
        print("\n── answers ──")
        head = f"{'category':<18} {'n':>3} {'correct':>9} {'refused':>9} {'grounded':>9}"
        print(head)
        print("-" * len(head))
        for category, m in sorted(answers["by_category"].items()):
            print(
                f"{category:<18} {m['n']:>3} {m['correct']:>8.1f}% "
                f"{m['refused']:>8.1f}% {m['grounded']:>8.1f}%"
            )
        o = answers["overall"]
        print(f"\n  answered correctly   {o['answered_correct']:.1f}%")
        print(f"  refusal accuracy     {o['refusal_accuracy']:.1f}%")
        print(f"  false refusals       {o['false_refusals']}")
        print(f"  grounded             {o['grounded_rate']:.1f}%")
        print(f"  cost                 ${o['total_cost_usd']:.4f} over {o['wall_seconds']:.0f}s")
        report["answers"] = answers

    out = REPORT_DIR / "rag_evaluation.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
