import type { Component, FoodEntry, Nutrients } from "./kb";

/** Where the numbers came from. The UI must always say this out loud: a demo
 *  response is not a prediction, and presenting one as if it were would be a lie
 *  told by the interface. */
export type ResponseSource = "model" | "demo";

export type Candidate = {
  class: string;
  title: string;
  probability: number;
};

export type ConformalSet = {
  /** Miscoverage rate. alpha = 0.05 means the set covers the true class 95% of
   *  the time, over the calibration distribution. */
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
    /** Post-calibration. Stage 5 found the ensemble under-confident, so the raw
     *  softmax and the calibrated value differ and both are worth showing. */
    confidence: number;
    raw_confidence: number;
  };
  conformal: ConformalSet;
  ood: OodVerdict;
  nutrition: NutritionPayload;
};

export type PredictError = { error: string };
