import type { Metadata } from "next";
import Link from "next/link";

import { Mermaid } from "../components/Mermaid";
import { Reveal } from "../components/Reveal";
import { Spider3D } from "../components/Spider3D";
import { WebShot } from "../components/WebShot";
import { Beat, Caption, GutterRule, Panel, StatPanel } from "../components/comic";

export const metadata: Metadata = {
  title: "The data — FoodGenome AI",
  description:
    "Exploratory analysis of Food-101: class balance, image geometry, colour, leakage detection, and the embedding-space analysis that predicted the model's failures before it was trained.",
};

const EDA_FLOW = `flowchart LR
  A["101,000 images"] --> B["Class balance<br/>count every file"]
  A --> C["Geometry<br/>read headers only"]
  A --> D["Colour<br/>3,939 sample"]
  A --> E["Leakage<br/>nearest neighbour"]
  A --> F["Separability<br/>class centroids"]
  B --> G["No resampling needed"]
  C --> H["RandomResizedCrop"]
  D --> I["color_jitter = 0.3"]
  E --> J["Test estimate trustworthy"]
  F --> K["Failure set predicted<br/>before training"]`;

/* Figures are produced by notebooks/00-eda.ipynb and copied into public/eda,
   so the page cannot show a number the notebook did not compute. */
const SECTIONS = [
  {
    id: "balance",
    n: "01",
    title: "IS IT BALANCED?",
    lede: "The first question for any classifier, because the answer decides whether accuracy is an honest headline or a misleading one.",
    img: "/eda/eda_class_balance.png",
    alt: "Bar charts of images per class for train and test, both perfectly flat",
    body: "Counting the files gives exactly 750 training and 250 test images for every one of the 101 classes. Imbalance ratio 1.0000; standard deviation of class counts, zero.",
    decision:
      "No resampling, undersampling, SMOTE or class weighting. Plain accuracy is honest. Macro- and weighted-averaged metrics must come out identical — which they do, to three decimals, and that is a free correctness check on the evaluation code.",
  },
  {
    id: "geometry",
    n: "02",
    title: "WHAT SHAPE ARE THEY?",
    lede: "Photographs from many different people are not a uniform size, and the resize strategy has to be chosen against the real distribution.",
    img: "/eda/eda_dimensions.png",
    alt: "Histograms of width, height and aspect ratio across the corpus",
    body: "Every image has its longest side capped at exactly 512 px — 100% of files — confirming the authors rescaled the collection. There are 464 distinct width–height pairs. By shape: 61.6% square, 26.0% landscape, 12.5% portrait. All 101,000 exported files are RGB.",
    decision:
      "Backbones need a fixed square input, so resize-then-crop is unavoidable, and on the 38.5% that are not square it will discard part of the frame. That is the argument for RandomResizedCrop: it turns an unavoidable loss into useful variation.",
  },
  {
    id: "colour",
    n: "03",
    title: "HOW ARE THEY LIT?",
    lede: "The backbones normalise with fixed ImageNet statistics, so it is worth knowing how far this dataset departs from them.",
    img: "/eda/eda_colour.png",
    alt: "Per-channel intensity, brightness and contrast histograms",
    body: "Food photography is markedly warm: mean red 0.547 against mean blue 0.345 — a gap of 0.20, where ImageNet's own channel means differ by less than 0.08. The poorly exposed tail is small: 3.83% below brightness 0.25, 0.33% above 0.75.",
    decision:
      "color_jitter=0.3 is justified. The deployment case is a phone camera under unknown lighting, and the model should not come to depend on the white balance of restaurant photography.",
  },
  {
    id: "leakage",
    n: "04",
    title: "IS THE TEST SET CLEAN?",
    lede: "If test images were near-copies of training images, the headline accuracy would be inflated and nobody would see it.",
    img: "/eda/eda_duplicates.png",
    alt: "Histogram of cosine similarity from each test image to its nearest training image",
    body: "Using the cached SigLIP embeddings, the nearest training neighbour was found for all 25,250 test images. Only 22 (0.09%) exceed cosine 0.999, and 111 (0.44%) exceed 0.98. The distribution is centred well below 1.0.",
    decision:
      "No de-duplication needed. The 13.96% above 0.95 is expected in user-uploaded restaurant photography — several people photograph the same dish — and is not leakage in the sense that matters.",
  },
  {
    id: "separability",
    n: "05",
    title: "WHICH CLASSES WILL IT CONFUSE?",
    lede: "The most useful result in the whole analysis, and the only one that made a prediction which could later be checked.",
    img: "/eda/eda_margin.png",
    alt: "Histogram of per-class separability margin, with a long left tail",
    body: "Each class centroid was computed in embedding space, then the cosine similarity between every pair. A margin — within-class tightness minus similarity to the nearest other class — ranks the classes by expected difficulty. No classifier is involved anywhere in this computation.",
    decision:
      "The five smallest margins were steak, filet mignon, chocolate mousse, chocolate cake and pork chop. Four of those five turned out to be among the trained model's five worst classes.",
  },
];

