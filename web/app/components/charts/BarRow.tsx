"use client";

import { useState } from "react";

import { CATEGORICAL, GRID, SEQUENTIAL } from "./palette";

/** Horizontal bars for comparing magnitude across named categories.
 *
 *  Horizontal rather than vertical because the categories here have long names —
 *  "graph_inversion", "nutrient_lookup" — and rotated axis labels are a reliable
 *  way to make a chart unreadable.
 *
 *  Sequential by default: one hue, more-is-darker. Categorical colour would imply
 *  the categories are the subject, when the job is comparing sizes. An `emphasis`
 *  option exists for the common case where one row is the story and the rest are
 *  context — that reads far better than five competing hues.
 */

export type BarDatum = { label: string; value: number; note?: string };

export function BarRow({
  data,
  max = 100,
  unit = "%",
  emphasis,
  height = 22,
}: {
  data: BarDatum[];
  max?: number;
  unit?: string;
  /** Label of the one row that carries the story; the rest recede. */
  emphasis?: string;
  height?: number;
}) {
  const [hover, setHover] = useState<string | null>(null);

  const colourFor = (d: BarDatum, i: number) => {
    if (emphasis) return d.label === emphasis ? CATEGORICAL[0] : "color-mix(in oklab, var(--line) 22%, transparent)";
    // More-is-darker within the sequential ramp, by rank rather than raw value so
    // a cluster of similar numbers still separates visually.
    const rank = [...data].sort((a, b) => a.value - b.value).findIndex((x) => x.label === d.label);
    const step = Math.min(SEQUENTIAL.length - 1, 1 + Math.floor((rank / Math.max(1, data.length - 1)) * (SEQUENTIAL.length - 2)));
    return SEQUENTIAL[step];
  };

  return (
    <div>
      <ul className="space-y-2">
        {data.map((d, i) => {
          const pct = Math.max(0, Math.min(1, d.value / max));
          const lit = hover === d.label;
          return (
            <li
              key={d.label}
              className="grid grid-cols-[9rem_1fr_4.5rem] gap-3 items-center"
              onMouseEnter={() => setHover(d.label)}
              onMouseLeave={() => setHover(null)}
            >
              <span className="text-sm truncate" title={d.label}>
                {d.label.replace(/_/g, " ")}
              </span>

              <div
                className="relative"
                style={{ height, background: GRID, borderRadius: 2 }}
                role="img"
                aria-label={`${d.label}: ${d.value}${unit}`}
              >
                <div
                  style={{
                    width: `${pct * 100}%`,
                    height: "100%",
                    background: colourFor(d, i),
                    // Rounded at the data end, square at the baseline.
                    borderRadius: "0 4px 4px 0",
                    transition: "filter 120ms",
                    filter: lit ? "brightness(1.12)" : undefined,
                  }}
                />
              </div>

              {/* Direct label on every row is acceptable here: there are few rows
                  and the number *is* the content, not an annotation on a trend. */}
              <span className="figures text-sm text-right">
                {d.value.toFixed(1)}
                {unit}
              </span>
            </li>
          );
        })}
      </ul>

      {hover && data.find((d) => d.label === hover)?.note && (
        <p className="mt-3 text-xs text-[var(--text-dim)]" aria-live="polite">
          {data.find((d) => d.label === hover)?.note}
        </p>
      )}
    </div>
  );
}
