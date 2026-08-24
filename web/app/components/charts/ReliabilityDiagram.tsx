"use client";

import { useId, useState } from "react";

import type { CalibrationBin } from "@/lib/reports";
import { AXIS, CATEGORICAL, GRID } from "./palette";

/** Confidence against observed accuracy, with the diagonal a perfect model sits on. */

const W = 460;
const H = 340;
const PAD = { top: 16, right: 16, bottom: 42, left: 46 };
const MIN_COUNT = 25;

type Series = { label: string; bins: CalibrationBin[]; colour: string };

function scaleX(v: number) {
  return PAD.left + v * (W - PAD.left - PAD.right);
}
function scaleY(v: number) {
  return H - PAD.bottom - v * (H - PAD.top - PAD.bottom);
}

export function ReliabilityDiagram({
  before,
  after,
}: {
  before: CalibrationBin[];
  after: CalibrationBin[];
}) {
  const id = useId();
  const [hover, setHover] = useState<{ s: number; i: number } | null>(null);

  const series: Series[] = [
    { label: "Raw softmax", bins: before.filter((b) => b.count >= MIN_COUNT), colour: CATEGORICAL[1] },
    { label: "Calibrated", bins: after.filter((b) => b.count >= MIN_COUNT), colour: CATEGORICAL[0] },
  ];

  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const active = hover ? series[hover.s].bins[hover.i] : null;

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        role="img"
        aria-labelledby={`${id}-title`}
      >
        <title id={`${id}-title`}>
          Reliability diagram: predicted confidence against observed accuracy, before and
          after temperature scaling
        </title>

        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={scaleY(t)} y2={scaleY(t)} stroke={GRID} strokeWidth={1} />
            <text x={PAD.left - 8} y={scaleY(t) + 4} textAnchor="end" fontSize="10" fill="var(--text-dim)" className="figures">
              {(t * 100).toFixed(0)}
            </text>
            <text x={scaleX(t)} y={H - PAD.bottom + 16} textAnchor="middle" fontSize="10" fill="var(--text-dim)" className="figures">
              {(t * 100).toFixed(0)}
            </text>
          </g>
        ))}

        {/* Perfect calibration. Dashed because it is a reference, not data. */}
        <line
          x1={scaleX(0)}
          y1={scaleY(0)}
          x2={scaleX(1)}
          y2={scaleY(1)}
          stroke={AXIS}
          strokeWidth={1.5}
          strokeDasharray="5 4"
        />
        {/* Placed below the diagonal: both series run above it here, so the
            space underneath is the only region guaranteed to be empty. */}
        <text
          x={scaleX(0.5)}
          y={scaleY(0.36)}
          fontSize="10"
          fill="var(--text-dim)"
          transform={`rotate(-33 ${scaleX(0.5)} ${scaleY(0.36)})`}
        >
          perfectly calibrated
        </text>

        {series.map((s, si) => (
          <g key={s.label}>
            <path
              d={s.bins.map((b, i) => `${i === 0 ? "M" : "L"}${scaleX(b.confidence)},${scaleY(b.accuracy)}`).join(" ")}
              fill="none"
              stroke={s.colour}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {s.bins.map((b, i) => (
              <circle
                key={b.bin}
                cx={scaleX(b.confidence)}
                cy={scaleY(b.accuracy)}
                r={hover?.s === si && hover?.i === i ? 6 : 4.5}
                fill={s.colour}
                stroke="var(--panel)"
                strokeWidth={2}
                onMouseEnter={() => setHover({ s: si, i })}
                onMouseLeave={() => setHover(null)}
                style={{ cursor: "pointer" }}
              />
            ))}
          </g>
        ))}

        <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={H - PAD.bottom} stroke={AXIS} strokeWidth={1} />
        <line x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom} stroke={AXIS} strokeWidth={1} />

        <text x={W / 2} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--text-dim)">
          predicted confidence (%)
        </text>
        <text x={12} y={H / 2} textAnchor="middle" fontSize="10" fill="var(--text-dim)" transform={`rotate(-90 12 ${H / 2})`}>
          observed accuracy (%)
        </text>
      </svg>

      <figcaption className="mt-3 flex flex-wrap items-center gap-4 text-sm">
        {series.map((s) => (
          <span key={s.label} className="flex items-center gap-1.5">
            <span className="w-3 h-3 shrink-0 ink-edge" style={{ background: s.colour }} />
            {s.label}
          </span>
        ))}
        <span className="text-[var(--text-dim)] text-xs ml-auto">
          bins under {MIN_COUNT} samples omitted as noise
        </span>
      </figcaption>

      {active && (
        <p className="mt-2 text-sm figures" aria-live="polite">
          {active.bin}: confidence {(active.confidence * 100).toFixed(1)}%, accuracy{" "}
          {(active.accuracy * 100).toFixed(1)}%, {active.count.toLocaleString()} images
        </p>
      )}
    </figure>
  );
}
