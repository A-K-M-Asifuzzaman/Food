/** The inline loading indicator: a spider walking a strand.
 *
 *  The full-page `WebLoader` spins an entire orb web, which is right when a
 *  route is loading and wrong inside a panel that is waiting on one fetch — a
 *  132px web in a 40px gap is a decoration, not a status. This is the small
 *  form: one strand, one spider, and the label saying what is being waited on.
 *
 *  Pure SVG and CSS, rendered on the server and animated without hydrating.
 *  A loading indicator that costs a JavaScript bundle is self-defeating.
 */
export function SpiderBar({
  label = "Loading",
  className = "",
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div className={`flex items-center gap-3 ${className}`} role="status" aria-live="polite">
      <svg viewBox="0 0 72 22" className="w-[4.5rem] h-[1.4rem] shrink-0" fill="none" aria-hidden="true">
        {/* The strand, anchored at both ends. */}
        <path d="M3 12 Q36 17 69 12" stroke="var(--line)" strokeWidth="1.4" opacity="0.4" />
        <circle cx="3" cy="12" r="2" fill="var(--line)" opacity="0.55" />
        <circle cx="69" cy="12" r="2" fill="var(--line)" opacity="0.55" />

        <g className="spider-walk">
          <g stroke="var(--line)" strokeWidth="1.3" strokeLinecap="round" fill="none">
            <path d="M-3 -1.5 -6 -4M3 -1.5 6 -4M-3.4 0.5 -7 0M3.4 0.5 7 0M-3 2.5 -6 4.5M3 2.5 6 4.5" />
          </g>
          <ellipse cx="0" cy="1" rx="3" ry="3.6" fill="var(--color-red)" stroke="var(--line)" strokeWidth="1.2" />
          <circle cx="0" cy="-2.6" r="1.8" fill="var(--line)" />
        </g>
      </svg>
      <span className="text-sm text-[var(--text-dim)]">{label}…</span>
    </div>
  );
}
