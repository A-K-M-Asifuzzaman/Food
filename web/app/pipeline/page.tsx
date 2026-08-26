import type { Metadata } from "next";
import Link from "next/link";

import { Mermaid } from "../components/Mermaid";
import { Reveal } from "../components/Reveal";
import { Spider3D } from "../components/Spider3D";
import { WebShot } from "../components/WebShot";
import { Beat, Caption, GutterRule, Panel } from "../components/comic";

export const metadata: Metadata = {
  title: "The pipeline — FoodGenome AI",
  description:
    "Every stage of the system as a diagram: data, feature bank, probe heads, fine-tuning, ensembling, calibration, conformal prediction, explainability, the nutrition knowledge base, retrieval and serving.",
};

/* Diagrams are authored here rather than fetched, so they are versioned with the
   code they describe and cannot drift from it silently. */

const SYSTEM = `flowchart TD
  A["Photograph"] --> B["Preprocess<br/>resize · crop · normalise"]
  B --> C["Two frozen backbones<br/>SigLIP-SO400M · EVA-02-L"]
  C --> D["Two MLP probe heads"]
  D --> E["Probability average"]
  E --> F["Temperature scaling<br/>T = 0.7621"]
  F --> G["Calibrated confidence"]
  F --> H["Conformal set<br/>99.61% coverage"]
  C --> I["Grad-CAM<br/>attribution map"]
  G --> J["Dish identified"]
  J --> K["Nutrition lookup<br/>USDA SR Legacy"]
  J --> L["Grounded question answering"]
  K --> M["32 nutrients<br/>per 100g and per serving"]
  L --> M`;

const DATA = `flowchart LR
  A["ethz/food101<br/>Parquet on the Hub"] --> B["Decode once"]
  B --> C["JPEG folder tree<br/>101 classes"]
  C --> D{"Stratified split<br/>seed = 1337"}
  D -->|"96%"| E["Train<br/>72,720"]
  D -->|"4%"| F["Validation<br/>3,030"]
  C --> G["Test — sealed<br/>25,250"]
  E --> H["Weight updates"]
  F --> I["Model selection<br/>temperature · conformal quantile"]
  G --> J["Final report only"]`;

const FEATURES = `flowchart TD
  A["101,000 images"] --> B["SigLIP-SO400M<br/>428M params · 384px"]
  A --> C["EVA-02-L<br/>304M params · 448px"]
  A --> D["DINOv2-L<br/>304M params · 518px"]
  B --> E["train_x.npy<br/>75,750 × 1152 · float16"]
  C --> F["train_x.npy<br/>75,750 × 1024"]
  D --> G["train_x.npy<br/>75,750 × 1024"]
  E --> H["Cached on disk<br/>inference runs once"]
  F --> H
  G --> H
  H --> I["Every later experiment<br/>takes minutes, not hours"]`;

const PROBE = `flowchart LR
  A["Cached embedding<br/>1152-d"] --> B["L2 normalise"]
  B --> C["Mixup in<br/>embedding space"]
  C --> D["LayerNorm"]
  D --> E["Linear 1152 → 1536"]
  E --> F["GELU"]
  F --> G["Dropout 0.3"]
  G --> H["LayerNorm"]
  H --> I["Linear 1536 → 101"]
  I --> J["Soft-target<br/>cross-entropy"]
  J --> K["AdamW + cosine<br/>40 epochs · ~4 min"]`;

const FINETUNE = `flowchart TD
  A["EVA-02-L pretrained"] --> B["Stage 1 — 224px<br/>6 epochs"]
  B --> C["Stage 2 — 448px<br/>short, closes the<br/>train/test resolution gap"]
  C --> D["Best checkpoint"]
  B -.->|"every epoch"| E["Resumable checkpoint<br/>model · EMA · optimiser · scheduler"]
  C -.-> E
  B --> F["RandAugment · Random Erasing<br/>Mixup · CutMix · label smoothing"]
  A --> G["Layer-wise LR decay 0.75<br/>early layers barely move"]
  D --> H["95.90% test top-1"]`;

