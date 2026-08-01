import {
  MACRO_KEYS,
  MICRO_KEYS,
  formatAmount,
  getKb,
  macroSplit,
} from "@/lib/kb";
import type { PredictResponse } from "@/lib/types";

import { NutrientHelix } from "./NutrientHelix";

const nutrientMeta = getKb().nutrients;

/** Confidence bands pair colour with a label and an icon, because colour is
 *  never allowed to be the sole carrier of meaning. */
function confidenceBand(p: number) {
  if (p >= 0.85) return { label: "High confidence", color: "var(--color-green)", mark: "✓" };
  if (p >= 0.65) return { label: "Moderate confidence", color: "var(--color-amber)", mark: "!" };
  return { label: "Low confidence", color: "var(--color-red)", mark: "?" };
}

export function ResultPanels({ result }: { result: PredictResponse }) {
  const { prediction, conformal, nutrition, ood, model, source } = result;
  const band = confidenceBand(prediction.confidence);
  const split = macroSplit(nutrition.per_serving);
  const entry = nutrition.entry;

  if (!ood.is_food) {
    return (
      <section className="panel p-6 animate-panel-in">
        <p className="sfx text-4xl text-[var(--color-red)]">KRAK</p>
        <h2 className="font-display text-2xl mt-2">Not a food image</h2>
        <p className="mt-2 text-[var(--text-dim)] max-w-prose">
          The out-of-distribution detector rejected this photo with a score of{" "}
          <span className="figures">{ood.score.toFixed(2)}</span> against a threshold of{" "}
          <span className="figures">{ood.threshold.toFixed(2)}</span>. Rejecting confidently
          is a feature: a classifier restricted to 101 categories would otherwise return one
          of them no matter what you gave it.
        </p>
      </section>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5 animate-panel-in">
      {/* ── Verdict ─────────────────────────────────────────────── */}
      <section className="panel p-6 lg:col-span-3">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-xs uppercase tracking-widest text-[var(--text-dim)]">
              {entry.cuisine} · {entry.tags.join(" · ")}
            </p>
            <h2 className="font-display text-4xl sm:text-5xl leading-none mt-1">
              {prediction.title}
            </h2>
          </div>
          <span
            className="sfx text-3xl animate-impact shrink-0"
            style={{ color: "var(--color-red)" }}
          >
            THWIP
          </span>
        </div>

        <div className="mt-5 flex items-center gap-3">
          <span
            className="ink-edge px-2 py-0.5 text-sm font-semibold shrink-0"
            style={{ background: band.color, color: "#0b0b0f" }}
          >
            {band.mark} {band.label}
          </span>
          <span className="figures text-2xl">
            {(prediction.confidence * 100).toFixed(1)}%
          </span>
        </div>

        <div
          className="mt-3 h-4 panel-flat overflow-hidden"
          role="img"
          aria-label={`Calibrated confidence ${(prediction.confidence * 100).toFixed(1)} percent`}
        >
          <div
            className="h-full"
            style={{ width: `${prediction.confidence * 100}%`, background: band.color }}
          />
        </div>

        <p className="mt-3 text-sm text-[var(--text-dim)]">
          Raw softmax was{" "}
          <span className="figures">{(prediction.raw_confidence * 100).toFixed(1)}%</span>.
          The ensemble is measurably under-confident, so the displayed figure is the
          calibrated one — the number that actually corresponds to how often it is right.
        </p>
      </section>

      {/* ── Conformal set ───────────────────────────────────────── */}
      <section className="panel p-6 lg:col-span-2">
        <h3 className="font-display text-xl">
          Prediction set · {Math.round((1 - conformal.alpha) * 100)}% coverage
        </h3>
        <p className="mt-1 text-sm text-[var(--text-dim)]">{conformal.guarantee}</p>
        <ul className="mt-4 space-y-2">
          {conformal.candidates.map((c) => (
            <li key={c.class} className="flex items-center gap-3">
              <span className="flex-1 truncate">{c.title}</span>
              <span className="figures text-sm tabular-nums">
                {(c.probability * 100).toFixed(1)}%
              </span>
              <span
                className="h-3 shrink-0"
                style={{
                  width: `${Math.max(4, c.probability * 70)}px`,
                  background: "var(--color-blue)",
                }}
              />
            </li>
          ))}
        </ul>
        {conformal.candidates.length > 1 && (
          <p className="mt-4 text-sm text-[var(--text-dim)]">
            More than one candidate means the model is genuinely uncertain here. An honest
            set beats a confident single guess.
          </p>
        )}
      </section>

      {/* ── Nutrition ───────────────────────────────────────────── */}
      <section className="panel p-6 lg:col-span-3">
        <div className="flex items-baseline justify-between gap-4 flex-wrap">
          <h3 className="font-display text-xl">Nutrition</h3>
          <span className="text-sm text-[var(--text-dim)]">{nutrition.serving_label}</span>
        </div>

        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {MACRO_KEYS.map((key) => {
            const meta = nutrientMeta[key];
            const value = nutrition.per_serving[key] ?? 0;
            return (
              <div key={key} className="panel-tight p-3">
                <p className="text-xs uppercase tracking-wide text-[var(--text-dim)]">
                  {meta?.name ?? key}
                </p>
                <p className="figures text-xl mt-1">{formatAmount(value, meta?.unit ?? "")}</p>
              </div>
            );
          })}
        </div>

        <div className="mt-5 grid sm:grid-cols-2 gap-5 items-center">
          <div>
            <p className="text-xs uppercase tracking-widest text-[var(--text-dim)] mb-2">
              Macro split by calories
            </p>
            <NutrientHelix nutrients={nutrition.per_serving} />
            <dl className="mt-2 flex gap-4 text-sm">
              {[
                ["Carbs", split.carbs, "var(--color-amber)"],
                ["Protein", split.protein, "var(--color-blue)"],
                ["Fat", split.fat, "var(--color-red)"],
              ].map(([label, share, color]) => (
                <div key={label as string} className="flex items-center gap-1.5">
                  <span
                    className="w-3 h-3 shrink-0 ink-edge"
                    style={{ background: color as string }}
                  />
                  <dt className="sr-only">{label as string}</dt>
                  <dd>
                    <span className="figures">
                      {((share as number) * 100).toFixed(0)}%
                    </span>{" "}
                    {label as string}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">
                Micronutrients per {nutrition.serving_label}
              </caption>
              <tbody>
                {MICRO_KEYS.map((key) => {
                  const meta = nutrientMeta[key];
                  if (!meta) return null;
                  return (
                    <tr key={key} className="border-b border-[var(--line)]/20">
                      <th scope="row" className="text-left font-normal py-1 pr-3">
                        {meta.name}
                      </th>
                      <td className="figures text-right py-1 whitespace-nowrap">
                        {formatAmount(nutrition.per_serving[key] ?? 0, meta.unit)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── Provenance ──────────────────────────────────────────── */}
      <section className="panel p-6 lg:col-span-2">
        <h3 className="font-display text-xl">Where these numbers come from</h3>

        <p className="mt-3 flex items-center gap-2 text-sm">
          <span
            className="ink-edge px-2 py-0.5 font-semibold"
            style={{
              background: entry.method === "direct" ? "var(--color-green)" : "var(--color-amber)",
              color: "#0b0b0f",
            }}
          >
            {entry.method === "direct" ? "✓ Measured" : "! Composed"}
          </span>
          <span className="text-[var(--text-dim)]">
            {entry.method === "direct"
              ? "USDA has this dish directly"
              : "Built from weighted ingredients"}
          </span>
        </p>

        {entry.note && (
          <p className="mt-3 text-sm text-[var(--text-dim)]">{entry.note}</p>
        )}

        {nutrition.components && nutrition.components.length > 0 && (
          <ul className="mt-4 space-y-1.5 text-sm">
            {nutrition.components.map((c) => (
              <li key={`${c.fdc_id}-${c.query}`} className="flex items-baseline gap-2">
                <span className="figures shrink-0 w-14 text-right">{c.grams} g</span>
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
        )}

        {entry.method === "direct" && entry.fdc_id && (
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
        )}

        <p className="mt-4 text-xs text-[var(--text-dim)]">
          {entry.source} · {getKb().basis}
        </p>
      </section>

      {/* ── Model footer ────────────────────────────────────────── */}
      <section className="panel-flat halftone p-4 lg:col-span-5 text-sm flex flex-wrap gap-x-6 gap-y-1 justify-between">
        <span>
          Classifier <strong>{model.name}</strong>
        </span>
        <span>
          Food-101 test top-1 <span className="figures">{model.test_top1.toFixed(2)}%</span>
        </span>
        <span>
          Responded in <span className="figures">{result.latency_ms}</span> ms
        </span>
        <span className="text-[var(--text-dim)]">
          {source === "model" ? "Live model" : "Demo response — model service not connected"}
        </span>
      </section>
    </div>
  );
}
