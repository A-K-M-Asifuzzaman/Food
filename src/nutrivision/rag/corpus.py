from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from nutrivision.config import DATA_DIR

KB_PATH = DATA_DIR / "nutrition" / "kb.json"
CORPUS_PATH = DATA_DIR / "nutrition" / "corpus.jsonl"

RANKED_NUTRIENTS = (
    ("energy_kcal", "calories", "kcal", 0),
    ("protein_g", "protein", "g", 1),
    ("fat_g", "total fat", "g", 1),
    ("saturated_fat_g", "saturated fat", "g", 1),
    ("carbs_g", "carbohydrate", "g", 1),
    ("sugar_g", "sugar", "g", 1),
    ("fiber_g", "dietary fibre", "g", 1),
    ("sodium_mg", "sodium", "mg", 0),
    ("cholesterol_mg", "cholesterol", "mg", 0),
    ("calcium_mg", "calcium", "mg", 0),
    ("iron_mg", "iron", "mg", 1),
    ("potassium_mg", "potassium", "mg", 0),
)

MICRO_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "minerals",
        ("sodium_mg", "potassium_mg", "calcium_mg", "iron_mg", "magnesium_mg",
         "phosphorus_mg", "zinc_mg", "copper_mg", "manganese_mg", "selenium_ug"),
    ),
    (
        "vitamins",
        ("vitamin_a_ug", "vitamin_c_mg", "vitamin_d_ug", "vitamin_e_mg", "vitamin_k_ug",
         "thiamin_mg", "riboflavin_mg", "niacin_mg", "vitamin_b6_mg", "folate_ug",
         "vitamin_b12_ug"),
    ),
)

LABELS = {
    "energy_kcal": ("energy", "kcal"), "protein_g": ("protein", "g"),
    "fat_g": ("total fat", "g"), "carbs_g": ("carbohydrate", "g"),
    "fiber_g": ("dietary fibre", "g"), "sugar_g": ("total sugars", "g"),
    "saturated_fat_g": ("saturated fat", "g"), "trans_fat_g": ("trans fat", "g"),
    "mono_fat_g": ("monounsaturated fat", "g"), "poly_fat_g": ("polyunsaturated fat", "g"),
    "cholesterol_mg": ("cholesterol", "mg"), "sodium_mg": ("sodium", "mg"),
    "potassium_mg": ("potassium", "mg"), "calcium_mg": ("calcium", "mg"),
    "iron_mg": ("iron", "mg"), "magnesium_mg": ("magnesium", "mg"),
    "phosphorus_mg": ("phosphorus", "mg"), "zinc_mg": ("zinc", "mg"),
    "copper_mg": ("copper", "mg"), "manganese_mg": ("manganese", "mg"),
    "selenium_ug": ("selenium", "µg"), "vitamin_a_ug": ("vitamin A", "µg"),
    "vitamin_c_mg": ("vitamin C", "mg"), "vitamin_d_ug": ("vitamin D", "µg"),
    "vitamin_e_mg": ("vitamin E", "mg"), "vitamin_k_ug": ("vitamin K", "µg"),
    "thiamin_mg": ("thiamin (B1)", "mg"), "riboflavin_mg": ("riboflavin (B2)", "mg"),
    "niacin_mg": ("niacin (B3)", "mg"), "vitamin_b6_mg": ("vitamin B6", "mg"),
    "folate_ug": ("folate", "µg"), "vitamin_b12_ug": ("vitamin B12", "µg"),
}


@dataclass
class Document:
    doc_id: str
    kind: str
    text: str
    food_class: str | None = None
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "kind": self.kind,
            "text": self.text,
            "food_class": self.food_class,
            "title": self.title,
            "metadata": self.metadata,
        }


def _fmt(value: float, digits: int = 1) -> str:
    if digits == 0:
        return f"{value:,.0f}"
    return f"{value:,.{digits}f}".rstrip("0").rstrip(".")


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


_GENERIC_HEADS = {
    "fish", "beverages", "nuts", "mollusks", "crustaceans", "cereals", "spices",
    "candies", "cookies", "desserts", "snacks", "soup",
    "leavening agents", "gelatins", "frostings", "salad dressing", "puddings",
}

_COMPOUND_HEADS = {"cheese", "oil", "seaweed", "sauce", "vinegar", "flour", "milk"}


