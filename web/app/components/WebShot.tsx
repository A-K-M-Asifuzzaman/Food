"use client";

import { useEffect, useRef, useState } from "react";

/** Spider-Man anchoring a web strand to a corner of something on the page.
 *
 *  Drawn as one SVG spanning the section so the strand can start at his wrist
 *  and end exactly on the target element's corner. The end point is measured
 *  from the DOM rather than hard-coded, because the target moves with the
 *  viewport and a guessed coordinate is only right at one width.
 *
 *  Each pose lives in a 150x150 box with its own viewBox, which keeps the
 *  drawing in round numbers, and publishes the one point the page needs back
 *  out of it: `wrist`. Both the figure and the strand read that same constant,
 *  so adjusting a pose cannot leave the web starting in mid-air.
 *
 *  Decoration, so it is inert: `pointer-events: none` throughout, `aria-hidden`,
 *  and nothing renders below `lg` — a diagonal strand across a phone screen
 *  would cross the content it is meant to frame.
 */

const BOX = 150;

export type Pose = "perch" | "hang" | "crawl";
export type Corner = "tl" | "tr" | "bl" | "br";

type Props = {
  /** id of the element the web sticks to. */
  targetId: string;
  /** Which corner of that element to hit. */
  corner?: Corner;
  pose?: Pose;
  /** Which side of the section he sits on. */
  side?: "left" | "right";
  /** Distance from that side, and from the top of the section. */
  inset?: number;
  top?: number;
  scale?: number;
  /** The sound effect. Empty string for none. */
  sfx?: string;
};

export function WebShot({
  targetId,
  corner = "tr",
  pose = "perch",
  side = "right",
  inset = 24,
  top = 4,
  scale = 1.45,
  sfx = "THWIP!",
}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null);
  const [width, setWidth] = useState(0);
  const [fired, setFired] = useState(false);

  useEffect(() => {
    const measure = () => {
      const box = host.current?.getBoundingClientRect();
      const target = document.getElementById(targetId)?.getBoundingClientRect();
      if (!box || !target) return;
      setWidth(box.width);
      // Just inside the corner, so the strand reads as stuck to the panel
      // rather than floating beside it.
      const pad = 5;
      setAnchor({
        x:
          (corner === "tr" || corner === "br"
            ? target.right - pad
            : target.left + pad) - box.left,
        y:
          (corner === "bl" || corner === "br"
            ? target.bottom - pad
            : target.top + pad) - box.top,
      });
    };

    measure();
    const observer = new ResizeObserver(measure);
    if (host.current) observer.observe(host.current);
    const target = document.getElementById(targetId);
    if (target) observer.observe(target);
    window.addEventListener("resize", measure);

    // Fire once the anchor is known, so the strand never animates to a stale point.
    const t = setTimeout(() => setFired(true), 400);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
      clearTimeout(t);
    };
  }, [targetId, corner]);

  if (!anchor || !width) {
    return <div ref={host} className="absolute inset-0 pointer-events-none" />;
  }

  const size = BOX * scale;
  const heroX = side === "right" ? width - size - inset : inset;
  const flip = side === "left";
  const wrist = POSES[pose].wrist;
  // Mirroring the figure mirrors the wrist with it.
  const hand = {
    x: heroX + (flip ? size - wrist.x * scale : wrist.x * scale),
    y: top + wrist.y * scale,
  };

  // A slack line, not a ruler. The sag is a fraction of the span, so it stays
  // proportional as the layout stretches.
  const span = Math.hypot(anchor.x - hand.x, anchor.y - hand.y);
  const sag = Math.min(span * 0.055, 24);
  const mid = { x: (hand.x + anchor.x) / 2, y: (hand.y + anchor.y) / 2 + sag };
  const line = (offset: number) =>
    `M ${hand.x} ${hand.y} Q ${mid.x} ${mid.y + offset} ${anchor.x} ${anchor.y}`;
  const cls = fired ? "webshot-line webshot-line-fired" : "webshot-line";

  return (
    <div
      ref={host}
      className="absolute inset-0 pointer-events-none hidden lg:block z-10"
      aria-hidden="true"
    >
      <svg className="w-full h-full overflow-visible" fill="none">
        {/* The strand, drawn from the wrist outward so the dash animation reads
            as web travelling rather than the corner reeling it in. */}
        <path
          className={cls}
          d={line(0)}
          stroke="var(--text)"
          strokeWidth="3"
          strokeLinecap="round"
          opacity="0.9"
        />
        {/* Two thin companions, the way a web line is inked in the comics. */}
        <path
          className={cls}
          d={line(-9)}
          stroke="var(--text)"
          strokeWidth="1.1"
          strokeLinecap="round"
          opacity="0.3"
        />
        <path
          className={cls}
          d={line(8)}
          stroke="var(--text)"
          strokeWidth="1.1"
          strokeLinecap="round"
          opacity="0.3"
        />

        {/* The splat where it hits the corner. */}
        <g
          className={
            fired ? "webshot-splat webshot-splat-fired" : "webshot-splat"
          }
          transform={`translate(${anchor.x} ${anchor.y})`}
        >
          {[10, 17, 24].map((r, i) => (
            <circle
              key={r}
              r={r}
              fill="none"
              stroke="var(--text)"
              strokeWidth="1.3"
              opacity={0.34 - i * 0.08}
            />
          ))}
          {[8, 46, 84, 122, 160, 198, 236, 274, 312].map((deg) => (
            <line
              key={deg}
              x1="0"
              y1="0"
              x2={Math.cos((deg * Math.PI) / 180) * 25}
              y2={Math.sin((deg * Math.PI) / 180) * 25}
              stroke="var(--text)"
              strokeWidth="1.5"
              strokeLinecap="round"
              opacity="0.4"
            />
          ))}
          <circle r="6" fill="var(--text)" opacity="0.92" />
        </g>

        {/* The sound effect fires once with the web and does not repeat. */}
        {sfx && (
          <text
            className={
              fired ? "webshot-thwip webshot-thwip-fired" : "webshot-thwip"
            }
            x={side === "right" ? hand.x - 18 : hand.x + 18}
            y={hand.y + 40}
            textAnchor={side === "right" ? "end" : "start"}
            fill="var(--color-red)"
            stroke="var(--line)"
            strokeWidth="1"
            style={{
              fontFamily: "var(--font-display), sans-serif",
              fontSize: 26,
              letterSpacing: "0.04em",
            }}
          >
            {sfx}
          </text>
        )}

        <svg
          className="webshot-hero"
          x={heroX}
          y={top}
          width={size}
          height={size}
          viewBox={`0 0 ${BOX} ${BOX}`}
          overflow="visible"
        >
          <g transform={flip ? `translate(${BOX} 0) scale(-1 1)` : undefined}>
            {POSES[pose].figure()}
          </g>
        </svg>
      </svg>
    </div>
  );
}

