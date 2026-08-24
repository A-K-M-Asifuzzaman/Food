"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import type { GraphData, GraphNode } from "./three/GraphWeb";
import { WebLoader } from "./WebLoader";

const GraphWeb = dynamic(() => import("./three/GraphWeb"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full grid place-items-center halftone-shade">
      <WebLoader label="Spinning the web" sub="181 nodes · 323 strands" />
    </div>
  ),
});

/** The explorer around the 3D scene. */
export function GraphExplorer({ data }: { data: GraphData }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "dish" | "ingredient">("all");
  const [near, setNear] = useState(false);
  const mount = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = mount.current;
    if (!node || near) return;
    const io = new IntersectionObserver(
      ([e]) => e.isIntersecting && (setNear(true), io.disconnect()),
      { rootMargin: "250px" },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [near]);

  const index = useMemo(() => new Map(data.nodes.map((n) => [n.id, n])), [data.nodes]);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return data.nodes
      .filter((n) => (filter === "all" || n.type === filter) && n.label.toLowerCase().includes(q))
      .slice(0, 8);
  }, [query, filter, data.nodes]);

  const detail = useMemo(() => {
    if (!selected) return null;
    const node = index.get(selected);
    if (!node) return null;
    const links = data.links.filter((l) => l.source === selected || l.target === selected);
    const neighbours = links
      .map((l) => {
        const other = l.source === selected ? l.target : l.source;
        return { node: index.get(other), weight: l.weight };
      })
      .filter((n): n is { node: GraphNode; weight: number } => Boolean(n.node))
      .sort((a, b) => b.weight - a.weight);
    return { node, neighbours };
  }, [selected, index, data.links]);

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_20rem]">
      {/* Canvas */}
      <div className="panel-raised overflow-hidden">
        <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b-3 border-[var(--line)] flex-wrap">
          <div className="flex items-center gap-3 text-xs">
            {[
              ["Dish", "#e62429", data.stats.dishes],
              ["Ingredient", "#22d3ee", data.stats.ingredients],
            ].map(([label, colour, count]) => (
              <span key={label as string} className="flex items-center gap-1.5">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ background: colour as string }}
                />
                {label as string}
                <span className="figures text-[var(--text-dim)]">{count as number}</span>
              </span>
            ))}
          </div>
          <p className="text-xs text-[var(--text-dim)]">drag to orbit · scroll to zoom · click a node</p>
        </div>

        <div ref={mount} className="w-full aspect-[4/3] sm:aspect-[16/10] relative">
          {near ? (
            <GraphWeb data={data} selected={selected} onSelect={setSelected} />
          ) : (
            <div className="w-full h-full halftone-shade" />
          )}
        </div>
      </div>

      {/* Side panel */}
      <aside className="space-y-4">
        <div className="panel p-4">
          <label className="block">
            <span className="text-xs uppercase tracking-widest text-[var(--text-dim)]">
              Find a node
            </span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="walnuts, sushi, butter…"
              className="mt-1 w-full ink-edge px-3 py-2 bg-transparent"
            />
          </label>

          <div className="mt-3 flex gap-1.5">
            {(["all", "dish", "ingredient"] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFilter(f)}
                className="px-2 py-1 text-xs uppercase tracking-wide border-2"
                style={{
                  borderColor: filter === f ? "var(--line)" : "transparent",
                  background: filter === f ? "var(--color-red)" : "transparent",
                  color: filter === f ? "#f4f1e8" : undefined,
                }}
              >
                {f}
              </button>
            ))}
          </div>

          {matches.length > 0 && (
            <ul className="mt-3 space-y-1">
              {matches.map((m) => (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelected(m.id);
                      setQuery("");
                    }}
                    className="w-full text-left text-sm px-2 py-1.5 panel-flat hover:-translate-x-0.5 transition-transform"
                  >
                    <span
                      className="inline-block w-2 h-2 rounded-full mr-2"
                      style={{ background: m.type === "dish" ? "#e62429" : "#22d3ee" }}
                    />
                    {m.label}
                    <span className="text-[var(--text-dim)] text-xs"> · {m.degree}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {detail ? (
          <div className="panel p-4 animate-snap">
            <p className="text-xs uppercase tracking-widest text-[var(--text-dim)]">
              {detail.node.type}
            </p>
            <h2 className="font-display text-xl leading-tight mt-0.5">{detail.node.label}</h2>

            {detail.node.type === "dish" && (
              <Link
                href={`/dishes/${detail.node.id}`}
                className="inline-block mt-2 text-sm underline"
                style={{ color: "var(--color-blue)" }}
              >
                Full nutrition profile →
              </Link>
            )}

            <p className="mt-3 text-xs uppercase tracking-widest text-[var(--text-dim)]">
              {detail.neighbours.length} connection
              {detail.neighbours.length === 1 ? "" : "s"}
            </p>
            <ul className="mt-2 space-y-1 max-h-72 overflow-y-auto">
              {detail.neighbours.map(({ node, weight }) => (
                <li key={node.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(node.id)}
                    className="w-full flex items-baseline gap-2 text-left text-sm py-1 hover:underline"
                  >
                    <span className="figures text-xs w-11 text-right shrink-0 text-[var(--text-dim)]">
                      {weight}&thinsp;g
                    </span>
                    <span className="flex-1 truncate">{node.label}</span>
                  </button>
                </li>
              ))}
            </ul>

            <button
              type="button"
              onClick={() => setSelected(null)}
              className="mt-3 text-xs uppercase tracking-widest text-[var(--text-dim)] hover:underline"
            >
              clear selection
            </button>
          </div>
        ) : (
          <div className="panel-flat halftone-shade p-4">
            <p className="font-display text-sm">Nothing selected</p>
            <p className="text-xs text-[var(--text-dim)] mt-1">
              Click a node in the web, or search above. Ingredients shared by several dishes
              are the strands that hold it together — {data.stats.shared} of the{" "}
              {data.stats.ingredients} appear in more than one recipe.
            </p>
          </div>
        )}
      </aside>
    </div>
  );
}
