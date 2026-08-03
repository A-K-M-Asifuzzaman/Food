import calibrationEnsemble from "@/data/reports/calibration_ensemble_siglip_eva02.json";
import calibrationSiglip from "@/data/reports/calibration_siglip_so400m.json";
import conformal from "@/data/reports/conformal.json";
import ensemble from "@/data/reports/ensemble.json";
import ensembleWithFinetune from "@/data/reports/ensemble_with_finetune.json";
import finetuneResult from "@/data/reports/eva02_ft_result.json";
import probeDinov2 from "@/data/reports/probe_dinov2_large.json";
import probeEva02 from "@/data/reports/probe_eva02_large.json";
import probeFusion from "@/data/reports/probe_fusion_siglip_eva02.json";
import probeSiglip from "@/data/reports/probe_siglip_so400m.json";
import ragEvaluation from "@/data/reports/rag_evaluation.json";

/** Everything the public and admin pages render comes from the JSON the
 *  evaluation scripts actually wrote. Nothing on these pages is a figure typed
 *  in by hand — if a number changes upstream, `scripts/sync_web_data.sh` moves
 *  it here and the page changes with it. A dashboard whose numbers were pasted
 *  in is a screenshot with extra steps. */

export type ProbeReport = {
  name: string;
  backbones: string[];
  arch: string;
  params: number;
  train_samples: number;
  val_top1: number;
  val_top5: number;
  test_top1: number;
  test_top5: number;
  best_epoch: number;
  minutes: number;
  num_classes: number;
};

export type EnsembleRow = {
  members: string[];
  method: string;
  weights: number[];
  test_top1: number;
  test_top5: number;
  val_top1?: number;
};

export type McNemar = {
  a_only: number;
  b_only: number;
  p: number;
  significant: boolean;
};

export type CalibrationBin = {
  bin: string;
  count: number;
  confidence: number;
  accuracy: number;
  gap: number;
};

export type CalibrationReport = {
  name: string;
  members: string[] | null;
  temperature: number;
  val_samples: number;
  test_samples: number;
  test_before: {
    top1: number;
    ece: number;
    mce: number;
    brier: number;
    nll: number;
    mean_confidence: number;
    bins: CalibrationBin[];
  };
  test_after: CalibrationReport["test_before"];
};

export type ConformalRow = {
  alpha: number;
  target_coverage: number;
  [method: string]: unknown;
};

export const probes: ProbeReport[] = [
  probeSiglip as ProbeReport,
  probeEva02 as ProbeReport,
  probeDinov2 as ProbeReport,
  probeFusion as ProbeReport,
];

export const ensembleReport = ensemble as unknown as {
  members: string[];
  n_test: number;
  n_val: number;
  results: EnsembleRow[];
  best: EnsembleRow;
  mcnemar: Record<string, McNemar>;
  agreement: {
    oracle_top1: number;
    all_wrong: number;
    pairs: Record<
      string,
      {
        both_correct: number;
        only_first: number;
        only_second: number;
        both_wrong: number;
        shared_error_rate: number;
      }
    >;
  };
};

/** The sweep that includes the fine-tuned model.
 *
 *  Kept separate from `ensembleReport` rather than replacing it. The frozen pair
 *  is what the service actually runs — serving the fine-tune means a 304M
 *  parameter model against two small heads over cached features — so the site
 *  reports the shipped configuration as the headline and this one as the best
 *  measured result, with its significance stated. Collapsing the two would let
 *  the page claim an accuracy the API does not deliver.
 */
export const ensembleWithFinetuneReport = ensembleWithFinetune as unknown as typeof ensembleReport;

export const finetune = finetuneResult as unknown as {
  test_top1: number;
  test_top5: number;
  history: { stage: string; epoch: number; size: number; val_top1: number; ema_top1: number; minutes: number }[];
};

export const calibration = {
  ensemble: calibrationEnsemble as unknown as CalibrationReport,
  siglip: calibrationSiglip as unknown as CalibrationReport,
};

export const conformalReport = conformal as unknown as {
  members: string[];
  temperature: number;
  calibration_samples: number;
  test_samples: number;
  results: ConformalRow[];
};

export const ragReport = ragEvaluation as unknown as {
  gold_cases: number;
  retrieval: Record<
    string,
    {
      n: number;
      "recall@1": number;
      "recall@5": number;
      "answerable@1": number;
      mrr: number;
      ndcg: number;
    }
  >;
  answers?: {
    by_category: Record<
      string,
      { n: number; correct: number; refused: number; grounded: number; median_ms: number }
    >;
    overall: {
      answered_correct: number;
      refusal_accuracy: number;
      false_refusals: number;
      grounded_rate: number;
      total_cost_usd: number;
      wall_seconds: number;
    };
  };
};

/** Display name for a backbone key. The keys are how the code refers to them;
 *  these are how the papers do. */
export const BACKBONE_LABELS: Record<string, string> = {
  siglip_so400m: "SigLIP-SO400M",
  eva02_large: "EVA-02-L",
  dinov2_large: "DINOv2-L",
  eva02_ft: "EVA-02-L (fine-tuned)",
  fusion_siglip_eva02: "Gated fusion head",
};

export function labelFor(key: string): string {
  return BACKBONE_LABELS[key] ?? key;
}

/** The single headline number, derived rather than restated so it cannot drift
 *  from the ensemble sweep that produced it. */
export function headlineAccuracy(): number {
  return ensembleReport.best.test_top1;
}
