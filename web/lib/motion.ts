"use client";

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

/** Motion primitives for the comic-panel language.
 *
 *  Comic motion is staged and snappy, not floaty: short durations, ease-out,
 *  overshoot on entry. The tokens here mirror the CSS custom properties in
 *  globals.css so a panel animated by GSAP and one animated by a CSS transition
 *  read as the same system.
 *
 *  Everything checks `prefers-reduced-motion` at call time rather than at import
 *  time, because the user can change it while the page is open and a stale
 *  answer would leave someone with vestibular sensitivity watching parallax.
 */

export const DUR = { instant: 0.09, snap: 0.18, panel: 0.32, stage: 0.5 } as const;
export const EASE = {
  snap: "power3.out",
  overshoot: "back.out(1.7)",
} as const;

let registered = false;

export function ensureGsap() {
  if (!registered && typeof window !== "undefined") {
    gsap.registerPlugin(ScrollTrigger);
    registered = true;
  }
  return gsap;
}

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return true;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Panels arrive as a staggered volley rather than all at once — the reading
 *  order of a comic page, not a fade-in of the whole spread. */
export function revealPanels(
  targets: gsap.TweenTarget,
  options: { trigger?: Element; stagger?: number } = {},
) {
  const g = ensureGsap();
  if (prefersReducedMotion()) {
    g.set(targets, { opacity: 1, y: 0, scale: 1, clearProps: "transform" });
    return;
  }
  return g.fromTo(
    targets,
    { opacity: 0, y: 26, scale: 0.97 },
    {
      opacity: 1,
      y: 0,
      scale: 1,
      duration: DUR.stage,
      ease: EASE.overshoot,
      stagger: options.stagger ?? 0.07,
      scrollTrigger: options.trigger
        ? { trigger: options.trigger, start: "top 82%", once: true }
        : undefined,
    },
  );
}

/** The signature transition: a strand fires across the panel, and the content
 *  snaps in behind it. The line is drawn with SVG dash offset so it reads as a
 *  web-line being shot rather than a bar wiping. */
export function webShot(line: SVGPathElement, content: Element) {
  const g = ensureGsap();
  if (prefersReducedMotion()) {
    g.set(content, { opacity: 1 });
    g.set(line, { opacity: 0 });
    return;
  }
  const length = line.getTotalLength();
  g.set(line, { strokeDasharray: length, strokeDashoffset: length, opacity: 1 });
  return g
    .timeline()
    .to(line, { strokeDashoffset: 0, duration: DUR.snap, ease: "none" })
    .fromTo(
      content,
      { opacity: 0, x: -14 },
      { opacity: 1, x: 0, duration: DUR.panel, ease: EASE.overshoot },
      "-=0.05",
    )
    .to(line, { opacity: 0, duration: DUR.instant }, "-=0.1");
}

/** SFX land on real events only, so they read as system feedback rather than
 *  decoration. Impact scale with a slight rotation, then hold. */
export function impact(target: gsap.TweenTarget) {
  const g = ensureGsap();
  if (prefersReducedMotion()) {
    g.set(target, { opacity: 1, scale: 1, rotate: -2 });
    return;
  }
  return g.fromTo(
    target,
    { opacity: 0, scale: 0.6, rotate: -12 },
    { opacity: 1, scale: 1, rotate: -2, duration: 0.42, ease: EASE.overshoot },
  );
}

/** Counts up to a value. Nutrition figures are the product, so they animate to
 *  their number rather than appearing — but they land fast, because a reader
 *  waiting to find out how many calories something has is being annoyed. */
export function countTo(
  el: HTMLElement,
  value: number,
  { decimals = 0, duration = 0.7 } = {},
) {
  const g = ensureGsap();
  if (prefersReducedMotion()) {
    el.textContent = value.toFixed(decimals);
    return;
  }
  const state = { v: 0 };
  return g.to(state, {
    v: value,
    duration,
    ease: EASE.snap,
    onUpdate: () => {
      el.textContent = state.v.toFixed(decimals);
    },
  });
}

export { ScrollTrigger };
