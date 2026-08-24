"""Verify that every number in a generated answer came from the sources."""

from __future__ import annotations

import re
from dataclasses import dataclass

# A number optionally followed by a unit.
_QUANTITY = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*(kcal|calories|cal|kj|mg|µg|ug|mcg|g\b|grams?|%)?",
    re.IGNORECASE,
)

_UNIT_ALIASES = {
    "calories": "kcal",
    "cal": "kcal",
    "grams": "g",
    "gram": "g",
    "mcg": "µg",
    "ug": "µg",
}

# Numbers that are almost never nutritional claims: list markers, small counts, years.
_IGNORE_BARE = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100, 1000}


@dataclass
class Claim:
    value: float
    unit: str | None
    supported: bool
    nearest: float | None = None

    @property
    def text(self) -> str:
        return f"{self.value:g}{' ' + self.unit if self.unit else ''}"


@dataclass
class GroundingReport:
    claims: list[Claim]
    grounded: bool

    @property
    def unsupported(self) -> list[Claim]:
        return [c for c in self.claims if not c.supported]

    def as_dict(self) -> dict:
        return {
            "grounded": self.grounded,
            "checked": len(self.claims),
            "unsupported": [
                {"value": c.text, "nearest_in_sources": c.nearest} for c in self.unsupported
            ],
        }


def _normalise_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = unit.lower().strip()
    return _UNIT_ALIASES.get(u, u)


def extract_quantities(text: str) -> list[tuple[float, str | None]]:
    out = []
    for value, unit in _QUANTITY.findall(text):
        try:
            number = float(value)
        except ValueError:
            continue
        out.append((number, _normalise_unit(unit)))
    return out


def check(answer: str, context: str, rel_tolerance: float = 0.02) -> GroundingReport:
    """Every quantity in `answer` must appear in `context`."""
    source_quantities = extract_quantities(context)
    by_unit: dict[str | None, list[float]] = {}
    for value, unit in source_quantities:
        by_unit.setdefault(unit, []).append(value)
    anything = [v for v, _ in source_quantities]

    claims: list[Claim] = []
    for value, unit in extract_quantities(answer):
        if unit is None and value in _IGNORE_BARE:
            continue

        pool = by_unit.get(unit, []) if unit else anything
        tolerance = max(abs(value) * rel_tolerance, 0.51)
        nearest = min(pool, key=lambda v: abs(v - value), default=None)
        supported = nearest is not None and abs(nearest - value) <= tolerance
        claims.append(
            Claim(value=value, unit=unit, supported=supported, nearest=nearest)
        )

    return GroundingReport(claims=claims, grounded=all(c.supported for c in claims))
