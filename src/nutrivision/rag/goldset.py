"""Build the RAG evaluation set."""

from __future__ import annotations

import argparse
import json
import random

from nutrivision.config import DATA_DIR

from .graph import load_graph

GOLD_PATH = DATA_DIR / "nutrition" / "rag_gold.json"

NUTRIENT_QUESTIONS = [
    ("sodium_mg", "how much sodium is in this", "minerals"),
    ("protein_g", "how much protein does this have", "macros"),
    ("energy_kcal", "how many calories are in this", "identity"),
    ("calcium_mg", "how much calcium is in this", "minerals"),
    ("iron_mg", "how much iron does this contain", "minerals"),
    ("vitamin_c_mg", "how much vitamin C is in this", "vitamins"),
    ("carbs_g", "how many carbohydrates does this have", "macros"),
    ("fat_g", "how much fat is in this", "macros"),
]

OUT_OF_SCOPE = [
    "what is the capital of France",
    "how do I treat a broken arm",
    "who won the world cup in 2018",
    "what is the derivative of x squared",
    "should I take insulin for this",
    "write me a poem about the sea",
]

SUPERLATIVES = [
    ("which dish has the most protein", "protein_g", True),
    ("which food has the fewest calories", "energy_kcal", False),
    ("what is highest in sodium", "sodium_mg", True),
    ("which dish has the most calcium", "calcium_mg", True),
]


def build(seed: int = 1337, per_nutrient: int = 6) -> list[dict]:
    rng = random.Random(seed)
    graph = load_graph()
    entries = graph.entries
    classes = sorted(entries)
    cases: list[dict] = []

    for key, phrasing, kind in NUTRIENT_QUESTIONS:
        eligible = [c for c in classes if entries[c]["nutrients_per_100g"].get(key, 0) > 0]
        for cls in rng.sample(eligible, min(per_nutrient, len(eligible))):
            entry = entries[cls]
            cases.append(
                {
                    "id": f"nutrient::{cls}::{key}",
                    "category": "nutrient_lookup",
                    "question": phrasing,
                    "food_class": cls,
                    "expected_doc_ids": [f"{cls}::{kind}"],
                    "expected_values": [
                        round(float(entry["nutrients_per_100g"][key]), 2),
                        round(float(entry["nutrients_per_serving"][key]), 2),
                    ],
                    "must_refuse": False,
                }
            )

    composites = [c for c in classes if entries[c].get("components")]
    for cls in rng.sample(composites, min(10, len(composites))):
        cases.append(
            {
                "id": f"ingredients::{cls}",
                "category": "ingredients",
                "question": "what is this made of",
                "food_class": cls,
                "expected_doc_ids": [f"{cls}::ingredients"],
                "expected_values": [],
                "must_refuse": False,
            }
        )

    shared = [
        (k, v) for k, v in graph.ingredient_dishes.items() if 2 <= len(v) <= 8
    ]
    for key, dishes in rng.sample(shared, min(8, len(shared))):
        label = graph.ingredient_titles[key]
        term = label.split(",")[-1].strip() if "," in label else label
        cases.append(
            {
                "id": f"graph::contains::{key}",
                "category": "graph_inversion",
                "question": f"which dishes contain {term.lower()}",
                "food_class": None,
                "expected_doc_ids": [f"graph::ingredient::{key}"],
                "expected_titles": sorted(entries[c]["title"] for c in dishes),
                "expected_values": [],
                "must_refuse": False,
            }
        )

    for question, key, highest in SUPERLATIVES:
        ranked = sorted(
            ((c, entries[c]["nutrients_per_100g"].get(key, 0.0)) for c in classes),
            key=lambda kv: -kv[1] if highest else kv[1],
        )
        winner = ranked[0]
        cases.append(
            {
                "id": f"superlative::{key}::{'max' if highest else 'min'}",
                "category": "superlative",
                "question": question,
                "food_class": None,
                "expected_doc_ids": [f"ranking::{key}"],
                "expected_titles": [entries[winner[0]]["title"]],
                "expected_values": [round(float(winner[1]), 2)],
                "must_refuse": False,
            }
        )

    for question in OUT_OF_SCOPE:
        cases.append(
            {
                "id": f"refuse::{question[:24].replace(' ', '_')}",
                "category": "out_of_scope",
                "question": question,
                "food_class": None,
                "expected_doc_ids": [],
                "expected_values": [],
                "must_refuse": True,
            }
        )

    return cases


def main() -> None:
    p = argparse.ArgumentParser(description="Build the RAG gold set")
    p.add_argument("--per-nutrient", type=int, default=6)
    p.add_argument("--seed", type=int, default=1337)
    args = p.parse_args()

    cases = build(seed=args.seed, per_nutrient=args.per_nutrient)
    GOLD_PATH.write_text(json.dumps(cases, indent=2))

    counts: dict[str, int] = {}
    for c in cases:
        counts[c["category"]] = counts.get(c["category"], 0) + 1
    print(f"{len(cases)} cases -> {GOLD_PATH}")
    for k, v in sorted(counts.items()):
        print(f"  {k:<18} {v}")


if __name__ == "__main__":
    main()