/* ── The figures ─────────────────────────────────────────────────────────
   Three poses, each drawn in the same 150x150 box. Limbs are an ink stroke
   with the suit colour laid over it, which is how the rest of the site draws
   its edges. Every pose keeps its silhouette inside x∈[8,142] so that a figure
   at the viewport edge never has a foot clipped off. */

/** A limb: an ink stroke with the suit colour laid over it. */
function Limb({ d, colour, w }: { d: string; colour: string; w: number }) {
  return (
    <>
      <path
        d={d}
        stroke="var(--line)"
        strokeWidth={w}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d={d}
        stroke={colour}
        strokeWidth={w - 4}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </>
  );
}

/** A boot, drawn as a wedge off the end of a leg. */
function Boot({ x, y, rotate = 0 }: { x: number; y: number; rotate?: number }) {
  return (
    <path
      d="M-3 -5 Q-16 -2 -15 6 Q-11 11 2 6 Z"
      transform={`translate(${x} ${y}) rotate(${rotate})`}
      fill="var(--color-red)"
      stroke="var(--line)"
      strokeWidth="2.5"
      strokeLinejoin="round"
    />
  );
}

/** The masked head. `tilt` in degrees, positive leans right. */
function Head({
  cx,
  cy,
  r = 17,
  tilt = 0,
}: {
  cx: number;
  cy: number;
  r?: number;
  tilt?: number;
}) {
  return (
    <g transform={`rotate(${tilt} ${cx} ${cy})`}>
      <ellipse
        cx={cx}
        cy={cy}
        rx={r + 1.5}
        ry={r}
        fill="var(--color-red)"
        stroke="var(--line)"
        strokeWidth="3"
      />
      {/* Mask webbing: radials from the crown plus two concentric arcs. */}
      <g stroke="var(--line)" strokeWidth="0.9" opacity="0.4" fill="none">
        <path
          d={`M${cx} ${cy - r} L${cx} ${cy + r} M${cx - r} ${cy} L${cx + r} ${cy}
              M${cx - r * 0.7} ${cy - r * 0.7} L${cx + r * 0.7} ${cy + r * 0.7}
              M${cx + r * 0.7} ${cy - r * 0.7} L${cx - r * 0.7} ${cy + r * 0.7}`}
        />
        <path
          d={`M${cx - r * 0.6} ${cy - r * 0.5} A ${r * 0.6} ${r * 0.6} 0 0 0 ${cx + r * 0.6} ${cy - r * 0.5}
              M${cx - r * 0.9} ${cy + r * 0.1} A ${r * 0.9} ${r * 0.9} 0 0 0 ${cx + r * 0.9} ${cy + r * 0.1}`}
        />
      </g>
      {/* The lenses: teardrops with the point toward the centre of the face.
          White in both themes — it is the read of the mask. */}
      <path
        d={`M${cx - 13} ${cy + 3} Q${cx - 17} ${cy - 7} ${cx - 8} ${cy - 8}
            Q${cx - 1} ${cy - 7} ${cx - 2} ${cy + 1} Q${cx - 5} ${cy + 7} ${cx - 13} ${cy + 3} Z`}
        fill="#F8F8F8"
        stroke="var(--line)"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
      <path
        d={`M${cx + 13} ${cy + 3} Q${cx + 17} ${cy - 7} ${cx + 8} ${cy - 8}
            Q${cx + 1} ${cy - 7} ${cx + 2} ${cy + 1} Q${cx + 5} ${cy + 7} ${cx + 13} ${cy + 3} Z`}
        fill="#F8F8F8"
        stroke="var(--line)"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
    </g>
  );
}

