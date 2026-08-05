"use client";

import { Component, ReactNode, Suspense, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Canvas } from "@react-three/fiber";

const SlingerModel = dynamic(
  () => import("./three/SlingerModel").then((m) => m.SlingerModel),
  { ssr: false },
);

/** Drop a rigged humanoid glTF here to change the character.
 *
 *  A list rather than a constant so swapping is a file copy, not a code change.
 *  Nothing here is required — with no model present the flat figure renders
 *  instead, so the site never depends on the asset being in place. */
export const MODEL_CANDIDATES = ["/models/slinger.glb"];

/** A malformed or half-uploaded model must not take the page with it.
 *  Three throws during parse, which React will happily propagate to the root. */
class Guard extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    console.warn("[Spider3D] model failed to load, falling back to the flat figure", error);
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/**
 * The 3D character, if there is one.
 *
 * The model is not in the repository — it is somebody's artwork, and which one
 * to ship is a licensing decision rather than a code one. So this probes for
 * the file and renders nothing when it is absent, which is why the flat figure
 * is still wired up on every page: the site has to be complete without it.
 *
 * Three things keep a decorative WebGL canvas from taxing the page: it does not
 * mount for a reader who asked for reduced motion or on a screen too narrow to
 * spare the room, it does not render while scrolled out of view, and it never
 * downloads the model until both of those pass.
 */
export function Spider3D({
  className = "",
  scale = 1,
  shootEvery = 6.4,
  pose,
  side = "right",
  hideBelowVerts = 400,
  fallback = null,
}: {
  className?: string;
  scale?: number;
  shootEvery?: number;
  /** Resting attitude. Defaults to facing into the page from `side`. */
  pose?: [number, number, number];
  /** Which edge the figure sits on. Mirrors the pose and the throw with it. */
  side?: "left" | "right";
  /** Drop meshes below this vertex count — rig widgets and prop geometry. */
  hideBelowVerts?: number;
  /** Shown when there is no model, no WebGL, or the reader asked for stillness.
   *  The flat figure is the fallback, so the page is never missing its
   *  character just because an asset decision has not been made. */
  fallback?: ReactNode;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [decided, setDecided] = useState(false);
  // Starts true: frameloop="never" renders zero frames, so a canvas that
  // mounts before the observer reports in would simply stay empty.
  const [active, setActive] = useState(true);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const wide = window.matchMedia("(min-width: 1024px)").matches;
    if (reduced || !wide) {
      setDecided(true);
      return;
    }

    let alive = true;
    // HEAD rather than GET: this only needs to know which files exist, and a
    // character model runs to megabytes.
    (async () => {
      for (const candidate of MODEL_CANDIDATES) {
        try {
          const res = await fetch(candidate, { method: "HEAD" });
          if (res.ok) {
            if (alive) setUrl(candidate);
            break;
          }
        } catch {
          // Next candidate.
        }
      }
      if (alive) setDecided(true);
    })();

    const el = host.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setActive(e.isIntersecting), {
      rootMargin: "150px",
    });
    io.observe(el);
    return () => {
      alive = false;
      io.disconnect();
    };
  }, []);

  return (
    <div ref={host} aria-hidden="true" className={`pointer-events-none ${className}`}>
      {decided && !url && fallback}
      {url && (
        <Guard>
          <Canvas
            frameloop={active ? "always" : "never"}
            dpr={[1, 2]}
            gl={{ alpha: true, antialias: true }}
            camera={{ position: [0.3, 0.4, 6], fov: 34 }}
            style={{ background: "transparent" }}
          >
            {/* Key from the upper front so the ramp breaks across the chest,
                cool fill so the shadow side is not a flat black hole. */}
            <ambientLight intensity={0.9} />
            <directionalLight position={[3, 4, 5]} intensity={2} />
            <directionalLight position={[-4, 1, -2]} intensity={0.5} color="#8fa8ff" />
            <Suspense fallback={null}>
              <SlingerModel
                url={url}
                scale={scale}
                shootEvery={shootEvery}
                pose={pose ?? (side === "left" ? [0.34, 0.6, -0.22] : [0.34, -0.6, 0.22])}
                webTarget={side === "left" ? [2.1, 1.7, 0] : [-2.1, 1.7, 0]}
                hideBelowVerts={hideBelowVerts}
              />
            </Suspense>
          </Canvas>
        </Guard>
      )}
    </div>
  );
}
