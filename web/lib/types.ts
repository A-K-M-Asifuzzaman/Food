import type { Component, FoodEntry, Nutrients } from "./kb";

/** Where the numbers came from. */
export type ResponseSource = "model" | "demo";

export type Candidate = {
  class: string;
  title: string;
  probability: number;
};

export type ConformalSet = {
  /** Miscoverage rate. */
  alpha: number;
  candidates: Candidate[];
  /** Plain-language restatement of the guarantee, shown to the user. */
  guarantee: string;
};

export type OodVerdict = {
  is_food: boolean;
  score: number;
  threshold: number;
};

export type NutritionPayload = {
  entry: FoodEntry;
  per_serving: Nutrients;
  per_100g: Nutrients;
  serving_label: string;
  /** Present only for composite dishes: the USDA records the figures were built from. */
  components?: Component[];
};

export type PredictResponse = {
  source: ResponseSource;
  latency_ms: number;
  model: {
    name: string;
    test_top1: number;
    ensemble: string[];
  };
  prediction: {
    class: string;
    title: string;
    /** Post-calibration. */
    confidence: number;
    raw_confidence: number;
  };
  conformal: ConformalSet;
  ood: OodVerdict;
  nutrition: NutritionPayload;
};

export type PredictError = { error: string };
