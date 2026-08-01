import { Analyzer } from "./components/Analyzer";
import { getKb } from "@/lib/kb";

const kb = getKb();

// Headline numbers come from the measured evaluation, not from marketing.
const STATS = [
  { value: "97.16%", label: "Food-101 test top-1", note: "held-out test split, never touched during training" },
  { value: "101", label: "dish categories", note: `${kb.num_classes} classes, each with a USDA-grounded profile` },
  { value: "32", label: "nutrients per dish", note: "macros, minerals and vitamins" },
  { value: "95%", label: "conformal coverage", note: "the candidate set is right this often" },
];

export default function Home() {
  return (
    <main className="flex-1 w-full">
      {/* ── Masthead ─────────────────────────────────────────────── */}
      <header className="border-b-3 border-[var(--line)]">
        <div className="mx-auto max-w-6xl px-5 py-3 flex items-center justify-between gap-4">
          <span className="font-display text-xl tracking-tight">FOODGENOME AI</span>
          <span className="text-xs uppercase tracking-widest text-[var(--text-dim)]">
            Vol. 1 · Food-101
          </span>
        </div>
      </header>

      {/* ── Hero panel ───────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 pt-10 pb-8">
        <div className="grid gap-6 lg:grid-cols-5 items-stretch">
          <div className="panel p-8 lg:col-span-3">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--text-dim)]">
              Computer vision · Conformal prediction · Grounded retrieval
            </p>
            <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl leading-[0.92] mt-3">
              READ THE GENOME
              <br />
              OF YOUR PLATE
            </h1>
            <p className="mt-5 max-w-prose text-lg text-[var(--text-dim)]">
              Photograph a dish. Get the category, an honestly calibrated confidence, the
              full set of candidates the model cannot rule out, and nutrition traced to the
              USDA record it came from.
            </p>
          </div>

          <div className="panel halftone p-8 lg:col-span-2 flex flex-col justify-center">
            <p className="sfx text-5xl leading-none" style={{ color: "var(--color-red)" }}>
              97.16%
            </p>
            <p className="mt-2 font-display text-xl">on a test split it never saw</p>
            <p className="mt-3 text-sm text-[var(--text-dim)]">
              An ensemble of SigLIP-SO400M and EVA-02-L. Validation was carved out of the
              training split so the 25,250-image test set stayed sealed until the end — the
              most common way projects like this overstate themselves.
            </p>
          </div>
        </div>
      </section>

      {/* ── Analyzer ─────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 pb-12">
        <Analyzer />
      </section>

      {/* ── Stat strip ───────────────────────────────────────────── */}
      <section className="border-y-3 border-[var(--line)] halftone">
        <div className="mx-auto max-w-6xl px-5 py-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.label}>
              <p className="figures text-3xl">{s.value}</p>
              <p className="font-display text-sm uppercase tracking-wide mt-1">{s.label}</p>
              <p className="text-xs text-[var(--text-dim)] mt-1">{s.note}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Method ───────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 py-12">
        <h2 className="font-display text-3xl">How it decides</h2>
        <div className="mt-6 grid gap-6 md:grid-cols-3">
          {[
            {
              n: "01",
              title: "Two backbones, averaged",
              body: "SigLIP-SO400M and EVA-02-L each score the image. A parameter-free probability average beat a 3.97M-parameter learned fusion head — and beat it significantly, by exact McNemar test.",
            },
            {
              n: "02",
              title: "Calibrated, not confident",
              body: "Raw softmax is not a probability. The displayed confidence is calibrated against a held-out slice, so 80% means right about 80% of the time.",
            },
            {
              n: "03",
              title: "Grounded in USDA records",
              body: "Every figure traces to a FoodData Central record. Where SR Legacy has no entry for a dish, the profile is composed from weighted ingredients and labelled as composed.",
            },
          ].map((c) => (
            <article key={c.n} className="panel p-6">
              <p className="figures text-sm" style={{ color: "var(--color-red)" }}>
                {c.n}
              </p>
              <h3 className="font-display text-xl mt-1">{c.title}</h3>
              <p className="mt-2 text-sm text-[var(--text-dim)]">{c.body}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="border-t-3 border-[var(--line)]">
        <div className="mx-auto max-w-6xl px-5 py-6 text-sm text-[var(--text-dim)] flex flex-wrap gap-x-6 gap-y-2 justify-between">
          <span>{kb.source}</span>
          <span>{kb.basis}</span>
        </div>
      </footer>
    </main>
  );
}
