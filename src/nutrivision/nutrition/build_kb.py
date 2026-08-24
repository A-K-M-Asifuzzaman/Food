"""Build the nutrition knowledge base for all 101 Food-101 categories."""

from __future__ import annotations

import argparse
import json
import re
import warnings
from typing import Any

from nutrivision.config import DATA_DIR, NUM_CLASSES
from nutrivision.data.dataset import load_classes
from nutrivision.nutrition.mapping import BY_CLASS, ClassSpec, Component
from nutrivision.nutrition.resolve import Resolver
from nutrivision.nutrition.usda import NUTRIENTS, UsdaDatabase

warnings.filterwarnings("ignore")

KB_DIR = DATA_DIR / "nutrition"
KB_PATH = KB_DIR / "kb.json"
AUDIT_PATH = KB_DIR / "audit.md"

ENERGY_FLOOR = 20.0
ENERGY_CEIL = 600.0
ATWATER_TOLERANCE = 0.30  # 30% disagreement before we flag it


def nutrients_for(db: UsdaDatabase, fdc_id: int) -> dict[str, float]:
    row = db.table.loc[db.table["fdc_id"] == fdc_id]
    if row.empty:
        return {}
    row = row.iloc[0]
    out = {}
    for key in NUTRIENTS:
        value = row[key]
        if value == value and value is not None:  # NaN-safe
            out[key] = float(value)
    return out


def resolve_component(resolver: Resolver, comp: Component) -> dict[str, Any]:
    match = resolver.best(
        comp.query, require=comp.require, avoid=comp.avoid, fdc_id=comp.fdc_id
    )
    return {
        "query": comp.query,
        "grams": comp.grams,
        "fdc_id": match.fdc_id,
        "description": match.description,
    }


def build_entry(spec: ClassSpec, resolver: Resolver, db: UsdaDatabase) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "class": spec.cls,
        "title": spec.title,
        "cuisine": spec.cuisine,
        "serving_g": spec.serving_g,
        "serving_label": spec.serving_label,
        "tags": list(spec.tags),
        "note": spec.note,
        "source": "USDA FoodData Central, SR Legacy (2018-04)",
    }

    if spec.is_composite:
        components = [resolve_component(resolver, c) for c in spec.recipe]
        total = sum(c["grams"] for c in components)
        per100: dict[str, float] = {}
        for comp in components:
            comp_nutrients = nutrients_for(db, comp["fdc_id"])
            weight = comp["grams"] / total
            for key, value in comp_nutrients.items():
                per100[key] = per100.get(key, 0.0) + value * weight
        entry["method"] = "composite"
        entry["components"] = components
        entry["component_mass_total_g"] = round(total, 1)
        entry["nutrients_per_100g"] = {k: round(v, 3) for k, v in sorted(per100.items())}
    else:
        match = resolver.best(
            spec.query or spec.cls.replace("_", " "),
            require=spec.require,
            avoid=spec.avoid,
            fdc_id=spec.fdc_id,
        )
        per100 = nutrients_for(db, match.fdc_id)
        entry["method"] = "direct"
        entry["fdc_id"] = match.fdc_id
        entry["description"] = match.description
        entry["nutrients_per_100g"] = {k: round(v, 3) for k, v in sorted(per100.items())}

    scale = spec.serving_g / 100.0
    entry["nutrients_per_serving"] = {
        k: round(v * scale, 3) for k, v in entry["nutrients_per_100g"].items()
    }
    return entry


def check(entry: dict[str, Any]) -> list[str]:
    """Return a list of problems with this entry, empty if it looks sound."""
    problems: list[str] = []
    n = entry["nutrients_per_100g"]

    kcal = n.get("energy_kcal")
    if kcal is None:
        problems.append("no energy value")
        return problems
    if kcal < ENERGY_FLOOR:
        problems.append(f"energy {kcal:.0f} kcal/100 g below plausible floor")
    if kcal > ENERGY_CEIL:
        problems.append(f"energy {kcal:.0f} kcal/100 g above plausible ceiling")

    protein = n.get("protein_g", 0.0)
    carbs = n.get("carbs_g", 0.0)
    fat = n.get("fat_g", 0.0)
    atwater = 4 * protein + 4 * carbs + 9 * fat
    if kcal > 0 and atwater > 0:
        drift = abs(atwater - kcal) / kcal
        if drift > ATWATER_TOLERANCE:
            problems.append(
                f"macros imply {atwater:.0f} kcal but record says {kcal:.0f} ({drift * 100:.0f}% off)"
            )

    if entry["method"] == "composite":
        total = entry["component_mass_total_g"]
        if not 80 <= total <= 125:
            problems.append(f"component weights sum to {total:.0f} g, expected ~100")
        problems.extend(provenance_problems(entry))
    return problems


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 2}


