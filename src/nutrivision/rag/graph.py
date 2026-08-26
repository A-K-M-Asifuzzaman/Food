"""GraphRAG: a dish -> ingredient -> nutrient graph over the knowledge base."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass

from nutrivision.config import DATA_DIR, INDEX_DIR

KB_PATH = DATA_DIR / "nutrition" / "kb.json"

RANKED_NUTRIENTS = (
    ("energy_kcal", "calories", "kcal"),
    ("protein_g", "protein", "g"),
    ("fat_g", "fat", "g"),
    ("carbs_g", "carbohydrate", "g"),
    ("sodium_mg", "sodium", "mg"),
    ("calcium_mg", "calcium", "mg"),
    ("iron_mg", "iron", "mg"),
)
TOP_N = 10


@dataclass
class Edge:
    source: str
    target: str
    relation: str
    weight: float
    attributes: dict


class NutritionGraph:
    def __init__(self, kb: dict):
        self.kb = kb
        self.entries = {e["class"]: e for e in kb["entries"]}
        self.edges: list[Edge] = []
        self.dish_ingredients: dict[str, dict[str, float]] = defaultdict(dict)
        self.ingredient_dishes: dict[str, dict[str, float]] = defaultdict(dict)
        self.ingredient_titles: dict[str, str] = {}
        self.nutrient_top: dict[str, list[tuple[str, float]]] = {}
        self._build()


    @staticmethod
    def _ingredient_key(component: dict) -> str:
        """Group by USDA record where there is one, else by description."""
        fdc = component.get("fdc_id")
        return f"fdc:{fdc}" if fdc else "desc:" + component["description"].lower()

    def _build(self) -> None:
        for cls, entry in self.entries.items():
            for component in entry.get("components") or []:
                key = self._ingredient_key(component)
                grams = float(component.get("grams", 0.0))
                self.ingredient_titles.setdefault(key, component["description"])
                self.dish_ingredients[cls][key] = grams
                self.ingredient_dishes[key][cls] = grams
                self.edges.append(
                    Edge(
                        source=cls,
                        target=key,
                        relation="CONTAINS",
                        weight=grams,
                        attributes={
                            "fdc_id": component.get("fdc_id"),
                            "description": component["description"],
                        },
                    )
                )

        for key, label, unit in RANKED_NUTRIENTS:
            ranked = sorted(
                (
                    (cls, float(e["nutrients_per_100g"].get(key, 0.0)))
                    for cls, e in self.entries.items()
                    if key in e["nutrients_per_100g"]
                ),
                key=lambda kv: -kv[1],
            )
            self.nutrient_top[key] = ranked[:TOP_N]
            for cls, value in ranked[:TOP_N]:
                self.edges.append(
                    Edge(
                        source=cls,
                        target=f"nutrient:{key}",
                        relation="HIGH_IN",
                        weight=value,
                        attributes={"label": label, "unit": unit},
                    )
                )


    def find_ingredient(self, term: str) -> list[str]:
        term = term.lower().strip()
        return [k for k, title in self.ingredient_titles.items() if term in title.lower()]

    def dishes_with(self, term: str) -> list[tuple[str, float, str]]:
        """Inversion: every dish containing an ingredient matching `term`."""
        out: dict[str, tuple[float, str]] = {}
        for key in self.find_ingredient(term):
            label = self.ingredient_titles[key]
            for cls, grams in self.ingredient_dishes[key].items():
                if cls not in out or grams > out[cls][0]:
                    out[cls] = (grams, label)
        return sorted(
            ((cls, g, label) for cls, (g, label) in out.items()), key=lambda t: -t[1]
        )

    def shared(self, a: str, b: str) -> dict:
        ia, ib = self.dish_ingredients.get(a, {}), self.dish_ingredients.get(b, {})
        missing = [c for c, ing in ((a, ia), (b, ib)) if not ing]
        if missing:
            return {
                "shared": [],
                "only_a": [],
                "only_b": [],
                "unavailable": missing,
                "reason": (
                    "no ingredient breakdown: this dish maps to a single USDA record "
                    "rather than a composite recipe"
                ),
            }
        common = set(ia) & set(ib)
        return {
            "shared": sorted(
                ({"ingredient": self.ingredient_titles[k], "a_g": ia[k], "b_g": ib[k]} for k in common),
                key=lambda d: -(d["a_g"] + d["b_g"]),
            ),
            "only_a": sorted(self.ingredient_titles[k] for k in set(ia) - common),
            "only_b": sorted(self.ingredient_titles[k] for k in set(ib) - common),
        }

    def _idf(self, key: str) -> float:
        """Rarity weight for an ingredient."""
        import math

        total = max(1, len(self.dish_ingredients))
        df = max(1, len(self.ingredient_dishes.get(key, {})))
        return math.log(1.0 + total / df)

    def _tfidf(self, ingredients: dict[str, float]) -> dict[str, float]:
        total = sum(ingredients.values()) or 1.0
        return {i: (g / total) * self._idf(i) for i, g in ingredients.items()}

    def neighbours(
        self, cls: str, k: int = 5, floor: float = 0.02
    ) -> list[tuple[str, float, list[str]]]:
        """Dishes closest by TF-IDF cosine over ingredients."""
        mine_raw = self.dish_ingredients.get(cls, {})
        if not mine_raw:
            return []
        mine = self._tfidf(mine_raw)
        mine_norm = sum(v * v for v in mine.values()) ** 0.5 or 1.0

        scored = []
        for other, raw in self.dish_ingredients.items():
            if other == cls or not raw:
                continue
            common = set(mine_raw) & set(raw)
            if not common:
                continue
            theirs = self._tfidf(raw)
            theirs_norm = sum(v * v for v in theirs.values()) ** 0.5 or 1.0
            dot = sum(mine[i] * theirs[i] for i in common)
            score = dot / (mine_norm * theirs_norm)
            if score < floor:
                continue
            drivers = sorted(common, key=lambda i: -(mine[i] * theirs[i]))
            scored.append((other, score, [self.ingredient_titles[i] for i in drivers]))
        return sorted(scored, key=lambda t: -t[1])[:k]


    def as_documents(self) -> list[dict]:
        """Graph facts as prose, so they join the same grounded pipeline."""
        docs = []

        for key, dishes in self.ingredient_dishes.items():
            if len(dishes) < 2:
                continue
            label = self.ingredient_titles[key]
            listed = ", ".join(
                f"{self.entries[c]['title']} ({g:g} g per 100 g)"
                for c, g in sorted(dishes.items(), key=lambda kv: -kv[1])
            )
            docs.append(
                {
                    "doc_id": f"graph::ingredient::{key}",
                    "kind": "graph_ingredient",
                    "text": (
                        f"{label} appears in {len(dishes)} of the 101 dishes: {listed}. "
                        f"This relationship comes from the composite recipes built from "
                        f"USDA SR Legacy records."
                    ),
                    "food_class": None,
                    "title": label,
                    "metadata": {"dish_count": len(dishes)},
                }
            )

        for cls in self.dish_ingredients:
            near = self.neighbours(cls, k=4)
            if not near:
                continue
            listed = "; ".join(
                f"{self.entries[o]['title']} (shares {', '.join(sh[:3])})" for o, _, sh in near
            )
            docs.append(
                {
                    "doc_id": f"graph::similar::{cls}",
                    "kind": "graph_similarity",
                    "text": (
                        f"Dishes most similar to {self.entries[cls]['title']} by shared "
                        f"ingredients: {listed}. Similarity is weighted ingredient overlap, "
                        f"not visual or textual resemblance."
                    ),
                    "food_class": cls,
                    "title": self.entries[cls]["title"],
                    "metadata": {"neighbours": len(near)},
                }
            )
        return docs

    def layout(self, seed: int = 1337, iterations: int = 220) -> dict[str, list[float]]:
        """Force-directed positions in 3D, computed here rather than in the browser."""
        import networkx as nx
        import numpy as np

        g = nx.Graph()
        for e in self.edges:
            if e.relation == "CONTAINS":
                g.add_edge(e.source, e.target, weight=max(e.weight, 1.0))
        if not g:
            return {}
        pos = nx.spring_layout(
            g, dim=3, seed=seed, iterations=iterations, weight="weight", k=1.0
        )

        coords = np.array(list(pos.values()))
        span = float(max(np.percentile(np.abs(coords), 96), 1e-6))
        return {
            key: [round(float(np.clip(v[i] / span, -1.35, 1.35)) * 10, 3) for i in range(3)]
            for key, v in pos.items()
        }

    def export(self, path=None) -> dict:
        """Node/link JSON for the frontend's 3D graph view."""
        positions = self.layout()

        nodes = [
            {
                "id": c,
                "label": e["title"],
                "type": "dish",
                "group": e["cuisine"],
                "degree": len(self.dish_ingredients[c]),
                "kcal": e["nutrients_per_100g"].get("energy_kcal"),
                "pos": positions.get(c, [0, 0, 0]),
            }
            for c, e in self.entries.items()
            if c in self.dish_ingredients
        ]
        nodes += [
            {
                "id": k,
                "label": self.ingredient_titles[k],
                "type": "ingredient",
                "degree": len(v),
                "pos": positions.get(k, [0, 0, 0]),
            }
            for k, v in self.ingredient_dishes.items()
        ]
        links = [
            {"source": e.source, "target": e.target, "relation": e.relation,
             "weight": e.weight}
            for e in self.edges
            if e.relation == "CONTAINS"
        ]
        payload = {
            "nodes": nodes,
            "links": links,
            "stats": {
                "dishes": len(self.dish_ingredients),
                "ingredients": len(self.ingredient_dishes),
                "shared": sum(1 for v in self.ingredient_dishes.values() if len(v) > 1),
            },
        }
        if path:
            path.write_text(json.dumps(payload))
        return payload


