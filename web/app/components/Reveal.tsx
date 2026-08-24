"use client";

import { useLayoutEffect, useRef } from "react";

import { ensureGsap, prefersReducedMotion } from "@/lib/motion";

/** Staggers the panels inside it as they scroll into view. */
export function Reveal({
  children,
  selector = ".panel, .panel-flat, .panel-tight",
  stagger = 0.07,
  className,
}: {
  children: React.ReactNode;
  selector?: string;
  stagger?: number;
  className?: string;
}) {
  const root = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!root.current || prefersReducedMotion()) return;
    const g = ensureGsap();

    const ctx = g.context(() => {
      const below = Array.from(
        root.current!.querySelectorAll<HTMLElement>(selector),
      ).filter((el) => el.getBoundingClientRect().top > window.innerHeight * 0.9);

      // A 101-card grid would otherwise stagger for seven seconds, leaving cards
      // invisible long after somebody scrolled to them.
      const panels = below.slice(0, 12);
      if (panels.length === 0) return;

      g.fromTo(
        panels,
        { opacity: 0, y: 24, scale: 0.985 },
        {
          opacity: 1,
          y: 0,
          scale: 1,
          duration: 0.5,
          ease: "back.out(1.6)",
          // `amount` fixes the total spread rather than the gap per element, so the
          // volley lasts the same half-second whether it is three panels or twelve.
          stagger: { amount: Math.min(stagger * panels.length, 0.55) },
          scrollTrigger: { trigger: root.current, start: "top 88%", once: true },
        },
      );
    }, root);

    return () => ctx.revert();
  }, [selector, stagger]);

  return (
    <div ref={root} className={className}>
      {children}
    </div>
  );
}
