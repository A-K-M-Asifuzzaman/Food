"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ensureGsap, prefersReducedMotion } from "@/lib/motion";

/** The between-pages moment. */

// Long enough that a prerendered route never flashes it, short enough that a slow one
// does not feel unacknowledged.
const THRESHOLD = 220;
// The overlay holds briefly after arrival so it reads as a transition rather than a
// flicker, but never long enough to be the reason you waited.
const MIN_VISIBLE = 480;

export function RouteTransition() {
  const pathname = usePathname();
  const [active, setActive] = useState(false);
  const shownAt = useRef(0);
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null);
  const overlay = useRef<HTMLDivElement>(null);
  const strand = useRef<SVGPathElement>(null);
  const spider = useRef<SVGGElement>(null);
  const web = useRef<SVGGElement>(null);
  const first = useRef(true);

  // Arm on any click that will navigate somewhere else.
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = (event.target as HTMLElement)?.closest?.("a");
      if (!link) return;

      const href = link.getAttribute("href");
      if (!href || href.startsWith("#") || link.target === "_blank") return;
      // External links leave the app; the browser shows its own progress.
      if (/^[a-z]+:/i.test(href) && !href.startsWith(window.location.origin)) return;

      const to = new URL(href, window.location.href);
      if (to.origin !== window.location.origin) return;
      if (to.pathname === window.location.pathname) return;

      pending.current = setTimeout(() => {
        shownAt.current = Date.now();
        setActive(true);
      }, THRESHOLD);
    };

    document.addEventListener("click", onClick, true);
    return () => {
      document.removeEventListener("click", onClick, true);
      if (pending.current) clearTimeout(pending.current);
    };
  }, []);

  // Arrival.
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (pending.current) {
      clearTimeout(pending.current);
      pending.current = null;
    }
    if (!active) return;

    const elapsed = Date.now() - shownAt.current;
    const t = setTimeout(() => setActive(false), Math.max(0, MIN_VISIBLE - elapsed));
    return () => clearTimeout(t);
    // `active` is deliberately not a dependency: this must run on navigation, not when
    // the overlay's own state settles.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // The animation itself.
  useEffect(() => {
    if (!active || !strand.current || !spider.current) return;
    if (prefersReducedMotion()) return;

    const g = ensureGsap();
    const line = strand.current;
    const length = line.getTotalLength();

    const timeline = g.timeline();
    timeline
      .fromTo(
        overlay.current,
        { opacity: 0 },
        { opacity: 1, duration: 0.14, ease: "power2.out" },
      )
      .fromTo(
        line,
        { strokeDasharray: length, strokeDashoffset: length },
        { strokeDashoffset: 0, duration: 0.34, ease: "power2.in" },
        0,
      )
      // The spider rides the strand it just spun, so the drop cannot drift out of step
      // with the line under it.
      .fromTo(
        spider.current,
        { y: -120, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.38, ease: "power2.in" },
        0.02,
      )
      .to(spider.current, { y: 8, duration: 0.5, ease: "sine.inOut", yoyo: true, repeat: -1 })
      .fromTo(
        web.current,
        { opacity: 0, scale: 0.72 },
        { opacity: 1, scale: 1, duration: 0.45, ease: "back.out(1.6)" },
        0.1,
      );

    return () => {
      timeline.kill();
    };
  }, [active]);

  if (!active) return null;

  return (
    <div
      ref={overlay}
      className="fixed inset-0 z-[100] grid place-items-center pointer-events-none"
      style={{ background: "color-mix(in srgb, var(--page) 88%, transparent)" }}
      role="status"
      aria-live="polite"
    >
      <span className="sr-only">Loading the next page</span>

      <svg viewBox="0 0 260 260" className="w-56 h-56 max-w-[60vw] max-h-[60vw]" fill="none">
        {/* The web, spun behind. */}
        <g ref={web} style={{ transformOrigin: "130px 150px" }}>
          {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
            <line
              key={deg}
              x1="130"
              y1="150"
              x2={130 + Math.cos((deg * Math.PI) / 180) * 110}
              y2={150 + Math.sin((deg * Math.PI) / 180) * 110}
              stroke="var(--line)"
              strokeWidth="1.4"
              opacity="0.3"
            />
          ))}
          {[34, 58, 82, 106].map((r) => (
            <circle
              key={r}
              cx="130"
              cy="150"
              r={r}
              stroke="var(--line)"
              strokeWidth="1.6"
              opacity="0.26"
              // A hand-spun web is not a perfect circle.
              style={{ transform: `rotate(${r}deg)`, transformOrigin: "130px 150px" }}
              strokeDasharray="42 7"
            />
          ))}
        </g>

        {/* The strand the spider comes down on. */}
        <path
          ref={strand}
          d="M130 0 L130 132"
          stroke="var(--line)"
          strokeWidth="2.4"
          strokeLinecap="round"
        />

        <g ref={spider} style={{ transformOrigin: "130px 150px" }}>
          {/* Legs. */}
          <g stroke="var(--line)" strokeWidth="3.4" strokeLinecap="round" fill="none">
            <path d="M118 142 96 124M118 150 92 148M118 158 96 172M142 142 164 124M142 150 168 148M142 158 164 172" />
          </g>
          <ellipse
            cx="130"
            cy="154"
            rx="17"
            ry="20"
            fill="var(--color-red)"
            stroke="var(--line)"
            strokeWidth="3"
          />
          <circle cx="130" cy="134" r="11" fill="var(--color-red)" stroke="var(--line)" strokeWidth="3" />
          {/* The lenses read the character even at this size. */}
          <path
            d="M124 134 Q120 128 126 127 Q131 128 130 134 Q128 138 124 134 Z"
            fill="#F8F8F8"
            stroke="var(--line)"
            strokeWidth="1.6"
          />
          <path
            d="M136 134 Q140 128 134 127 Q129 128 130 134 Q132 138 136 134 Z"
            fill="#F8F8F8"
            stroke="var(--line)"
            strokeWidth="1.6"
          />
        </g>
      </svg>
    </div>
  );
}
