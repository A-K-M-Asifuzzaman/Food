from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from nutrivision.config import DATA_DIR

USDA_DIR = DATA_DIR / "usda" / "FoodData_Central_sr_legacy_food_csv_2018-04"

NUTRIENTS: dict[str, tuple[int, str, str]] = {
    "energy_kcal": (1008, "Energy", "kcal"),
    "protein_g": (1003, "Protein", "g"),
    "fat_g": (1004, "Total fat", "g"),
    "carbs_g": (1005, "Carbohydrate", "g"),
    "fiber_g": (1079, "Dietary fiber", "g"),
    "sugar_g": (2000, "Total sugars", "g"),
    "saturated_fat_g": (1258, "Saturated fat", "g"),
    "trans_fat_g": (1257, "Trans fat", "g"),
    "mono_fat_g": (1292, "Monounsaturated fat", "g"),
    "poly_fat_g": (1293, "Polyunsaturated fat", "g"),
    "cholesterol_mg": (1253, "Cholesterol", "mg"),
    "sodium_mg": (1093, "Sodium", "mg"),
    "potassium_mg": (1092, "Potassium", "mg"),
    "calcium_mg": (1087, "Calcium", "mg"),
    "iron_mg": (1089, "Iron", "mg"),
    "magnesium_mg": (1090, "Magnesium", "mg"),
    "phosphorus_mg": (1091, "Phosphorus", "mg"),
    "zinc_mg": (1095, "Zinc", "mg"),
    "copper_mg": (1098, "Copper", "mg"),
    "manganese_mg": (1101, "Manganese", "mg"),
    "selenium_ug": (1103, "Selenium", "µg"),
    "vitamin_a_ug": (1106, "Vitamin A (RAE)", "µg"),
    "vitamin_c_mg": (1162, "Vitamin C", "mg"),
    "vitamin_d_ug": (1114, "Vitamin D", "µg"),
    "vitamin_e_mg": (1109, "Vitamin E", "mg"),
    "vitamin_k_ug": (1185, "Vitamin K", "µg"),
    "thiamin_mg": (1165, "Thiamin (B1)", "mg"),
    "riboflavin_mg": (1166, "Riboflavin (B2)", "mg"),
    "niacin_mg": (1167, "Niacin (B3)", "mg"),
    "vitamin_b6_mg": (1175, "Vitamin B6", "mg"),
    "folate_ug": (1177, "Folate", "µg"),
    "vitamin_b12_ug": (1178, "Vitamin B12", "µg"),
}

NUTRIENT_BY_ID = {nid: key for key, (nid, _, _) in NUTRIENTS.items()}


@dataclass
class UsdaFood:
    fdc_id: int
    description: str
    category: str
    nutrients: dict[str, float]


class UsdaDatabase:
    def __init__(self, root: Path = USDA_DIR):
        if not root.exists():
            raise FileNotFoundError(
                f"USDA SR Legacy not found at {root}. Run scripts/fetch_usda.sh first."
            )
        self.root = root
        self._food: pd.DataFrame | None = None
        self._wide: pd.DataFrame | None = None

    @property
    def food(self) -> pd.DataFrame:
        if self._food is None:
            food = pd.read_csv(self.root / "food.csv", usecols=["fdc_id", "description", "food_category_id"])
            cats = pd.read_csv(self.root / "food_category.csv", usecols=["id", "description"])
            cats = cats.rename(columns={"id": "food_category_id", "description": "category"})
            self._food = food.merge(cats, on="food_category_id", how="left")
        return self._food

    @property
    def wide(self) -> pd.DataFrame:
        if self._wide is None:
            fn = pd.read_csv(
                self.root / "food_nutrient.csv",
                usecols=["fdc_id", "nutrient_id", "amount"],
                dtype={"fdc_id": "int64", "nutrient_id": "int64", "amount": "float64"},
            )
            fn = fn[fn["nutrient_id"].isin(NUTRIENT_BY_ID)]
            fn["key"] = fn["nutrient_id"].map(NUTRIENT_BY_ID)
            wide = fn.pivot_table(index="fdc_id", columns="key", values="amount", aggfunc="mean")
            for key in NUTRIENTS:
                if key not in wide.columns:
                    wide[key] = pd.NA
            self._wide = wide[list(NUTRIENTS)].reset_index()
        return self._wide

    @functools.cached_property
    def table(self) -> pd.DataFrame:
        return self.food.merge(self.wide, on="fdc_id", how="inner")

    def get(self, fdc_id: int) -> UsdaFood:
        row = self.table.loc[self.table["fdc_id"] == fdc_id]
        if row.empty:
            raise KeyError(f"fdc_id {fdc_id} not present")
        row = row.iloc[0]
        return UsdaFood(
            fdc_id=int(row["fdc_id"]),
            description=str(row["description"]),
            category=str(row.get("category", "")),
            nutrients={k: float(row[k]) for k in NUTRIENTS if pd.notna(row[k])},
        )

    def search(self, query: str, limit: int = 10) -> pd.DataFrame:
        terms = [t for t in query.lower().replace("_", " ").split() if t]
        desc = self.table["description"].str.lower()
        score = sum(desc.str.contains(t, regex=False).astype(int) for t in terms)
        out = self.table.assign(_score=score)
        out = out[out["_score"] > 0].sort_values(["_score", "description"], ascending=[False, True])
        return out.head(limit)[["fdc_id", "description", "category", "energy_kcal", "_score"]]

    def portions(self, fdc_id: int) -> pd.DataFrame:
        p = pd.read_csv(self.root / "food_portion.csv")
        units = pd.read_csv(self.root / "measure_unit.csv").rename(
            columns={"id": "measure_unit_id", "name": "unit"}
        )
        p = p[p["fdc_id"] == fdc_id].merge(units, on="measure_unit_id", how="left")
        return p[["amount", "unit", "modifier", "portion_description", "gram_weight"]]
