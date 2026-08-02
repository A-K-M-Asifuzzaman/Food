/** The chart palette, distinct from the interface palette — and validated.
 *
 *  The UI accents cannot be reused as data marks. Run against the validator, the
 *  interface cyan (#22d3ee, L 0.797) and amber (#f5a524, L 0.782) both fall
 *  outside the lightness band and land under 3:1 against the surface: fine for a
 *  badge with a label beside it, unreadable as a bar someone has to compare.
 *
 *  These are the snapped steps, and the order is load-bearing. Green next to
 *  amber fails CVD separation at ΔE 5.6 under deuteranopia — the classic
 *  red-green confusion — so teal sits between them. Reordering this array
 *  reintroduces that failure.
 *
 *      node scripts/validate_palette.js \
 *        "#e62429,#1b4ce0,#c07708,#0e8fa3,#16a34a" --mode light
 *      → ALL CHECKS PASS
 *
 *  Dark mode carries one contrast warning (blue at 2.76:1), which the guidance
 *  says is relieved rather than dismissed — every chart here ships direct labels
 *  and a table view, so identity never rests on the swatch alone.
 */
export const CATEGORICAL = [
  "#e62429", // red — the brand accent, always series 1
  "#1b4ce0", // blue
  "#c07708", // amber, darkened from the UI token
  "#0e8fa3", // teal, darkened; sits between amber and green on purpose
  "#16a34a", // green
] as const;

/** Magnitude, one hue, light to dark. Never a rainbow. */
export const SEQUENTIAL = [
  "#e9eefb",
  "#c3d2f4",
  "#8fa9e8",
  "#5b7fdb",
  "#2f57c4",
  "#1b4ce0",
] as const;

/** Polarity around a meaningful zero, with a neutral — not a hue — at the middle.
 *  Used for calibration gaps, where the sign is the whole point: a model can be
 *  over-confident or under-confident and those are different failures. */
export const DIVERGING = {
  negative: "#1b4ce0", // under-confident
  neutral: "#9a9aa8",
  positive: "#e62429", // over-confident
} as const;

/** Reserved for state. Never reused as "series 4", and always shipped with a
 *  label or icon so colour is not the only carrier. */
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