def load_graph() -> NutritionGraph:
    return NutritionGraph(json.loads(KB_PATH.read_text()))


def main() -> None:
    p = argparse.ArgumentParser(description="Query the nutrition graph")
    p.add_argument("--contains", help="find every dish containing this ingredient")
    p.add_argument("--similar", help="dishes closest to this class by ingredient overlap")
    p.add_argument("--compare", nargs=2, metavar=("A", "B"))
    p.add_argument("--export", action="store_true", help="write graph.json for the frontend")
    p.add_argument("--stats", action="store_true")
    args = p.parse_args()

    g = load_graph()

    if args.stats or not any([args.contains, args.similar, args.compare, args.export]):
        multi = sum(1 for v in g.ingredient_dishes.values() if len(v) > 1)
        print(f"dishes with recipes : {len(g.dish_ingredients)}")
        print(f"distinct ingredients: {len(g.ingredient_dishes)}  ({multi} shared by 2+ dishes)")
        print(f"edges               : {len(g.edges)}")
        print(f"graph documents     : {len(g.as_documents())}")

    if args.contains:
        rows = g.dishes_with(args.contains)
        print(f"\ndishes containing '{args.contains}': {len(rows)}")
        for cls, grams, label in rows:
            print(f"  {g.entries[cls]['title']:<28} {grams:>5g} g   ({label})")

    if args.similar:
        near = g.neighbours(args.similar)
        print(f"\nclosest to {g.entries[args.similar]['title']}:")
        if not near:
            print("  no dish shares enough of its ingredients to count as similar")
        for other, score, shared in near:
            print(f"  {g.entries[other]['title']:<28} {score:.3f}  shares {', '.join(shared[:2])}")

    if args.compare:
        a, b = args.compare
        r = g.shared(a, b)
        print(f"\n{g.entries[a]['title']} vs {g.entries[b]['title']}")
        if r.get("unavailable"):
            names = ", ".join(g.entries[c]["title"] for c in r["unavailable"])
            print(f"  cannot compare — {names}: {r['reason']}")
            return
        for s in r["shared"]:
            print(f"  both: {s['ingredient']} ({s['a_g']:g} g / {s['b_g']:g} g)")
        print(f"  only {a}: {', '.join(r['only_a']) or '-'}")
        print(f"  only {b}: {', '.join(r['only_b']) or '-'}")

    if args.export:
        payload = g.export(INDEX_DIR / "graph.json")
        print(f"\nexported {len(payload['nodes'])} nodes, {len(payload['links'])} links")


if __name__ == "__main__":
    main()
