import { macroSplit, type Nutrients } from "@/lib/kb";

/** The macro profile drawn as a double strand — the "genome" reading of a dish. */
export function NutrientHelix({ nutrients }: { nutrients: Nutrients }) {
  const { protein, carbs, fat } = macroSplit(nutrients);

  const width = 260;
  const height = 120;
  const rungs = 22;
  const amplitude = 30;
  const midline = height / 2;

  // Each rung is assigned to a macro by walking the three shares in order, so the
  // coloured bands are proportional to calorie contribution.
  const bands = [
    { key: "carbs", share: carbs, color: "var(--color-amber)" },
    { key: "protein", share: protein, color: "var(--color-blue)" },
    { key: "fat", share: fat, color: "var(--color-red)" },
  ];

  const rungColor = (i: number) => {
    const t = i / rungs;
    let acc = 0;
    for (const b of bands) {
      acc += b.share;
      if (t <= acc) return b.color;
    }
    return bands[bands.length - 1].color;
  };

  const strand = (phase: number) =>
    Array.from({ length: 60 }, (_, i) => {
      const x = (i / 59) * width;
      const y = midline + Math.sin((i / 59) * Math.PI * 3 + phase) * amplitude;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full h-auto"
      role="presentation"
      aria-hidden="true"
    >
      {Array.from({ length: rungs }, (_, i) => {
        const x = (i / (rungs - 1)) * width;
        const phase = (i / (rungs - 1)) * Math.PI * 3;
        const y1 = midline + Math.sin(phase) * amplitude;
        const y2 = midline + Math.sin(phase + Math.PI) * amplitude;
        return (
          <line
            key={i}
            x1={x}
            y1={y1}
            x2={x}
            y2={y2}
            stroke={rungColor(i)}
            strokeWidth={3}
            strokeLinecap="round"
            opacity={0.9}
          />
        );
      })}
      <path d={strand(0)} fill="none" stroke="var(--line)" strokeWidth={3} />
      <path d={strand(Math.PI)} fill="none" stroke="var(--line)" strokeWidth={3} />
    </svg>
  );
}
