"use client";

import { Component, ReactNode, Suspense, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

import { useHydrated, useMediaQuery } from "@/lib/client-state";

const SlingerModel = dynamic(
  () => import("./three/SlingerModel").then((m) => m.SlingerModel),
  { ssr: false },
);

/** Drop a rigged humanoid glTF here to change the character. */
export const MODEL_CANDIDATES = ["/models/slinger.glb"];

/** A malformed or half-uploaded model must not take the page with it. */
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

/** The 3D character, if there is one. */
export function Spider3D({
  className = "",
  scale = 1,
  pose,
  side = "right",
  hideBelowVerts = 400,
  model,
  interactive = true,
  fallback = null,
}: {
  className?: string;
  scale?: number;
  /** Resting attitude. */
  pose?: [number, number, number];
  /** Which edge the figure sits on. */
  side?: "left" | "right";
  /** Drop meshes below this vertex count — rig widgets and prop geometry. */
  hideBelowVerts?: number;
  /** Override the model path. */
  model?: string;
  /** Let a reader drag the figure around. */
  interactive?: boolean;
  /** Shown when there is no model, no WebGL, or the reader asked for stillness. */
  fallback?: ReactNode;
}) {
  const host = useRef<HTMLDivElement>(null);
  const hydrated = useHydrated();
  const wide = useMediaQuery("(min-width: 1024px)");
  const reduced = useMediaQuery("(prefers-reduced-motion: reduce)");
  const [found, setFound] = useState<string | null>(null);
  const [probed, setProbed] = useState(false);
  // Starts true: frameloop="never" renders zero frames, so a canvas that mounts before
  // the observer reports in would simply stay empty.
  const [active, setActive] = useState(true);

  // A few megabytes of character is not what someone on a metered connection asked for.
  // Read after hydration only — the server has no navigator to ask.
  const thrifty =
    hydrated &&
    Boolean(
      (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData,
    );
  const still = reduced || thrifty;

  // No probe means no model, so the fallback is settled the moment we decide not to look.
  const decided = still || probed;
  const url = still ? null : found;

  useEffect(() => {
    if (!hydrated || still) return;
    let alive = true;
    // HEAD rather than GET: this only needs to know which files exist, and a character
    // model runs to megabytes.
    void (async () => {
      let hit: string | null = null;
      for (const candidate of model ? [model] : MODEL_CANDIDATES) {
        try {
          const res = await fetch(candidate, { method: "HEAD" });
          if (res.ok) {
            hit = candidate;
            break;
          }
        } catch {
          // Next candidate.
        }
      }
      if (!alive) return;
      setFound(hit);
      setProbed(true);
    })();
    return () => {
      alive = false;
    };
  }, [hydrated, still, model]);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setActive(e.isIntersecting), {
      rootMargin: "150px",
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // Dragging is a pointer gesture on desktop and a scroll gesture on a phone.
  const draggable = interactive && wide;

  return (
    <div ref={host} aria-hidden="true" className={`${draggable ? "" : "pointer-events-none"} ${className}`}>
      {decided && !url && fallback}
      {url && (
        <Guard>
          <Canvas
            frameloop={active ? "always" : "never"}
            dpr={wide ? [1, 2] : [1, 1.5]}
            gl={{ alpha: true, antialias: true }}
            camera={{ position: [0, 0.15, 7.4], fov: 34 }}
            style={{ background: "transparent" }}
          >
            {/* Key from the upper front so the ramp breaks across the chest,
                cool fill so the shadow side is not a flat black hole. */}
            <ambientLight intensity={0.9} />
            <directionalLight position={[3, 4, 5]} intensity={2} />
            <directionalLight position={[-4, 1, -2]} intensity={0.5} color="#8fa8ff" />
            {draggable && (
              // Rotation only.
              <OrbitControls
                enableZoom={false}
                enablePan={false}
                enableDamping
                dampingFactor={0.08}
                rotateSpeed={0.6}
                minPolarAngle={Math.PI * 0.15}
                maxPolarAngle={Math.PI * 0.85}
              />
            )}
            <Suspense fallback={null}>
              <SlingerModel
                url={url}
                // A phone canvas is narrow enough that the frustum is narrower than the
                // figure at the desktop scale, cropping him down one side.
                scale={wide ? scale : scale * 0.72}
                pose={pose ?? (side === "left" ? [0.34, 0.6, -0.22] : [0.34, -0.6, 0.22])}
                hideBelowVerts={hideBelowVerts}
              />
            </Suspense>
          </Canvas>
        </Guard>
      )}
    </div>
  );
}
