"""Verify that every number in a generated answer came from the sources.

This exists because of what the application is. A fluent, confident, wrong
calorie figure is worse than no answer at all — someone may act on it. General
RAG evaluation treats grounding as a quality metric to report at the end of a
research run; here it is a runtime gate, and an answer that fails it is not
shown as though it passed.

The check is deliberately narrow, and narrow is what makes it trustworthy.
It does not attempt to judge whether prose is faithful, which would need another
model and would inherit that model's errors. It extracts the *quantities* and
asks a question with a definite answer: does this number appear in the retrieved
context? Numbers are where the harm is, and they are the one part of an answer
that can be checked exactly.

Tolerance exists only for presentation: a model writing "about 330 kcal" for a
source that says 331.25 is rounding, not inventing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A number optionally followed by a unit. Units are captured so "12 g" and
# "12 mg" are never treated as the same claim.
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

# Numbers that are almost never nutritional claims: list markers, small counts,
# years. Flagging "one of the 3 main macronutrients" as unsupported would train
# the reader to ignore the warning, which is worse than not having one.
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
    """Every quantity in `answer` must appear in `context`.

    Matching is per-unit: a figure in milligrams cannot be supported by the same
    digits in grams, which is exactly the confusion a nutrition answer must not
    make.
    """
    source_quantities = extract_quantities(context)
    by_unit: dict[str | None, list[float]] = {}
    for value, unit in source_quantities:
        by_unit.setdefault(unit, []).append(value)
    # A bare number in the sources can support a bare number in the answer, and
    # a unitless mention in the answer may legitimately match a figure that the
    # source spelled out with a unit.
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
