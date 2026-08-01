import kbData from "@/data/kb.json";

/** One USDA source record folded into a composite dish. */
export type Component = {
  query: string;
  grams: number;
  fdc_id: number | null;
  description: string;
};

export type Nutrients = Record<string, number>;

export type FoodEntry = {
  class: string;
  title: string;
  cuisine: string;
  serving_g: number;
  serving_label: string;
  tags: string[];
  note: string;
  source: string;
  /** "direct" when SR Legacy has the dish itself, "composite" when it was built
   *  from weighted ingredient records. The distinction is shown to the user —
   *  a composed figure carries more uncertainty than a measured one. */
  method: "direct" | "composite";
  fdc_id?: number | null;
  description?: string;
  components?: Component[];
  component_mass_total_g?: number;
  nutrients_per_100g: Nutrients;
  nutrients_per_serving: Nutrients;
  review_flags: string[];
};

export type NutrientMeta = { name: string; unit: string; usda_id: number };

export type KnowledgeBase = {
  schema: number;
  source: string;
  basis: string;
  num_classes: number;
  nutrients: Record<string, NutrientMeta>;
  entries: FoodEntry[];
};

const kb = kbData as unknown as KnowledgeBase;

const byClass = new Map(kb.entries.map((e) => [e.class, e]));

export function getKb(): KnowledgeBase {
  return kb;
}

export function getEntry(className: string): FoodEntry | undefined {
  return byClass.get(className);
}

export function allClasses(): string[] {
  return kb.entries.map((e) => e.class);
}

/** Macro split by calorie contribution, which is what a ring or bar should encode.
 *  Using gram mass instead would misrepresent fat, at 9 kcal/g against 4 for the
 *  other two. */
export function macroSplit(n: Nutrients) {
  const protein = (n.protein_g ?? 0) * 4;
  const carbs = (n.carbs_g ?? 0) * 4;
  const fat = (n.fat_g ?? 0) * 9;
  const total = protein + carbs + fat || 1;
  return {
    protein: protein / total,
    carbs: carbs / total,
    fat: fat / total,
    kcalFromMacros: protein + carbs + fat,
  };
}

export const MACRO_KEYS = ["energy_kcal", "protein_g", "carbs_g", "fat_g"] as const;

export const MICRO_KEYS = [
  "saturated_fat_g",
  "sodium_mg",
  "potassium_mg",
  "calcium_mg",
  "iron_mg",
  "magnesium_mg",
  "zinc_mg",
  "vitamin_c_mg",
  "vitamin_a_ug",
  "folate_ug",
] as const;

export function formatAmount(value: number, unit: string): string {
  if (value === 0) return `0 ${unit}`;
  if (value < 0.1) return `${value.toFixed(3)} ${unit}`;
  if (value < 10) return `${value.toFixed(1)} ${unit}`;
  return `${Math.round(value)} ${unit}`;
}

export function titleFor(className: string): string {
  return (
    byClass.get(className)?.title ??
    className.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}