const ENSEMBLE = `flowchart TD
  A["SigLIP probe<br/>96.83%"] --> C["Probability average<br/>no trainable parameters"]
  B["EVA-02 probe<br/>95.53%"] --> C
  C --> D["97.16% test top-1"]
  A --> E["McNemar test"]
  D --> E
  E --> F["198 vs 115 discordant<br/>p = 3 × 10⁻⁶ — significant"]
  G["DINOv2 probe<br/>94.87%"] -.->|"tested and rejected:<br/>weakest member drags<br/>the average down"| C`;

const RELIABILITY = `flowchart LR
  A["Raw logits"] --> B["Divide by T<br/>fitted on validation"]
  B --> C["Calibrated probabilities"]
  C --> D["ECE 0.0514 → 0.0062"]
  C --> E["Accuracy unchanged<br/>order-preserving"]
  C --> F["Conformal scores<br/>on validation"]
  F --> G["Quantile q̂<br/>⌈(n+1)(1−α)⌉ / n"]
  G --> H["Prediction set<br/>avg 1.39 labels"]
  H --> I["99.61% measured coverage"]`;

const NUTRITION = `flowchart TD
  A["101 dish classes"] --> B{"Direct USDA<br/>record exists?"}
  B -->|"41 dishes"| C["Match SR Legacy row<br/>penalised text search"]
  B -->|"60 dishes"| D["Compose from ingredients<br/>weighted by grams"]
  C --> E["32 nutrients<br/>per 100g"]
  D --> E
  E --> F["Serving size applied"]
  F --> G["kb.json<br/>provenance per dish"]
  D --> H["Ingredient graph<br/>181 nodes · 323 edges"]`;

const RAG = `flowchart TD
  A["Question"] --> B["Rewrite with the dish<br/>the vision model named"]
  B --> C["BM25<br/>lexical"]
  B --> D["Dense retrieval<br/>bge-small · 384-d"]
  C --> E["Reciprocal Rank Fusion<br/>combines ranks, not scores"]
  D --> E
  E --> F["Rerank<br/>reads query and document together"]
  F --> G{"Anything<br/>relevant?"}
  G -->|"no"| H["Refuse — 70 ms<br/>no LLM call"]
  G -->|"yes"| I["Generate with citations"]
  I --> J["Grounding check<br/>every number verified<br/>against the sources"]
  J --> K["Answer — 98.57% correct<br/>100% grounded"]`;

const SERVING = `flowchart LR
  A["Browser"] --> B["Next.js route handler<br/>forwards the auth token"]
  B --> C["FastAPI on HF Spaces"]
  C --> D["/predict"]
  C --> E["/explain"]
  C --> F["/ask"]
  D --> G["Lazy-loaded weights<br/>thread-locked"]
  E --> G
  F --> H["Retrieval index"]
  G --> I["Prediction · confidence<br/>conformal set · nutrition"]`;