/** The torso: broad shoulders tapering to the waist, with chest webbing and
 *  the emblem. `d` differs per pose; the detail is placed off the same box. */
function Torso({
  d,
  webbing,
  spider,
}: {
  d: string;
  webbing: string;
  spider: { x: number; y: number; s?: number };
}) {
  const { x, y, s = 1 } = spider;
  return (
    <>
      <path
        d={d}
        fill="var(--color-red)"
        stroke="var(--line)"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <g stroke="var(--line)" strokeWidth="1" opacity="0.4" fill="none">
        <path d={webbing} />
      </g>
      {/* The emblem: body, then four legs a side, splayed. */}
      <g
        transform={`translate(${x} ${y}) scale(${s})`}
        stroke="var(--line)"
        strokeWidth="1.9"
        strokeLinecap="round"
        fill="none"
      >
        <path d="M0 -8 L0 8" />
        <path d="M-2 -5 L-9 -10 M2 -5 L9 -10 M-2 -1 L-10 -2 M2 -1 L10 -2 M-2 3 L-10 5 M2 3 L10 5 M-2 6 L-7 12 M2 6 L7 12" />
      </g>
    </>
  );
}

const POSES: Record<
  Pose,
  { wrist: { x: number; y: number }; figure: () => React.ReactNode }
