import type { Metadata } from "next";
import Link from "next/link";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { GraphSection } from "../components/GraphSection";
import type { GraphData } from "../components/three/GraphWeb";

export const metadata: Metadata = {
  title: "The web — FoodGenome AI",
  description:
    "The dish, ingredient and nutrient graph behind the retrieval system, rendered as an interactive 3D web.",
};

async function loadGraph(): Promise<GraphData> {
  const file = path.join(process.cwd(), "public", "data", "graph.json");
  return JSON.parse(await readFile(file, "utf8")) as GraphData;
}

export default async function WebPage() {
  const data = await loadGraph();

  return (
    <main className="flex-1 w-full">
      <header className="border-b-3 border-[var(--line)]">
        <div className="mx-auto max-w-6xl px-5 py-3 flex items-center justify-between gap-4">
          <Link href="/" className="font-display text-xl tracking-tight">
            FOODGENOME AI
          </Link>
          <nav className="flex gap-4 text-sm uppercase tracking-widest">
            <Link href="/" className="hover:underline">
              Analyse
            </Link>
            <span style={{ color: "var(--color-red)" }}>The web</span>
          </nav>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-5 pt-10 pb-6">
        <p className="text-xs uppercase tracking-[0.2em] text-[var(--text-dim)]">
          GraphRAG · {data.stats.dishes} dishes · {data.stats.ingredients} ingredients
        </p>
        <h1 className="font-display text-5xl sm:text-6xl leading-[0.95] mt-3">
          EVERY DISH IS A STRAND
        </h1>
        <p className="mt-4 max-w-prose text-lg text-[var(--text-dim)]">
          Sixty dishes had no single USDA record, so each was composed from weighted
          ingredient records. Those weights are edges. What began as a workaround for
          missing data is the structure the retrieval system reasons over — and it is
          literally a web.
        </p>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-10">
        <GraphSection data={data} />
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-14 grid gap-6 md:grid-cols-3">
        {[
          {
            n: "01",
            h: "Inversion",
            b: `"Which dishes contain walnuts" is written in no document — it is an inversion of ${data.stats.dishes} separate ingredient lists. The graph answers it; top-k retrieval over those lists cannot.`,
          },
          {
            n: "02",
            h: "Shared structure",
            b: `${data.stats.shared} ingredients appear in more than one dish. Those are the strands that connect the web, and the reason similarity can be computed from recipes rather than from how two dishes happen to be described.`,
          },
          {
            n: "03",
            h: "Cited, not inferred",
            b: "Every edge carries the USDA FoodData Central record it came from, so an answer built on this graph points at a source rather than at a plausible sentence.",
          },
        ].map((c) => (
          <article key={c.n} className="panel p-6">
            <p className="figures text-sm" style={{ color: "var(--color-red)" }}>
              {c.n}
            </p>
            <h2 className="font-display text-xl mt-1">{c.h}</h2>
            <p className="mt-2 text-sm text-[var(--text-dim)]">{c.b}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
