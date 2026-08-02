/** A web being spun, drawn the way a spider actually builds one.
 *
 *  Real orb weavers lay the radial spokes first, then walk a spiral outward
 *  across them. Animating in that order is what makes this read as construction
 *  rather than as a rotating graphic — and it gives the loader an honest sense of
 *  progress even though it knows nothing about how long the work will take.
 *
 *  Pure SVG and CSS: no canvas, no library, nothing to hydrate. A loading
 *  indicator that itself costs a JavaScript bundle is self-defeating, and this
 *  one renders on the server and animates without ever becoming interactive.
 */

const SPOKES = 12;
const RINGS = [0.28, 0.46, 0.64, 0.82, 1];

function polar(angleDeg: number, radius: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return [50 + Math.cos(rad) * radius * 46, 50 + Math.sin(rad) * radius * 46] as const;
}

/** One ring of the spiral: a polygon across all spokes, which is how the strand
 *  actually sits — straight segments between radials, not a true circle. */
function ringPath(radius: number) {
  const points = Array.from({ length: SPOKES }, (_, i) => polar((360 / SPOKES) * i, radius));
  return (
    points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ") +
    " Z"
  );
}

export function WebLoader({
  label = "Spinning the strand",
  sub,
  size = 132,
}: {
  label?: string;
  sub?: string;
  size?: number;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center gap-3">
      <svg
        width={size}
        height={size}
        viewBox="0 0 100 100"
        className="web-loader"
        role="img"
        aria-label={label}
      >
        <g className="web-loader-spin">
          {Array.from({ length: SPOKES }, (_, i) => {
            const [x, y] = polar((360 / SPOKES) * i, 1);
            return (
              <line
                key={i}
                x1="50"
                y1="50"
                x2={x}
                y2={y}
                className="web-spoke"
                style={{ animationDelay: `${i * 0.045}s` }}
              />
            );
          })}

          {RINGS.map((r, i) => (
            <path
              key={r}
              d={ringPath(r)}
              className="web-ring"
              style={{ animationDelay: `${0.5 + i * 0.13}s` }}
            />
          ))}

          <circle cx="50" cy="50" r="3.4" className="web-hub" />
        </g>
      </svg>

      <div>
        <p className="font-display text-lg leading-tight">{label}</p>
        {sub && <p className="text-sm text-[var(--text-dim)] mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

/** Full-panel variant for route-level loading states. */
export function WebLoaderPanel({
  label,
  sub,
  className = "",
}: {
  label?: string;
  sub?: string;
  className?: string;
}) {
  return (
    <div className={`panel halftone-shade p-10 grid place-items-center ${className}`}>
      <WebLoader label={label} sub={sub} />
    </div>
  );
}