def provenance_problems(entry: dict[str, Any]) -> list[str]:
    """Flag components whose resolved record shares no whole word with the query."""
    problems = []
    for comp in entry.get("components", []):
        query_tokens = _tokens(comp["query"])
        desc_tokens = _tokens(comp["description"])
        if query_tokens and not (query_tokens & desc_tokens):
            problems.append(
                f"ingredient {comp['query']!r} resolved to {comp['description']!r} "
                "with no shared term"
            )
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the nutrition knowledge base")
    ap.add_argument("--review", action="store_true", help="print every resolution for eyeballing")
    args = ap.parse_args()

    classes = load_classes()
    missing = [c for c in classes if c not in BY_CLASS]
    extra = [c for c in BY_CLASS if c not in classes]
    if missing:
        raise SystemExit(f"{len(missing)} classes have no curated spec: {missing}")
    if extra:
        raise SystemExit(f"specs reference unknown classes: {extra}")

    db = UsdaDatabase()
    resolver = Resolver(db)

    entries: list[dict[str, Any]] = []
    flagged: list[tuple[str, list[str]]] = []
    for cls in classes:
        entry = build_entry(BY_CLASS[cls], resolver, db)
        problems = check(entry)
        entry["review_flags"] = problems
        entries.append(entry)
        if problems:
            flagged.append((cls, problems))

    KB_DIR.mkdir(parents=True, exist_ok=True)
    kb = {
        "schema": 1,
        "source": "USDA FoodData Central, SR Legacy (April 2018 release)",
        "basis": "per 100 g edible portion; per-serving figures scaled by serving_g",
        "num_classes": len(entries),
        "nutrients": {k: {"name": v[1], "unit": v[2], "usda_id": v[0]} for k, v in NUTRIENTS.items()},
        "entries": entries,
    }
    KB_PATH.write_text(json.dumps(kb, indent=2))

    direct = sum(1 for e in entries if e["method"] == "direct")
    composite = len(entries) - direct

    lines = [
        "# Nutrition knowledge base - audit report",
        "",
        f"- Classes covered: **{len(entries)}/{NUM_CLASSES}**",
        f"- Direct USDA matches: **{direct}**",
        f"- Composite recipes: **{composite}**",
        f"- Entries with review flags: **{len(flagged)}**",
        "",
        "Every figure below traces to a USDA SR Legacy record. Composite dishes are",
        "mass-weighted means of their ingredient records; the ingredients are listed so",
        "the arithmetic can be checked by hand.",
        "",
        "## Resolutions",
        "",
        "| Class | Method | kcal/100 g | Resolved to |",
        "|---|---|---|---|",
    ]
    for e in entries:
        kcal = e["nutrients_per_100g"].get("energy_kcal", float("nan"))
        if e["method"] == "direct":
            target = e["description"]
        else:
            target = ", ".join(c["description"].split(",")[0] for c in e["components"][:4]) + " ..."
        flag = " ⚠" if e["review_flags"] else ""
        lines.append(f"| {e['class']}{flag} | {e['method']} | {kcal:.0f} | {target[:70]} |")

    if flagged:
        lines += ["", "## Flagged for review", ""]
        for cls, problems in flagged:
            lines.append(f"- **{cls}**: " + "; ".join(problems))

    AUDIT_PATH.write_text("\n".join(lines) + "\n")

    print(f"classes      {len(entries)}/{NUM_CLASSES}")
    print(f"direct       {direct}")
    print(f"composite    {composite}")
    print(f"flagged      {len(flagged)}")
    print(f"kb           {KB_PATH}")
    print(f"audit        {AUDIT_PATH}")

    if args.review or flagged:
        print("\n--- flagged ---")
        for cls, problems in flagged:
            print(f"{cls:26s} {'; '.join(problems)}")


if __name__ == "__main__":
    main()
