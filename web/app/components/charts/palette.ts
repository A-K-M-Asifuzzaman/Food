/** The chart palette, distinct from the interface palette — and validated. */
export const CATEGORICAL = [
  "#e62429", // red — the brand accent, always series 1
  "#1b4ce0", // blue
  "#c07708", // amber, darkened from the UI token
  "#0e8fa3", // teal, darkened; sits between amber and green on purpose
  "#16a34a", // green
] as const;

/** Magnitude, one hue, light to dark. */
export const SEQUENTIAL = [
  "#e9eefb",
  "#c3d2f4",
  "#8fa9e8",
  "#5b7fdb",
  "#2f57c4",
  "#1b4ce0",
] as const;

/** Polarity around a meaningful zero, with a neutral — not a hue — at the middle. */
export const DIVERGING = {
  negative: "#1b4ce0", // under-confident
  neutral: "#9a9aa8",
  positive: "#e62429", // over-confident
} as const;

/** Reserved for state. */
export const STATUS = {
  good: "#16a34a",
  warning: "#c07708",
  serious: "#e62429",
  critical: "#a4161a",
} as const;

/** Recessive furniture: one step off the surface, hairline, solid. */
export const GRID = "color-mix(in oklab, var(--line) 16%, transparent)";
export const AXIS = "color-mix(in oklab, var(--line) 34%, transparent)";
export const MUTED = "var(--text-dim)";
