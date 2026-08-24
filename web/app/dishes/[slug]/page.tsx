import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Caption, InkSplit, Panel } from "../../components/comic";
import { NutrientHelix } from "../../components/NutrientHelix";
import {
  MACRO_KEYS,
  MICRO_KEYS,
  formatAmount,
  getEntry,
  getKb,
  macroSplit,
} from "@/lib/kb";

type Params = { params: Promise<{ slug: string }> };

// All 101 pages are prerendered.
export function generateStaticParams() {
  return getKb().entries.map((e) => ({ slug: e.class }));
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const entry = getEntry(slug);
  if (!entry) return { title: "Not found — FoodGenome AI" };
  const kcal = Math.round(entry.nutrients_per_serving.energy_kcal ?? 0);
  return {
    title: `${entry.title} — nutrition, ingredients and sources`,
    description: `${entry.title}: ${kcal} kcal per ${entry.serving_label}, with every figure traced to its USDA FoodData Central record.`,
  };
}

const nutrients = getKb().nutrients;

export default async function DishPage({ params }: Params) {
  const { slug } = await params;
  const entry = getEntry(slug);
  if (!entry) notFound();

  const split = macroSplit(entry.nutrients_per_serving);
  const all = getKb().entries;
  const index = all.findIndex((e) => e.class === slug);
  const prev = all[(index - 1 + all.length) % all.length];
  const next = all[(index + 1) % all.length];

  // Where this dish sits against the other 100 on calories, which is the comparison a
  // reader actually wants and no single record can give.
  const sortedKcal = [...all].sort(
    (a, b) => (b.nutrients_per_100g.energy_kcal ?? 0) - (a.nutrients_per_100g.energy_kcal ?? 0),
  );
  const kcalRank = sortedKcal.findIndex((e) => e.class === slug) + 1;

  return (
    <main className="flex-1 w-full">
      <section className="mx-auto max-w-6xl px-5 pt-8">
        <nav className="text-xs uppercase tracking-widest text-[var(--text-dim)]">
          <Link href="/dishes" className="hover:underline">
            Dishes
          </Link>
          <span aria-hidden="true"> / </span>
          <span>{entry.title}</span>
        </nav>

        <div className="mt-4 grid gap-6 sm:grid-cols-[196px_1fr] sm:items-end">
          {/* The representative photograph: the training image nearest this
              class's centroid in embedding space, so it is the dataset's most
              typical example of the dish rather than an arbitrary one. */}
          <div
            className="dish-thumb relative w-40 sm:w-full border-3 border-[var(--line)] overflow-hidden bg-[var(--panel)]"
            style={{ boxShadow: "7px 7px 0 var(--line)" }}
          >
            <img
              src={`/dishes/${slug}.webp`}
              alt={`${entry.title}, a representative photograph from the Food-101 dataset`}
              width={512}
              height={512}
              decoding="async"
              className="block w-full aspect-square object-cover halftone-img"
            />
          </div>

          <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-5xl sm:text-6xl leading-none">
              <InkSplit>{entry.title.toUpperCase()}</InkSplit>
            </h1>
            <p className="mt-2 text-[var(--text-dim)]">
              {entry.cuisine} · {entry.tags.join(" · ")} · {entry.serving_label}
            </p>
          </div>
          <span
            className="ink-edge px-3 py-1 text-sm font-semibold"
            style={{
              background:
                entry.method === "direct" ? "var(--color-green)" : "var(--color-amber)",
              color: "#0b0b0f",
            }}
          >
            {entry.method === "direct" ? "✓ Measured by USDA" : "! Composed from ingredients"}
          </span>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-8 grid gap-6 lg:grid-cols-3">
        {/* Macros */}
        <Panel raised className="p-6 lg:col-span-2">
          <h2 className="font-display text-xl">Per {entry.serving_label}</h2>
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {MACRO_KEYS.map((key) => (
              <div key={key} className="panel-tight p-3">
                <p className="text-xs uppercase tracking-wide text-[var(--text-dim)]">
                  {nutrients[key]?.name ?? key}
                </p>
                <p className="figures text-2xl mt-1">
                  {formatAmount(entry.nutrients_per_serving[key] ?? 0, nutrients[key]?.unit ?? "")}
                </p>
                <p className="text-[10px] text-[var(--text-dim)] mt-0.5">
                  {formatAmount(entry.nutrients_per_100g[key] ?? 0, nutrients[key]?.unit ?? "")} per 100 g
                </p>
              </div>
            ))}
          </div>

          <div className="mt-6 grid sm:grid-cols-2 gap-6 items-center">
            <div>
              <p className="text-xs uppercase tracking-widest text-[var(--text-dim)] mb-2">
                Energy by macronutrient
              </p>
              <NutrientHelix nutrients={entry.nutrients_per_serving} />
              <dl className="mt-2 flex gap-4 text-sm">
                {[
                  ["Carbs", split.carbs, "var(--color-amber)"],
                  ["Protein", split.protein, "var(--color-blue)"],
                  ["Fat", split.fat, "var(--color-red)"],
                ].map(([label, share, colour]) => (
                  <div key={label as string} className="flex items-center gap-1.5">
                    <span
                      className="w-3 h-3 ink-edge shrink-0"
                      style={{ background: colour as string }}
                    />
                    <dt className="sr-only">{label as string}</dt>
                    <dd>
                      <span className="figures">{((share as number) * 100).toFixed(0)}%</span>{" "}
                      {label as string}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">Micronutrients per serving</caption>
                <tbody>
                  {MICRO_KEYS.map((key) => {
                    const meta = nutrients[key];
                    if (!meta) return null;
                    return (
                      <tr key={key} className="border-b border-[var(--line)]/20">
                        <th scope="row" className="text-left font-normal py-1 pr-3">
                          {meta.name}
                        </th>
                        <td className="figures text-right py-1 whitespace-nowrap">
                          {formatAmount(entry.nutrients_per_serving[key] ?? 0, meta.unit)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </Panel>

        {/* Provenance */}
        <Panel className="p-6">
          <h2 className="font-display text-xl">Provenance</h2>
          {entry.note && (
            <p className="mt-3 text-sm text-[var(--text-dim)]">{entry.note}</p>
          )}

          {entry.components && entry.components.length > 0 ? (
            <>
              <p className="mt-4 text-xs uppercase tracking-widest text-[var(--text-dim)]">
                Composed from {entry.components.length} USDA records
              </p>
              <ul className="mt-2 space-y-1.5 text-sm">
                {entry.components.map((c) => (
                  <li key={`${c.fdc_id}-${c.query}`} className="flex items-baseline gap-2">
                    <span className="figures w-12 text-right shrink-0">{c.grams} g</span>
                    <span className="flex-1">{c.description}</span>
                    {c.fdc_id && (
                      <a
                        href={`https://fdc.nal.usda.gov/food-details/${c.fdc_id}/nutrients`}
                        target="_blank"
                        rel="noreferrer"
                        className="figures text-xs underline shrink-0"
                        style={{ color: "var(--color-blue)" }}
                      >
                        #{c.fdc_id}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            entry.fdc_id && (
              <p className="mt-4 text-sm">
                <a
                  href={`https://fdc.nal.usda.gov/food-details/${entry.fdc_id}/nutrients`}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                  style={{ color: "var(--color-blue)" }}
                >
                  {entry.description} · USDA #{entry.fdc_id}
                </a>
              </p>
            )
          )}

          <div className="mt-6 panel-tight p-3">
            <p className="text-xs uppercase tracking-wide text-[var(--text-dim)]">
              Calorie rank
            </p>
            <p className="figures text-2xl mt-1">
              {kcalRank}
              <span className="text-sm text-[var(--text-dim)]"> of {all.length}</span>
            </p>
            <p className="text-xs text-[var(--text-dim)] mt-1">
              by energy per 100 g, highest first
            </p>
          </div>

          <p className="mt-4 text-xs text-[var(--text-dim)]">{entry.source}</p>
        </Panel>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-8">
        <Caption className="max-w-3xl">
          {entry.method === "direct"
            ? "These figures come from a single USDA record for this dish, so they are measured rather than assembled."
            : "USDA SR Legacy has no record for this dish, so the profile is a weighted combination of its ingredients. That carries more uncertainty than a measured record, which is why it is labelled."}
        </Caption>
      </section>

      <nav className="mx-auto max-w-6xl px-5 pb-16 flex justify-between gap-4 text-sm">
        <Link href={`/dishes/${prev.class}`} className="panel px-4 py-3 hover:-translate-y-0.5 transition-transform">
          ← {prev.title}
        </Link>
        <Link href={`/dishes/${next.class}`} className="panel px-4 py-3 text-right hover:-translate-y-0.5 transition-transform">
          {next.title} →
        </Link>
      </nav>
    </main>
  );
}
