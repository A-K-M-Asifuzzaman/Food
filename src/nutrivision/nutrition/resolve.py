from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from nutrivision.nutrition.usda import UsdaDatabase

PENALTY_PATTERNS = (
    (re.compile(r"\bbabyfood\b", re.I), 40.0),
    (re.compile(r"\bdry mix\b|\bmix, dry\b|\bunprepared\b", re.I), 12.0),
    (re.compile(r"\binfant\b|\bformula\b|\bjunior\b|\bstrained\b", re.I), 30.0),
    (re.compile(r"\bsoup, .*condensed\b", re.I), 6.0),
    (re.compile(r"\bpie fillings\b|\bfrosting\b|\bsyrup\b", re.I), 8.0),
    (re.compile(r"\bschool\b|\bUSDA Commodity\b", re.I), 10.0),
)

BRAND_TOKEN = re.compile(r"\b[A-Z]{3,}(?:'?[A-Z]+)?\b")
GENERIC_HINT = re.compile(r"\b(home-prepared|prepared from recipe|commercially prepared)\b", re.I)


@dataclass
class Match:
    fdc_id: int
    description: str
    score: float
    energy_kcal: float


class Resolver:
    def __init__(self, db: UsdaDatabase | None = None):
        self.db = db or UsdaDatabase()
        table = self.db.table.copy()
        table["_desc_l"] = table["description"].str.lower()
        table["_penalty"] = 0.0
        for pattern, weight in PENALTY_PATTERNS:
            hit = table["description"].str.contains(pattern, regex=True)
            table.loc[hit, "_penalty"] += weight
        brand_hits = table["description"].apply(lambda d: len(BRAND_TOKEN.findall(d)))
        table["_penalty"] += brand_hits.clip(upper=3) * 4.0
        table.loc[table["description"].str.contains(GENERIC_HINT, regex=True), "_penalty"] -= 4.0
        self.table = table

    def resolve(
        self,
        query: str,
        require: tuple[str, ...] = (),
        avoid: tuple[str, ...] = (),
        fdc_id: int | None = None,
        limit: int = 5,
    ) -> list[Match]:
        if fdc_id is not None:
            row = self.table.loc[self.table["fdc_id"] == fdc_id]
            if row.empty:
                raise KeyError(f"pinned fdc_id {fdc_id} not in SR Legacy")
            row = row.iloc[0]
            return [Match(int(row.fdc_id), row.description, 999.0, float(row.energy_kcal))]

        terms = [t for t in re.split(r"[\s,_]+", query.lower()) if len(t) > 1]
        desc = self.table["_desc_l"]

        score = pd.Series(0.0, index=self.table.index)
        for t in terms:
            hit = desc.str.contains(re.escape(t), regex=True)
            score += hit.astype(float) * 6.0
            score += desc.str.startswith(t).astype(float) * 3.0

        for t in require:
            score -= (~desc.str.contains(re.escape(t.lower()), regex=True)).astype(float) * 100.0
        for t in avoid:
            score -= desc.str.contains(re.escape(t.lower()), regex=True).astype(float) * 25.0

        score -= self.table["_penalty"]
        score -= self.table["description"].str.len() / 90.0

        out = self.table.assign(_score=score).nlargest(limit, "_score")
        return [
            Match(
                fdc_id=int(row["fdc_id"]),
                description=str(row["description"]),
                score=round(float(row["_score"]), 2),
                energy_kcal=float(row["energy_kcal"]) if pd.notna(row["energy_kcal"]) else float("nan"),
            )
            for _, row in out.iterrows()
        ]

    def best(self, query: str, **kw) -> Match:
        matches = self.resolve(query, **kw)
        if not matches:
            raise LookupError(f"no SR Legacy match for {query!r}")
        return matches[0]
