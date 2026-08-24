"use client";

import { useEffect, useRef } from "react";

/** SpiderWebBackground — a real spider web drawn to canvas and plucked by the pointer. */

type Props = {
  className?: string;
  /** Web origin as a fraction of the box, [x, y]. */
  origin?: [number, number];
  /** Sector the web spans, in TURNS. */
  arc?: number;
  /** Rotation of the sector, in turns. */
  rotate?: number;
  spokes?: number;
  rings?: number;
  /** Web radius as a multiple of the box diagonal. */
  reach?: number;
  /** Strand colour. */
  color?: string;
  /** Colour of strands near the pointer. */
  highlight?: string;
  /** Junction-bead colour. */
  nodeColor?: string;
  opacity?: number;
};

type Vertex = { x: number; y: number; bx: number; by: number; vx: number; vy: number };

export function SpiderWebBackground({
  className = "",
  origin = [1, 0],
  arc = 0.42,
  rotate = 0.29,
  spokes = 18,
  rings = 10,
  reach = 1.05,
  color = "var(--line)",
  highlight = "var(--color-red)",
  nodeColor = "var(--text-dim)",
  opacity = 0.34,
}: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  const [originX, originY] = origin;

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let w = 0;
    let h = 0;
    let verts: Vertex[][] = [];
    let pointer = { x: -9999, y: -9999, active: false };
    let visible = true;

    /** Canvas cannot read `var(--x)`, so resolve tokens against the document. */
    const readToken = (value: string, fallback: string) => {
      const token = value.match(/^var\(\s*(--[\w-]+)\s*\)$/);
      if (!token) return value;
      const resolved = getComputedStyle(document.documentElement)
        .getPropertyValue(token[1])
        .trim();
      return resolved || fallback;
    };

    let ink = readToken(color, "#0b0b0f");
    let accent = readToken(highlight, "#e62429");
    let bead = readToken(nodeColor, "#4b4b55");

    const rereadTokens = () => {
      ink = readToken(color, "#0b0b0f");
      accent = readToken(highlight, "#e62429");
      bead = readToken(nodeColor, "#4b4b55");
      if (reduced) step(0);
    };

    /** Rest lattice. */
    const build = () => {
      const cx = originX * w;
      const cy = originY * h;
      const maxR = Math.hypot(w, h) * reach;
      verts = [];
      for (let j = 1; j <= rings; j++) {
        const r = maxR * Math.pow(j / rings, 1.45);
        const row: Vertex[] = [];
        for (let k = 0; k <= spokes; k++) {
          const t = spokes === 0 ? 0 : k / spokes;
          const ang = (rotate + t * arc) * Math.PI * 2;
          const x = cx + Math.cos(ang) * r;
          const y = cy + Math.sin(ang) * r;
          row.push({ x, y, bx: x, by: y, vx: 0, vy: 0 });
        }
        verts.push(row);
      }
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = rect.width;
      h = rect.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      build();
      if (reduced) step(0);
    };

    const step = (t: number) => {
      if (!verts.length) return;
      const cx = originX * w;
      const cy = originY * h;
      const pluckR = Math.min(w, h) * 0.34;

      for (let j = 0; j < verts.length; j++) {
        for (let k = 0; k < verts[j].length; k++) {
          const v = verts[j][k];

          // Ambient drift so the web is never dead still.
          const sway = reduced ? 0 : Math.sin(t * 0.0011 + j * 0.55 + k * 0.42) * 1.6;

          // Pointer pluck: push away, falling off smoothly to nothing.
          let px = 0;
          let py = 0;
          if (pointer.active) {
            const dx = v.x - pointer.x;
            const dy = v.y - pointer.y;
            const d = Math.hypot(dx, dy);
            if (d < pluckR && d > 0.001) {
              const f = (1 - d / pluckR) ** 2 * 26;
              px = (dx / d) * f;
              py = (dy / d) * f;
            }
          }

          // Spring toward rest + damping.
          const tx = v.bx + px + sway;
          const ty = v.by + py + sway * 0.6;
          v.vx = (v.vx + (tx - v.x) * 0.09) * 0.86;
          v.vy = (v.vy + (ty - v.y) * 0.09) * 0.86;
          v.x += v.vx;
          v.y += v.vy;
        }
      }

      ctx.clearRect(0, 0, w, h);
      ctx.globalAlpha = opacity;
      ctx.lineCap = "round";

      // Radial spokes — origin outward through each ring vertex.
      ctx.lineWidth = 1.1;
      ctx.strokeStyle = ink;
      for (let k = 0; k < verts[0].length; k++) {
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        for (let j = 0; j < verts.length; j++) ctx.lineTo(verts[j][k].x, verts[j][k].y);
        ctx.stroke();
      }

      // Ring strands — quadratic curves sagging toward the origin.
      for (let j = 0; j < verts.length; j++) {
        const row = verts[j];
        ctx.beginPath();
        for (let k = 0; k < row.length - 1; k++) {
          const a = row[k];
          const b = row[k + 1];
          const mx = (a.x + b.x) / 2;
          const my = (a.y + b.y) / 2;
          const sag = 0.14; // ← the detail that makes it silk, not a grid
          const qx = mx + (cx - mx) * sag;
          const qy = my + (cy - my) * sag;
          if (k === 0) ctx.moveTo(a.x, a.y);
          ctx.quadraticCurveTo(qx, qy, b.x, b.y);
        }
        ctx.lineWidth = j >= verts.length - 2 ? 1.5 : 1;
        ctx.strokeStyle = pointer.active && j % 3 === 0 ? accent : ink;
        ctx.globalAlpha = opacity * (j >= verts.length - 3 ? 0.85 : 0.6);
        ctx.stroke();
      }

      // Junction beads on every third crossing.
      ctx.globalAlpha = opacity * 0.8;
      ctx.fillStyle = bead;
      for (let j = 1; j < verts.length; j += 3) {
        for (let k = 0; k < verts[j].length; k += 2) {
          const v = verts[j][k];
          ctx.beginPath();
          ctx.arc(v.x, v.y, 1.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    };

    const loop = (t: number) => {
      if (visible) step(t);
      raf = requestAnimationFrame(loop);
    };

    const onPointer = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      pointer = { x: e.clientX - rect.left, y: e.clientY - rect.top, active: true };
    };
    const onLeave = () => {
      pointer.active = false;
    };

    resize();

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
    });
    io.observe(canvas);

    // The toggle stamps data-theme on <html>; the OS preference is the fallback.
    const themeWatcher = new MutationObserver(rereadTokens);
    themeWatcher.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme", "class"],
    });
    const scheme = window.matchMedia("(prefers-color-scheme: dark)");
    scheme.addEventListener("change", rereadTokens);

    if (reduced) {
      step(0);
    } else {
      window.addEventListener("pointermove", onPointer, { passive: true });
      window.addEventListener("pointerleave", onLeave);
      raf = requestAnimationFrame(loop);
    }

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      themeWatcher.disconnect();
      scheme.removeEventListener("change", rereadTokens);
      window.removeEventListener("pointermove", onPointer);
      window.removeEventListener("pointerleave", onLeave);
    };
  }, [originX, originY, arc, rotate, spokes, rings, reach, color, highlight, nodeColor, opacity]);

  return <canvas ref={ref} aria-hidden="true" className={`pointer-events-none ${className}`} />;
}
