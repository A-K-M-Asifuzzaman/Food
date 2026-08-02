import Link from "next/link";

import { Beat, Caption, GutterRule, InkSplit, Panel, Sfx, StatPanel } from "./components/comic";
import { getKb } from "@/lib/kb";

const kb = getKb();

export default function Home() {
  return (
    <main className="flex-1 w-full">
      {/* ── Splash page ─────────────────────────────────────────────────
          A comic opens on a splash: one dominant panel, the title breaking its
          own frame, smaller panels crowding the edge. */}
      <section className="relative overflow-hidden border-b-3 border-[var(--line)]">
        <div className="absolute inset-0 halftone-shade opacity-60" aria-hidden="true" />

        <div className="relative mx-auto max-w-6xl px-5 py-14 sm:py-20">
          <div className="grid gap-8 lg:grid-cols-12 items-start">
            <div className="lg:col-span-7">
              <p className="text-xs uppercase tracking-[0.28em] text-[var(--text-dim)]">
                Issue 01 · Vision · Conformal prediction · Grounded retrieval
              </p>

              <h1 className="font-display leading-[0.92] mt-4 text-[3.2rem] sm:text-[4.6rem] lg:text-[5.6rem]">
                <InkSplit>READ THE</InkSplit>
                <br />
                <InkSplit>GENOME OF</InkSplit>
                <br />
                <span style={{ color: "var(--color-red)" }}>
                  <InkSplit>YOUR PLATE</InkSplit>
                </span>
              </h1>

              <p className="mt-6 max-w-xl text-lg text-[var(--text-dim)]">
                Photograph a dish. Get the category, an honestly calibrated confidence, the
                full set of candidates the model cannot rule out, and nutrition traced to
                the USDA record it came from.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href="/analyze"
                  className="ink-edge px-6 py-3 font-display text-lg uppercase tracking-wide"
                  style={{ background: "var(--color-red)", color: "#f4f1e8" }}
                >
                  Analyse a photo
                </Link>
                <Link
                  href="/benchmarks"
                  className="ink-edge px-6 py-3 font-display text-lg uppercase tracking-wide"
                >
                  See the evidence
                </Link>
              </div>
            </div>

            {/* Panels stack with a shared gutter and alternate their tilt, which
                gives the off-axis comic feel without absolute positioning that
                collides the moment the type reflows. */}
            <div className="lg:col-span-5 flex flex-col gap-5 lg:pl-6">
              <Panel raised tilt="right" web className="p-6 pt-8">
                <p className="text-xs uppercase tracking-widest text-[var(--text-dim)] pl-14">
                  Food-101 test split
                </p>
                <p
                  className="figures text-5xl sm:text-6xl leading-none mt-2"
                  style={{ color: "var(--color-red)" }}
                >
                  97.16%
                </p>
                <p className="font-display text-lg mt-1">top-1 accuracy</p>
                <p className="mt-3 text-sm text-[var(--text-dim)]">
                  SigLIP-SO400M and EVA-02-L, averaged. Validation was carved out of the
                  training split so all 25,250 test images stayed sealed until the end.
                </p>
              </Panel>

              <div className="flex items-end gap-4">
                <Panel tilt="left" className="p-4 flex-1">
                  <p className="figures text-3xl" style={{ color: "var(--color-blue)" }}>
                    99.56%
                  </p>
                  <p className="text-xs uppercase tracking-wide font-display mt-1">
                    conformal coverage
                  </p>
                  <p className="text-xs text-[var(--text-dim)] mt-1">
                    measured · average 1.54 candidates
                  </p>
                </Panel>
                <span className="text-3xl sm:text-4xl shrink-0 pb-2">
                  <Sfx>THWIP</Sfx>
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Stat strip ──────────────────────────────────────────────────── */}
      <section className="border-b-3 border-[var(--line)]">
        <div className="mx-auto max-w-6xl px-5 py-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <StatPanel
            value="101"
            label="dish categories"
            note="each with a USDA-grounded profile"
            tilt="left"
          />
          <StatPanel
            value="32"
            label="nutrients per dish"
            note="macros, minerals, vitamins"
            accent="var(--color-blue)"
          />
          <StatPanel
            value="693"
            label="retrieval documents"
            note="577 written + 116 graph facts"
            accent="var(--color-blue)"
            tilt="right"
          />
          <StatPanel
            value="98.6%"
            label="RAG answers correct"
            note="76-case gold set, 100% grounded"
            accent="var(--color-green)"
          />
        </div>
      </section>

      {/* ── How it decides ──────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <Beat
          n="01"
          title="HOW IT DECIDES"
          lede="Three commitments, each of which cost something to keep."
        />

        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {[
            {
              h: "Two backbones, averaged",
              b: "SigLIP-SO400M and EVA-02-L each score the image. A parameter-free probability average beat a 3.97M-parameter learned fusion head — significantly, by exact McNemar test.",
              link: "/benchmarks",
              cta: "See the ablation",
            },
            {
              h: "Calibrated, not confident",
              b: "Raw softmax is not a probability. Temperature fitted on held-out data cut expected calibration error eightfold, so 80% now means right about 80% of the time.",
              link: "/methods#calibration",
              cta: "See the reliability curve",
            },
            {
              h: "It refuses to guess",
              b: "Questions outside the knowledge base are declined in under 130ms without calling a language model, and no answer states a number that is not in a cited source.",
              link: "/methods#grounding",
              cta: "See the grounding gate",
            },
          ].map((c, i) => (
            <Panel key={c.h} tilt={i === 1 ? "right" : "none"} className="p-6 flex flex-col">
              <h3 className="font-display text-xl">{c.h}</h3>
              <p className="mt-2 text-sm text-[var(--text-dim)] flex-1">{c.b}</p>
              <Link
                href={c.link}
                className="mt-4 inline-block py-1.5 text-sm font-semibold underline"
                style={{ color: "var(--color-blue)" }}
              >
                {c.cta} →
              </Link>
            </Panel>
          ))}
        </div>

        <Caption className="mt-8 max-w-3xl">
          Most projects like this report a single accuracy figure. This one reports the
          experiments that failed too — a learned fusion head that lost to an average, and a
          third backbone that earned no place in the ensemble.
        </Caption>
      </section>

      <GutterRule />

      {/* ── The web ─────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <div className="grid gap-8 lg:grid-cols-2 items-center">
          <div>
            <Beat
              n="02"
              title="EVERY DISH IS A STRAND"
              lede="Sixty dishes had no single USDA record, so each was composed from weighted ingredient records. Those weights became a graph — and the graph answers questions no document contains."
            />
            <ul className="mt-6 space-y-2 text-sm">
              {[
                "Which dishes contain walnuts — an inversion of 60 ingredient lists",
                "What two dishes share, and what sets them apart",
                "Which dishes are closest by recipe rather than by description",
              ].map((t) => (
                <li key={t} className="flex gap-2">
                  <span style={{ color: "var(--color-red)" }}>▸</span>
                  <span className="text-[var(--text-dim)]">{t}</span>
                </li>
              ))}
            </ul>
            <Link
              href="/explore"
              className="inline-block mt-6 ink-edge px-5 py-2.5 font-display uppercase tracking-wide"
              style={{ background: "var(--color-blue)", color: "#f4f1e8" }}
            >
              Open the web
            </Link>
          </div>

          <Panel raised tilt="right" className="p-6 halftone-shade">
            <dl className="grid grid-cols-3 gap-4 text-center">
              {[
                ["60", "dishes"],
                ["121", "ingredients"],
                ["323", "edges"],
              ].map(([v, l]) => (
                <div key={l}>
                  <dd className="figures text-3xl" style={{ color: "var(--color-red)" }}>
                    {v}
                  </dd>
                  <dt className="text-xs uppercase tracking-wide mt-1">{l}</dt>
                </div>
              ))}
            </dl>
            <p className="mt-5 text-sm text-[var(--text-dim)]">
              Every edge carries the FoodData Central record it came from, so an answer
              built on this graph points at a source rather than at a plausible sentence.
            </p>
          </Panel>
        </div>
      </section>

      <GutterRule />

      {/* ── Closing ─────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 py-16 text-center">
        <h2 className="font-display text-4xl sm:text-5xl leading-none">
          <InkSplit>PHOTOGRAPH SOMETHING</InkSplit>
        </h2>
        <p className="mt-4 text-[var(--text-dim)] max-w-xl mx-auto">
          {kb.num_classes} categories, {kb.entries.length} grounded nutrition profiles, and a
          model that tells you when it is not sure.
        </p>
        <Link
          href="/analyze"
          className="inline-block mt-7 ink-edge px-8 py-4 font-display text-xl uppercase tracking-wide"
          style={{ background: "var(--color-red)", color: "#f4f1e8" }}
        >
          Start
        </Link>
      </section>
    </main>
  );
}