const PREDICTED = [
  { cls: "steak", near: "filet mignon", margin: "−0.125", rank: "1st worst", acc: "78.4%" },
  { cls: "filet mignon", near: "steak", margin: "−0.102", rank: "2nd worst", acc: "87.2%" },
  { cls: "chocolate mousse", near: "chocolate cake", margin: "−0.098", rank: "4th worst", acc: "90.0%" },
  { cls: "chocolate cake", near: "chocolate mousse", margin: "−0.098", rank: "5th worst", acc: "90.4%" },
  { cls: "pork chop", near: "steak", margin: "−0.092", rank: "not in worst 12", acc: "—" },
];

export default function DataPage() {
  return (
    <main className="flex-1 w-full">
      <div className="relative overflow-hidden">
        <section className="mx-auto max-w-6xl px-5 pt-10 pb-4">
          <Beat
            n="—"
            title="THE DATA"
            lede="Exploratory analysis of Food-101, run before a single model was trained. Six questions, each of which changed a decision — and one that predicted where the finished model would fail."
          />
        </section>

        <Spider3D
          className="absolute right-1 top-0 z-10 w-[128px] h-[170px] opacity-70 sm:w-[170px] sm:h-[210px] sm:opacity-100 xl:right-2 xl:w-[330px] xl:h-[340px]"
          scale={0.8}
          side="right"
          model="/models/slinger-b.glb"
          pose={[0.1, -0.5, 0.06]}
          fallback={<WebShot targetId="eda-stats" corner="tl" pose="crawl" top={-6} />}
        />
      </div>

      <section className="mx-auto max-w-6xl px-5 pb-6">
        <div id="eda-stats" className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <StatPanel value="101,000" label="images scanned" note="every file, not a sample" tilt="left" />
          <StatPanel value="1.0000" label="imbalance ratio" note="perfectly balanced" accent="var(--color-blue)" />
          <StatPanel value="0.09%" label="near-duplicates" note="above cosine 0.999" accent="var(--color-green)" tilt="right" />
          <StatPanel value="4 / 5" label="failures predicted" note="before any training" accent="var(--color-red)" />
        </div>

        <Panel raised className="mt-8 p-4 sm:p-6">
          <Mermaid chart={EDA_FLOW} className="py-2" />
        </Panel>
        <Caption className="mt-3 max-w-3xl">
          Each analysis exists because its answer changed something downstream. An
          exploratory step that could not have changed a decision is decoration.
        </Caption>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-20">
        {SECTIONS.map((s) => (
          <div key={s.id} id={`eda-${s.id}`}>
            <GutterRule className="my-10" />
            <Reveal>
              <div className="flex items-baseline gap-3">
                <span className="figures text-2xl shrink-0" style={{ color: "var(--color-red)" }}>
                  {s.n}
                </span>
                <h2 className="font-display text-2xl sm:text-3xl">{s.title}</h2>
              </div>
              <p className="mt-2 max-w-3xl text-[var(--text-dim)]">{s.lede}</p>

              <Panel raised className="mt-5 p-3 sm:p-5">
                <img
                  src={s.img}
                  alt={s.alt}
                  className="block w-full h-auto"
                  loading="lazy"
                  decoding="async"
                />
              </Panel>

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <p className="text-sm">{s.body}</p>
                <Panel className="p-4">
                  <p className="text-[10px] uppercase tracking-widest text-[var(--text-dim)]">
                    What it changed
                  </p>
                  <p className="mt-1 text-sm">{s.decision}</p>
                </Panel>
              </div>
            </Reveal>
          </div>
        ))}

        <GutterRule className="my-10" />

        <Reveal>
          <h2 className="font-display text-2xl sm:text-3xl">THE PREDICTION, CHECKED</h2>
          <p className="mt-2 max-w-3xl text-[var(--text-dim)]">
            The separability analysis was run before any classifier existed. Once the
            model was trained and evaluated on the sealed test split, the two lists
            could be compared. This table is the comparison.
          </p>

          <Panel raised className="mt-5 p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b-3 border-[var(--line)]">
                  <th className="text-left p-3 font-display">Predicted hardest</th>
                  <th className="text-left p-3 font-display">Nearest class</th>
                  <th className="text-right p-3 font-display">Margin</th>
                  <th className="text-left p-3 font-display">Actual rank</th>
                  <th className="text-right p-3 font-display">Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {PREDICTED.map((r) => (
                  <tr key={r.cls} className="border-b border-[var(--line)]">
                    <td className="p-3 font-semibold">{r.cls}</td>
                    <td className="p-3 text-[var(--text-dim)]">{r.near}</td>
                    <td className="p-3 text-right figures">{r.margin}</td>
                    <td
                      className="p-3"
                      style={{ color: r.rank.startsWith("not") ? "var(--text-dim)" : "var(--color-red)" }}
                    >
                      {r.rank}
                    </td>
                    <td className="p-3 text-right figures">{r.acc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          <Caption className="mt-3 max-w-3xl">
            Four of the five classes predicted hardest from embedding geometry alone
            are among the model&rsquo;s five worst. The easiest prediction held too:
            edamame, the largest margin in the dataset, scored 100.0%. This relocates
            the residual error — the categories overlap in feature space before any
            model is trained, so what remains is a property of the label taxonomy
            rather than a training deficiency.
          </Caption>

          <Panel raised className="mt-6 p-4 sm:p-5">
            <img
              src="/eda/eda_pca.png"
              alt="PCA projection of the 101 class centroids, labelled"
              className="block w-full h-auto"
              loading="lazy"
              decoding="async"
            />
          </Panel>
          <Caption className="mt-3 max-w-3xl">
            The 101 class centroids projected to two dimensions. Desserts, salads,
            soups and meat dishes form loose neighbourhoods; the pairs that later
            cause errors sit almost on top of one another. PCA rather than t-SNE,
            because it is linear and deterministic — so distances in the plot stay
            interpretable, which is the whole point when the claim is about which
            classes are close.
          </Caption>
        </Reveal>

        <GutterRule className="my-10" />
        <div className="flex flex-wrap gap-3">
          <Link href="/pipeline" className="ink-edge px-5 py-2.5 font-display uppercase tracking-wide">
            The pipeline
          </Link>
          <Link
            href="/benchmarks"
            className="ink-edge px-5 py-2.5 font-display uppercase tracking-wide"
            style={{ background: "var(--color-red)", color: "#f4f1e8" }}
          >
            Where it ended up
          </Link>
        </div>
      </section>
    </main>
  );
}