> = {
  /** Crouched on the top edge of the section, shooting down and to one side. */
  perch: {
    wrist: { x: 18, y: 100 },
    figure: () => (
      <>
        {/* Far side first, so the near limbs overlap it. */}
        <Limb d="M90 86 L118 78 L128 96" colour="var(--color-blue)" w={13} />
        <Boot x={129} y={98} rotate={140} />
        <Limb d="M94 56 L116 62 L112 82" colour="var(--color-red)" w={12} />

        {/* Near leg, coiled under him and planted forward. */}
        <Limb d="M76 92 L62 116 L84 130" colour="var(--color-blue)" w={16} />
        <Boot x={87} y={131} rotate={200} />

        {/* Neck, so the head sits on the shoulders rather than beside them. */}
        <Limb d="M78 44 L79 54" colour="var(--color-red)" w={13} />

        <Torso
          d="M62 52 Q78 42 96 52 Q102 74 90 90 Q76 98 68 88 Q58 70 62 52 Z"
          webbing="M79 44 L80 95 M63 56 L97 80 M96 54 L64 80
                   M64 58 Q79 66 96 58 M62 70 Q79 79 98 70 M66 83 Q79 91 92 83"
          spider={{ x: 80, y: 68, s: 0.95 }}
        />

        {/* Shooting arm: shoulder, elbow, then the wrist the web leaves from. */}
        <Limb d="M64 56 L40 78 L18 100" colour="var(--color-red)" w={12} />
        {/* The fist, two fingers folded onto the shooter. */}
        <circle
          cx="18"
          cy="100"
          r="7"
          fill="var(--color-red)"
          stroke="var(--line)"
          strokeWidth="2.5"
        />

        <Head cx={79} cy={26} tilt={-14} />
      </>
    ),
  },

  /** Hanging upside down from a lifeline that leaves the top of the frame —
   *  the pose everyone pictures first, and the one that works over a heading. */
  hang: {
    wrist: { x: 30, y: 118 },
    figure: () => (
      <>
        {/* The lifeline, running up out of the box from the hooked ankle. */}
        <path
          d="M84 34 L86 -140"
          stroke="var(--line)"
          strokeWidth="2.6"
          strokeLinecap="round"
          opacity="0.85"
        />
        <path
          d="M84 34 L80 -140"
          stroke="var(--line)"
          strokeWidth="1"
          strokeLinecap="round"
          opacity="0.28"
        />

        {/* Legs up, one bent, the ankle hooked over the line. */}
        <Limb d="M78 76 L82 48 L92 32" colour="var(--color-blue)" w={15} />
        <Limb d="M92 78 L108 56 L100 36" colour="var(--color-blue)" w={14} />
        <Boot x={98} y={34} rotate={-100} />

        {/* Free arm hanging, knuckles down. */}
        <Limb d="M94 92 L108 112 L104 132" colour="var(--color-red)" w={12} />
        <circle
          cx="104"
          cy="134"
          r="6.5"
          fill="var(--color-red)"
          stroke="var(--line)"
          strokeWidth="2.5"
        />

        <Torso
          d="M72 74 Q88 68 96 78 Q102 96 96 108 Q80 116 70 106 Q66 88 72 74 Z"
          webbing="M84 70 L84 113 M70 80 L99 100 M99 80 L70 100
                   M69 84 Q84 92 100 84 M68 96 Q84 104 100 96"
          spider={{ x: 84, y: 92, s: 0.85 }}
        />

        {/* Shooting arm, reaching down and across. */}
        <Limb d="M72 90 L50 106 L30 118" colour="var(--color-red)" w={12} />
        <circle
          cx="30"
          cy="118"
          r="7"
          fill="var(--color-red)"
          stroke="var(--line)"
          strokeWidth="2.5"
        />

        {/* Head below the body — upside down, so the lenses point down too. */}
        <g transform="rotate(180 84 132)">
          <Head cx={84} cy={132} r={15} tilt={8} />
        </g>
      </>
    ),
  },

  /** Clinging side-on, the way he crawls a wall — flatter, so it fits beside a
   *  block of text without pushing into it. */
  crawl: {
    wrist: { x: 22, y: 92 },
    figure: () => (
      <>
        <Limb d="M96 74 L124 66 L134 86" colour="var(--color-blue)" w={14} />
        <Boot x={134} y={88} rotate={150} />
        <Limb d="M94 54 L118 50 L128 62" colour="var(--color-red)" w={12} />

        <Limb d="M84 82 L88 112 L64 122" colour="var(--color-blue)" w={15} />
        <Boot x={62} y={122} rotate={12} />

        <Torso
          d="M64 44 Q84 38 96 52 Q104 70 92 84 Q74 92 66 78 Q60 60 64 44 Z"
          webbing="M80 38 L82 89 M64 50 L98 74 M97 48 L66 74
                   M65 52 Q81 60 97 52 M63 65 Q81 74 99 65 M67 78 Q81 86 94 78"
          spider={{ x: 81, y: 62, s: 0.9 }}
        />

        <Limb d="M66 50 L42 70 L22 92" colour="var(--color-red)" w={12} />
        <circle
          cx="22"
          cy="92"
          r="7"
          fill="var(--color-red)"
          stroke="var(--line)"
          strokeWidth="2.5"
        />

        <Head cx={74} cy={22} r={16} tilt={-22} />
      </>
    ),
  },
};
