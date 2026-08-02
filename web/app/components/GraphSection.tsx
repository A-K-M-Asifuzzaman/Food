"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import type { GraphData } from "./three/GraphWeb";
import { WebLoader } from "./WebLoader";

// The 3D bundle is large and the design system forbids it blocking anything on
// the upload -> result path, so it is code-split and only requested once the
// section is actually near the viewport.
const GraphWeb = dynamic(() => import("./three/GraphWeb"), {
  ssr: false,
  loading: () => (
    <div className="w-full aspect-[4/3] sm:aspect-[16/10] ink-edge halftone-shade grid place-items-center">
      <WebLoader label="Spinning the web" sub="181 nodes · 323 strands" />
    </div>
  ),
});

export function GraphSection({ data }: { data: GraphData }) {
  const ref = useRef<HTMLDivElement>(null);
  const [near, setNear] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || near) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setNear(true);
          observer.disconnect();
        }
      },
      { rootMargin: "300px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [near]);

  return (
    <div ref={ref}>
      {near ? (
        <GraphWeb data={data} />
      ) : (
        <div className="w-full aspect-[4/3] sm:aspect-[16/10] ink-edge halftone" />
      )}
    </div>
  );
}
