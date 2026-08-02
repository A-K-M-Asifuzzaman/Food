"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

type Dish = {
  slug: string;
  title: string;
  cuisine: string;
  tags: string[];
  method: "direct" | "composite";
  kcal: number;
  protein: number;
  serving: string;
};

type SortKey = "title" | "kcal" | "protein";

export function DishBrowser({ dishes }: { dishes: Dish[] }) {
  const [query, setQuery] = useState("");
  const [cuisine, setCuisine] = useState("all");
  const [sort, setSort] = useState<SortKey>("title");
  const [descending, setDescending] = useState(false);

  const cuisines = useMemo(
    () => ["all", ...Array.from(new Set(dishes.map((d) => d.cuisine))).sort()],
    [dishes],
  );

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = dishes.filter((d) => {
      if (cuisine !== "all" && d.cuisine !== cuisine) return false;
      if (!q) return true;
      // Tags are searched too, so "dessert" finds things whose title never says
      // dessert — which is most of them.
      return (
        d.title.toLowerCase().includes(q) ||
        d.cuisine.toLowerCase().includes(q) ||
        d.tags.some((t) => t.includes(q))
      );
    });
    const direction = descending ? -1 : 1;
    return filtered.sort((a, b) => {
      if (sort === "title") return a.title.localeCompare(b.title) * direction;
      return (a[sort] - b[sort]) * direction;
    });
  }, [dishes, query, cuisine, sort, descending]);

  return (
    <div>
      <div className="panel p-4 flex flex-wrap gap-3 items-end">
        <label className="flex-1 min-w-[12rem]">
          <span className="block text-xs uppercase tracking-widest text-[var(--text-dim)] mb-1">
            Search
          </span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="pizza, dessert, Japanese…"
            className="w-full ink-edge px-3 py-2 bg-transparent"
          />
        </label>

        <label>
          <span className="block text-xs uppercase tracking-widest text-[var(--text-dim)] mb-1">
            Cuisine
          </span>
          <select
            value={cuisine}
            onChange={(e) => setCuisine(e.target.value)}
            className="ink-edge px-3 py-2 bg-transparent"
          >
            {cuisines.map((c) => (
              <option key={c} value={c}>
                {c === "all" ? "All cuisines" : c}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span className="block text-xs uppercase tracking-widest text-[var(--text-dim)] mb-1">
            Sort
          </span>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="ink-edge px-3 py-2 bg-transparent"
          >
            <option value="title">Name</option>
            <option value="kcal">Calories</option>
            <option value="protein">Protein</option>
          </select>
        </label>

        <button
          type="button"
          onClick={() => setDescending((v) => !v)}
          className="ink-edge px-3 py-2 font-semibold"
          aria-label={descending ? "Sort ascending" : "Sort descending"}
        >
          {descending ? "↓ desc" : "↑ asc"}
        </button>

        <p className="figures text-sm text-[var(--text-dim)] ml-auto">
          {shown.length}/{dishes.length}
        </p>
      </div>

      {shown.length === 0 ? (
        <p className="mt-10 text-center text-[var(--text-dim)]">
          Nothing matches “{query}”. The knowledge base covers the 101 Food-101 categories.
        </p>
      ) : (
        <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((d, i) => (
            <li key={d.slug}>
              <Link
                href={`/dishes/${d.slug}`}
                className="panel p-4 h-full flex flex-col transition-transform hover:-translate-x-0.5 hover:-translate-y-0.5 block"
                style={{ transform: i % 7 === 3 ? "rotate(-0.5deg)" : undefined }}
              >
                <div className="flex items-start justify-between gap-2">
                  <h2 className="font-display text-lg leading-tight">{d.title}</h2>
                  <span
                    className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 ink-edge shrink-0"
                    style={{
                      background:
                        d.method === "direct" ? "var(--color-green)" : "var(--color-amber)",
                      color: "#0b0b0f",
                    }}
                  >
                    {d.method === "direct" ? "measured" : "composed"}
                  </span>
                </div>

                <p className="text-xs text-[var(--text-dim)] mt-1">
                  {d.cuisine} · {d.tags.join(" · ")}
                </p>

                <dl className="mt-3 flex gap-4 text-sm mt-auto pt-3">
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-[var(--text-dim)]">
                      kcal/100g
                    </dt>
                    <dd className="figures" style={{ color: "var(--color-red)" }}>
                      {Math.round(d.kcal)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-[var(--text-dim)]">
                      protein
                    </dt>
                    <dd className="figures" style={{ color: "var(--color-blue)" }}>
                      {d.protein.toFixed(1)} g
                    </dd>
                  </div>
                </dl>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