def ingredient_name(description: str) -> str:
    segments = [s.strip() for s in description.split(",") if s.strip()]
    if not segments:
        return description.lower()
    head = segments[0].lower()
    if len(segments) > 1:
        if head in _COMPOUND_HEADS:
            return f"{segments[1].lower()} {head}"
        if head in _GENERIC_HEADS:
            return segments[1].lower()
    return head


def load_kb(path=KB_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"knowledge base missing at {path}; run nutrivision.nutrition.build_kb")
    return json.loads(path.read_text())


def identity_doc(entry: dict) -> Document:
    title = entry["title"]
    n = entry["nutrients_per_100g"]
    kcal = n.get("energy_kcal", 0)
    serving_kcal = entry["nutrients_per_serving"].get("energy_kcal", 0)
    tags = ", ".join(entry.get("tags", [])) or "general"

    if entry["method"] == "direct":
        provenance = (
            f"Its nutritional values come directly from the USDA SR Legacy record "
            f"\"{entry['description']}\" (FDC ID {entry['fdc_id']})."
        )
    else:
        names = [ingredient_name(c["description"]) for c in entry["components"]]
        provenance = (
            "USDA SR Legacy has no single record for this dish, so its nutritional profile is "
            "computed as a mass-weighted composite of its ingredients: "
            + ", ".join(names[:8])
            + "."
        )

    text = (
        f"{title} is {_article(entry['cuisine'])} {entry['cuisine']} dish, categorised as {tags}. "
        f"A typical serving is {entry['serving_label']}. "
        f"{title} provides {_fmt(kcal, 0)} kcal per 100 g, "
        f"which is {_fmt(serving_kcal, 0)} kcal for a typical serving of "
        f"{_fmt(entry['serving_g'], 0)} g. "
        f"{provenance}"
    )
    if entry.get("note"):
        text += f" Note: {entry['note']}"

    return Document(
        doc_id=f"{entry['class']}::identity",
        kind="identity",
        text=text,
        food_class=entry["class"],
        title=title,
        metadata={"cuisine": entry["cuisine"], "energy_kcal": kcal, "method": entry["method"]},
    )


def macro_doc(entry: dict) -> Document:
    title = entry["title"]
    n = entry["nutrients_per_100g"]
    s = entry["nutrients_per_serving"]
    parts = []
    for key in ("protein_g", "fat_g", "carbs_g", "fiber_g", "sugar_g", "saturated_fat_g"):
        if key in n:
            label, unit = LABELS[key]
            parts.append(f"{label} {_fmt(n[key])} {unit} per 100 g ({_fmt(s[key])} {unit} per serving)")

    text = (
        f"Macronutrients for {title}. "
        + "; ".join(parts)
        + ". "
        + f"Energy is {_fmt(n.get('energy_kcal', 0), 0)} kcal per 100 g and "
        f"{_fmt(s.get('energy_kcal', 0), 0)} kcal per {entry['serving_label']}."
    )
    return Document(
        doc_id=f"{entry['class']}::macros",
        kind="macros",
        text=text,
        food_class=entry["class"],
        title=title,
        metadata={k: n[k] for k in ("protein_g", "fat_g", "carbs_g") if k in n},
    )


def micro_docs(entry: dict) -> Iterable[Document]:
    title = entry["title"]
    n = entry["nutrients_per_100g"]
    per_serving = entry.get("nutrients_per_serving", {})
    serving_label = entry.get("serving_label", "1 serving")

    for group, keys in MICRO_GROUPS:
        present = [(k, n[k]) for k in keys if k in n and n[k] > 0]
        if not present:
            continue
        parts = [
            f"{LABELS[k][0]} {_fmt(v, 2)} {LABELS[k][1]} per 100 g"
            + (
                f" ({_fmt(per_serving[k], 2)} {LABELS[k][1]} per serving)"
                if k in per_serving
                else ""
            )
            for k, v in present
        ]
        text = (
            f"{group.capitalize()} in {title}, per 100 g and per serving of "
            f"{serving_label}: " + "; ".join(parts) + ". "
            "These figures are sourced from USDA SR Legacy."
        )
        yield Document(
            doc_id=f"{entry['class']}::{group}",
            kind=group,
            text=text,
            food_class=entry["class"],
            title=title,
            metadata={"nutrient_count": len(present)},
        )


