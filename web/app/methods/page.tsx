import type { Metadata } from "next";
import Link from "next/link";

import { Reveal } from "../components/Reveal";
import { Spider3D } from "../components/Spider3D";
import { WebShot } from "../components/WebShot";
import { Beat, Caption, GutterRule, Panel } from "../components/comic";
import { calibration, ensembleReport } from "@/lib/reports";

export const metadata: Metadata = {
  title: "How it decides — FoodGenome AI",
  description:
    "The method behind the model: the ensemble, calibration, conformal prediction, abstention, retrieval and the grounding gate — including what does not work.",
};

const STAGES = [
  {
    id: "features",
    n: "01",
    title: "A FROZEN FEATURE BANK",
    body: "Three backbones — SigLIP-SO400M, EVA-02-L and DINOv2-L — were run once over all 101,000 images and their embeddings cached. That took about twenty hours and made every experiment afterwards finish in seconds instead of hours. The cache is the reason this project could afford to be rigorous: calibration, conformal sets, abstention and every ensemble combination were re-run dozens of times against it.",
  },
  {
    id: "ensemble",
    n: "02",
    title: "AVERAGING BEAT LEARNING",
    body: "A gated fusion head with 3.97M parameters was trained for 21.9 minutes to learn how to weigh the backbones per image. A parameter-free average of their probabilities, computed in milliseconds, beat it — and by exact McNemar test the fusion head did not significantly outperform its own best single input. The average is what ships.",
  },
  {
    id: "calibration",
    n: "03",
    title: "CONFIDENCE THAT MEANS SOMETHING",
    body: "Raw softmax output is not a probability. Fitting one temperature on held-out data cut expected calibration error from 0.051 to 0.006 — an eightfold improvement — and moved mean confidence from 92.0% to 96.6% against 97.16% accuracy. Notably the model was under-confident, not over-confident, which is the less common direction and means the correction sharpens rather than softens.",
  },
  {
    id: "conformal",
    n: "04",
    title: "A GUARANTEE, NOT A FEELING",
    body: "A conformal prediction set covers the true class 99.56% of the time, measured on 25,250 held-out images, at an average of 1.54 candidates. That is a property of the procedure rather than a claim about any single image, and it holds without assuming anything about the model. Below 97% coverage the machinery is pointless here — top-1 accuracy alone already satisfies it.",
  },
  {
    id: "abstention",
    n: "05",
    title: "KNOWING WHEN TO SAY NOTHING",
    body: "Two signals decide whether to answer at all: the calibrated maximum probability, and the size of the conformal set. Neither is sufficient alone — a flat blue image scored 0.43 on the first and slipped through, while the second caught it at eight candidates. Together they abstain on 2.28% of real food and raise accuracy on what remains from 97.16% to 97.94%.",
  },
  {
    id: "retrieval",
    n: "06",
    title: "RETRIEVAL THAT KNOWS THE DISH",
    body: "BM25 and a bi-encoder fail differently, so their ranks are fused rather than their scores, then reranked by a cross-encoder. Crucially, the question is rewritten to name the dish the vision model already identified — real questions say \"how much sodium is in this\", and against 101 near-identical sodium documents no retriever can resolve that pronoun on its own.",
  },
  {
    id: "grounding",
    n: "07",
    title: "IT CANNOT INVENT A NUMBER",
    body: "Every quantity in a generated answer is checked against the retrieved sources, matched per unit so milligrams can never be supported by the same digits in grams. An answer that fails is withheld and a deterministic summary served instead. On the first live query the gate caught a figure that was arithmetically correct but appeared in no source — the fix was to put the number in the corpus, not to loosen the check.",
  },
];

const LIMITS = [
  ["Attribution is diffuse.", "Grad-CAM localises at 0.87× chance on this architecture — better than random but not sharply on the food. The probe never sees the image, only a globally pooled vector, so position is partly discarded before classification. The attention-pooling map is worse still, at 1.14×, which reproduces the known artefact where transformers park high attention on empty background patches."],
  ["Composed nutrition carries more uncertainty.", "60 of the 101 dishes have no single USDA record and were built from weighted ingredients. Those figures are estimates, and every surface says so rather than presenting them as measurements."],
  ["The knowledge base is a fixed 101 classes.", "Anything outside Food-101 is refused rather than guessed at. That is a deliberate limit, not an oversight — a classifier restricted to 101 categories would otherwise return one of them for a photograph of a car."],
  ["Abstention is not a trained OOD detector.", "It reports that the model is lost, which correlates with but is not the same as \"this is not food\". A real detector needs non-food negatives to train against."],
];

export default function MethodsPage() {
  const cal = calibration.ensemble;
  return (
    <main className="flex-1 w-full">
      <Reveal>
      <div className="relative overflow-hidden">
      <section className="mx-auto max-w-6xl px-5 pt-10 pb-8">
        <Beat
          n="—"
          title="HOW IT DECIDES"
          lede="Seven stages, each with a measurement behind it. Where something did not work, it says so — a method section that only reports successes is advertising."
        />
      </section>

        <Spider3D
          className="absolute right-2 top-0 z-10 hidden xl:block w-[330px] h-[340px]"
          scale={0.8}
          side="right"
          model="/models/slinger-b.glb"
          pose={[0.1, -0.5, 0.06]}
          fallback={<WebShot targetId="features" corner="tl" pose="crawl" top={-6} />}
        />
      <section className="mx-auto max-w-6xl px-5 pb-12 space-y-6">
        {STAGES.map((s, i) => (
          <Panel key={s.id} id={s.id} tilt={i % 3 === 1 ? "right" : "none"} className="p-6 scroll-mt-24">
            <div className="grid gap-4 md:grid-cols-[4rem_1fr]">
              <p className="figures text-3xl" style={{ color: "var(--color-red)" }}>
                {s.n}
              </p>
              <div>
                <h2 className="font-display text-2xl leading-none">{s.title}</h2>
                <p className="mt-3 text-[var(--text-dim)] max-w-prose">{s.body}</p>
              </div>
            </div>
          </Panel>
        ))}
      </section>
      </div>

      <GutterRule />

      <section className="mx-auto max-w-6xl px-5 py-12" id="limits">
        <Beat
          n="—"
          title="WHAT IT CANNOT DO"
          lede="Every one of these was found by measuring rather than assumed, and none of them is hidden in the interface."
        />
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {LIMITS.map(([title, body]) => (
            <Panel key={title} className="p-5">
              <h3 className="font-display text-lg">{title}</h3>
              <p className="mt-2 text-sm text-[var(--text-dim)]">{body}</p>
            </Panel>
          ))}
        </div>

        <Caption className="mt-8 max-w-3xl">
          Validation is a fixed 4% class-stratified slice carved out of the training split,
          seed 1337. The {ensembleReport.n_test.toLocaleString()}-image test set was untouched
          until final evaluation — reporting model-selection numbers on test is the single
          most common way projects like this overstate themselves.
        </Caption>

        <p className="mt-8 text-sm">
          <Link href="/benchmarks" className="underline" style={{ color: "var(--color-blue)" }}>
            Every measured figure is on the benchmarks page →
          </Link>
        </p>
      </section>
      </Reveal>
    </main>
  );
}