const STAGES = [
  {
    id: "system",
    n: "01",
    title: "THE WHOLE SYSTEM",
    lede: "One photograph in, five things out — each produced by a different part of the pipeline.",
    chart: SYSTEM,
    note: "Confidence and the candidate set come from the same calibrated probabilities, which is why they can never disagree with each other.",
  },
  {
    id: "data",
    n: "02",
    title: "DATA AND THE SPLIT",
    lede: "Food-101 ships only train and test. The validation set is carved out of train, never out of test.",
    chart: DATA,
    note: "Selecting checkpoints on the test split is the standard way projects on this dataset overstate their results. The mask is seeded and shared by both the image and the cached-feature pipelines so they cannot disagree about what is held out.",
  },
  {
    id: "features",
    n: "03",
    title: "THE FROZEN FEATURE BANK",
    lede: "Run the expensive backbones exactly once, then never again.",
    chart: FEATURES,
    note: "This is the decision that made the rest affordable on a laptop. Extraction costs hours; every experiment afterwards costs minutes.",
  },
  {
    id: "probe",
    n: "04",
    title: "PROBE HEAD TRAINING",
    lede: "A 1.9M-parameter head on a cached vector reaches 96.83% in under four minutes.",
    chart: PROBE,
    note: "Pixel-space augmentation is impossible once features are frozen, so Mixup is applied to the embeddings instead.",
  },
  {
    id: "finetune",
    n: "05",
    title: "FULL FINE-TUNING",
    lede: "Updating all 304M parameters — and losing to the probe that took four minutes.",
    chart: FINETUNE,
    note: "Attention cost grows with the square of the token count, so 448px costs about sixteen times what 224px does. Most epochs run cheap; a short high-resolution stage closes the gap at the end.",
  },
  {
    id: "ensemble",
    n: "06",
    title: "ENSEMBLING",
    lede: "A parameter-free average beat a trained 3.97M-parameter fusion head.",
    chart: ENSEMBLE,
    note: "A 0.33-point gap is small enough to demand a significance test rather than a claim. McNemar counts only the images where the two models disagree.",
  },
  {
    id: "reliability",
    n: "07",
    title: "CALIBRATION AND CONFORMAL SETS",
    lede: "Making the confidence figure mean what it says, then attaching a guarantee that can be falsified.",
    chart: RELIABILITY,
    note: "Dividing every logit by the same positive constant cannot change which one is largest, so accuracy is mathematically untouched while calibration improves eightfold.",
  },
  {
    id: "nutrition",
    n: "08",
    title: "THE NUTRITION KNOWLEDGE BASE",
    lede: "Forty-one dishes had a USDA record. Sixty did not, and were rebuilt from ingredients.",
    chart: NUTRITION,
    note: "Composing from weighted ingredients is more honest than borrowing a loosely similar row, and the ingredient lists are what the allergen and substitution logic later needs.",
  },
  {
    id: "rag",
    n: "09",
    title: "GROUNDED RETRIEVAL",
    lede: "Three retrieval stages, then a check that no number reaches the reader unsupported.",
    chart: RAG,
    note: "Out-of-scope questions never reach the language model at all, which is why they are refused in 70 ms and cost nothing. Every box here is a node in a LangGraph state machine, so the path a given answer took is recorded rather than reconstructed.",
  },
  {
    id: "serving",
    n: "10",
    title: "SERVING",
    lede: "Where the trained artefacts actually run.",
    chart: SERVING,
    note: "Weights load lazily behind a lock so the container can answer a health check before the model is in memory, and two simultaneous requests cannot each load 1.5 GB.",
  },
];

export default function PipelinePage() {
  return (
    <main className="flex-1 w-full">
      <div className="relative overflow-hidden">
        <section className="mx-auto max-w-6xl px-5 pt-10 pb-4">
          <Beat
            n="—"
            title="THE PIPELINE"
            lede="Every stage of the system, drawn. Follow it from a photograph on the left to a cited nutrient table on the right — the diagrams are the same ones the report uses."
          />
        </section>

        <Spider3D
          className="absolute right-1 top-0 z-10 w-[128px] h-[170px] opacity-70 sm:w-[170px] sm:h-[210px] sm:opacity-100 xl:right-2 xl:w-[330px] xl:h-[340px]"
          scale={0.8}
          side="right"
          model="/models/slinger.glb"
          fallback={<WebShot targetId="stage-system" corner="tl" pose="crawl" top={-6} />}
        />
      </div>

      <section className="mx-auto max-w-6xl px-5 pb-20">
        {STAGES.map((s, i) => (
          <div key={s.id} id={`stage-${s.id}`}>
            {i > 0 && <GutterRule className="my-10" />}
            <Reveal>
              <div className="flex items-baseline gap-3">
                <span
                  className="figures text-2xl shrink-0"
                  style={{ color: "var(--color-red)" }}
                >
                  {s.n}
                </span>
                <h2 className="font-display text-2xl sm:text-3xl">{s.title}</h2>
              </div>
              <p className="mt-2 max-w-3xl text-[var(--text-dim)]">{s.lede}</p>

              <Panel raised className="mt-5 p-4 sm:p-6">
                <Mermaid chart={s.chart} className="py-2" />
              </Panel>

              <Caption className="mt-3 max-w-3xl">{s.note}</Caption>
            </Reveal>
          </div>
        ))}

        <GutterRule className="my-10" />
        <div className="flex flex-wrap gap-3">
          <Link
            href="/methods"
            className="ink-edge px-5 py-2.5 font-display uppercase tracking-wide"
          >
            The method in prose
          </Link>
          <Link
            href="/benchmarks"
            className="ink-edge px-5 py-2.5 font-display uppercase tracking-wide"
            style={{ background: "var(--color-red)", color: "#f4f1e8" }}
          >
            See the measurements
          </Link>
        </div>
      </section>
    </main>
  );
}