def ingredient_doc(entry: dict) -> Document | None:
    if entry["method"] != "composite":
        return None
    title = entry["title"]
    parts = [
        f"{ingredient_name(c['description'])} ({_fmt(c['grams'], 0)} g per 100 g)"
        for c in entry["components"]
    ]
    text = (
        f"{title} is composed of the following ingredients, with their proportions per 100 g "
        f"of finished dish: " + "; ".join(parts) + ". "
        f"Each ingredient maps to a USDA SR Legacy record, so the nutritional profile of "
        f"{title} is reconstructed from these components rather than measured directly."
    )
    return Document(
        doc_id=f"{entry['class']}::ingredients",
        kind="ingredients",
        text=text,
        food_class=entry["class"],
        title=title,
        metadata={"ingredients": [c["description"] for c in entry["components"]]},
    )


def portion_doc(entry: dict) -> Document:
    title = entry["title"]
    s = entry["nutrients_per_serving"]
    text = (
        f"Portion and serving information for {title}. "
        f"A typical serving is {entry['serving_label']}, i.e. {_fmt(entry['serving_g'], 0)} grams. "
        f"That serving supplies {_fmt(s.get('energy_kcal', 0), 0)} kcal, "
        f"{_fmt(s.get('protein_g', 0))} g protein, {_fmt(s.get('fat_g', 0))} g fat and "
        f"{_fmt(s.get('carbs_g', 0))} g carbohydrate. "
        f"To convert any per-100 g figure for {title} to a per-serving figure, "
        f"multiply by {entry['serving_g'] / 100:.2f}."
    )
    return Document(
        doc_id=f"{entry['class']}::portion",
        kind="portion",
        text=text,
        food_class=entry["class"],
        title=title,
        metadata={"serving_g": entry["serving_g"]},
    )


def ranking_docs(entries: list[dict], top_n: int = 12) -> Iterable[Document]:
    for key, label, unit, digits in RANKED_NUTRIENTS:
        have = [(e, e["nutrients_per_100g"].get(key)) for e in entries]
        have = [(e, v) for e, v in have if v is not None]
        if len(have) < 10:
            continue
        ordered = sorted(have, key=lambda kv: kv[1], reverse=True)

        highest = "; ".join(f"{e['title']} {_fmt(v, digits)} {unit}" for e, v in ordered[:top_n])
        lowest = "; ".join(
            f"{e['title']} {_fmt(v, digits)} {unit}" for e, v in reversed(ordered[-top_n:])
        )
        text = (
            f"Ranking of Food-101 dishes by {label} per 100 g. "
            f"Highest in {label}: {highest}. "
            f"Lowest in {label}: {lowest}. "
            f"All values are per 100 g from USDA SR Legacy."
        )
        yield Document(
            doc_id=f"ranking::{key}",
            kind="ranking",
            text=text,
            food_class=None,
            title=f"Dishes ranked by {label}",
            metadata={
                "nutrient": key,
                "highest": [e["class"] for e, _ in ordered[:top_n]],
                "lowest": [e["class"] for e, _ in ordered[-top_n:]],
            },
        )


def build_corpus(kb: dict | None = None) -> list[Document]:
    kb = kb or load_kb()
    entries = kb["entries"]
    docs: list[Document] = []
    for entry in entries:
        docs.append(identity_doc(entry))
        docs.append(macro_doc(entry))
        docs.extend(micro_docs(entry))
        ing = ingredient_doc(entry)
        if ing:
            docs.append(ing)
        docs.append(portion_doc(entry))
    docs.extend(ranking_docs(entries))
    return docs


def main() -> None:
    docs = build_corpus()
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CORPUS_PATH.open("w") as fh:
        for d in docs:
            fh.write(json.dumps(d.to_json()) + "\n")

    by_kind: dict[str, int] = {}
    for d in docs:
        by_kind[d.kind] = by_kind.get(d.kind, 0) + 1
    lengths = sorted(len(d.text.split()) for d in docs)

    print(f"documents     {len(docs)}")
    for kind, count in sorted(by_kind.items(), key=lambda kv: -kv[1]):
        print(f"  {kind:14s} {count}")
    print(f"words         median {lengths[len(lengths) // 2]}, max {lengths[-1]}")
    print(f"written to    {CORPUS_PATH}")


if __name__ == "__main__":
    main()
