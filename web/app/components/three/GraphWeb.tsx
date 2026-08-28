"use client";

import { Line, OrbitControls, Html } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";

/** The GraphRAG knowledge graph rendered as a literal web. */

export type GraphNode = {
  id: string;
  label: string;
  type: "dish" | "ingredient";
  degree: number;
  group?: string;
  kcal?: number | null;
  pos: [number, number, number];
};

export type GraphLink = { source: string; target: string; weight: number };

export type GraphData = {
  nodes: GraphNode[];
  links: GraphLink[];
  stats: { dishes: number; ingredients: number; shared: number };
};

const DISH = "#e62429";
const INGREDIENT = "#22d3ee";
const DIM = "#4b4b55";

function Strands({
  links,
  index,
  active,
}: {
  links: GraphLink[];
  index: Map<string, GraphNode>;
  active: string | null;
}) {
  return (
    <>
      {links.map((link, i) => {
        const a = index.get(link.source);
        const b = index.get(link.target);
        if (!a || !b) return null;
        const lit =
          active !== null && (link.source === active || link.target === active);
        const faded = active !== null && !lit;
        return (
          <Line
            key={i}
            points={[a.pos, b.pos]}
            color={lit ? DISH : DIM}
            lineWidth={lit ? 2.2 : 0.6}
            transparent
            opacity={faded ? 0.06 : lit ? 0.95 : 0.28}
          />
        );
      })}
    </>
  );
}

function Node({
  node,
  active,
  pinned,
  dimmed,
  onHover,
  onSelect,
}: {
  node: GraphNode;
  active: boolean;
  pinned: boolean;
  dimmed: boolean;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
}) {
  const ref = useRef<THREE.Mesh>(null);
  // Radius encodes degree, so hub ingredients read as hubs.
  const radius = 0.12 + Math.sqrt(node.degree) * 0.07;
  const colour = node.type === "dish" ? DISH : INGREDIENT;

  useFrame((_, delta) => {
    if (!ref.current) return;
    const target = pinned ? 1.9 : active ? 1.55 : 1;
    ref.current.scale.lerp(new THREE.Vector3(target, target, target), delta * 9);
  });

  return (
    <mesh
      ref={ref}
      position={node.pos}
      onPointerOver={(e) => {
        e.stopPropagation();
        onHover(node.id);
      }}
      onPointerOut={() => onHover(null)}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(node.id);
      }}
    >
      <sphereGeometry args={[radius, 20, 20]} />
      <meshStandardMaterial
        color={colour}
        emissive={colour}
        emissiveIntensity={active ? 1.1 : 0.28}
        transparent
        opacity={dimmed ? 0.12 : 1}
        roughness={0.35}
      />
      {active && (
        <Html distanceFactor={16} zIndexRange={[10, 0]}>
          <div className="panel-tight px-2 py-1 text-xs whitespace-nowrap pointer-events-none">
            <span className="font-display">{node.label}</span>
            <span className="text-[var(--text-dim)]">
              {" "}
              · {node.type === "dish" ? "dish" : `in ${node.degree} dishes`}
            </span>
          </div>
        </Html>
      )}
    </mesh>
  );
}

function Scene({
  data,
  selected,
  onSelect,
}: {
  data: GraphData;
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  // A click pins the focus; a hover only previews it.
  const active = hovered ?? selected;

  const index = useMemo(
    () => new Map(data.nodes.map((n) => [n.id, n])),
    [data.nodes],
  );

  const neighbours = useMemo(() => {
    if (!active) return new Set<string>();
    const set = new Set<string>([active]);
    for (const l of data.links) {
      if (l.source === active) set.add(l.target);
      if (l.target === active) set.add(l.source);
    }
    return set;
  }, [active, data.links]);

  const group = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    // Idle rotation stops while inspecting, so a hovered label stays readable.
    if (group.current && !active) group.current.rotation.y += delta * 0.045;
  });

  return (
    <>
      <ambientLight intensity={0.75} />
      <pointLight position={[14, 14, 14]} intensity={1.1} />
      <pointLight position={[-14, -8, -10]} intensity={0.5} color={INGREDIENT} />
      <group ref={group}>
        <Strands links={data.links} index={index} active={active} />
        {data.nodes.map((n) => (
          <Node
            key={n.id}
            node={n}
            active={active === n.id}
            pinned={selected === n.id}
            dimmed={active !== null && !neighbours.has(n.id)}
            onHover={setHovered}
            onSelect={onSelect}
          />
        ))}
      </group>
      <OrbitControls
        enablePan={false}
        enableDamping
        dampingFactor={0.08}
        minDistance={8}
        maxDistance={34}
      />
    </>
  );
}

export default function GraphWeb({
  data,
  selected = null,
  onSelect = () => {},
}: {
  data: GraphData;
  selected?: string | null;
  onSelect?: (id: string | null) => void;
}) {
  return (
    <div className="relative w-full h-full overflow-hidden">
      <Canvas
        camera={{ position: [0, 0, 26], fov: 46 }}
        dpr={[1, 1.8]}
        gl={{ antialias: true, powerPreference: "high-performance" }}
        onPointerMissed={() => onSelect(null)}
      >
        <Scene data={data} selected={selected} onSelect={onSelect} />
      </Canvas>

    </div>
  );
}
