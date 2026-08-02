import { getKb } from "./kb";

/** The command palette's index.
 *
 *  Built on the server and handed to the client as a trimmed projection. The
 *  knowledge base is 300 kB and the palette only matches on a name, a cuisine
 *  and a few tags — shipping the nutrient tables would be a third of a megabyte
 *  nobody reads to support a search box.
 */

export type SearchItem = {
  id: string;
  label: string;
  sub?: string;
  href: string;
  kind: "page" | "dish" | "action";
  /** Extra text matched against but never displayed. */
  terms?: string;
};

const PAGES: SearchItem[] = [
  { id: "p-analyze", label: "Analyse a photo", href: "/analyze", kind: "page", sub: "Upload and classify", terms: "upload predict camera photo image" },
  { id: "p-dishes", label: "All dishes", href: "/dishes", kind: "page", sub: "Browse 101 categories", terms: "browse list catalogue food" },
  { id: "p-explore", label: "The knowledge web", href: "/explore", kind: "page", sub: "3D ingredient graph", terms: "graph network graphrag 3d nodes" },
  { id: "p-bench", label: "Benchmarks", href: "/benchmarks", kind: "page", sub: "Every measured result", terms: "accuracy ablation mcnemar results evaluation" },
  { id: "p-methods", label: "Method", href: "/methods", kind: "page", sub: "How it decides", terms: "how works pipeline calibration conformal limits" },
  { id: "p-admin", label: "Admin console", href: "/admin", kind: "page", sub: "Operations overview", terms: "ops dashboard monitoring" },
  { id: "p-models", label: "Model registry", href: "/admin/models", kind: "page", sub: "Ablation and significance", terms: "models ablation mcnemar registry" },
  { id: "p-rel", label: "Reliability", href: "/admin/reliability", kind: "page", sub: "Calibration and conformal", terms: "calibration temperature conformal coverage ece" },
  { id: "p-rag", label: "Retrieval operations", href: "/admin/rag", kind: "page", sub: "RAG quality and spend", terms: "rag retrieval grounding cost openai" },
  { id: "p-kb", label: "Knowledge base audit", href: "/admin/knowledge-base", kind: "page", sub: "101-class provenance", terms: "usda audit provenance composite" },
];

export function buildSearchIndex(): SearchItem[] {
  const dishes: SearchItem[] = getKb().entries.map((e) => ({
    id: `d-${e.class}`,
    label: e.title,
    sub: `${e.cuisine} · ${Math.round(e.nutrients_per_100g.energy_kcal ?? 0)} kcal/100g`,
    href: `/dishes/${e.class}`,
    kind: "dish",
    terms: [e.cuisine, ...e.tags, e.method].join(" "),
  }));
  return [...PAGES, ...dishes];
}

/** Subsequence match with a score, which is what makes "chkn" find "Chicken
 *  Wings". A plain `includes` would not, and a full fuzzy library is a
 *  dependency for something this small. */
export function scoreMatch(item: SearchItem, query: string): number {
  const q = query.toLowerCase().trim();
  if (!q) return 0;

  const label = item.label.toLowerCase();
  const haystack = `${label} ${item.sub ?? ""} ${item.terms ?? ""}`.toLowerCase();

  if (label === q) return 1000;
  if (label.startsWith(q)) return 800 - label.length;
  if (label.includes(q)) return 600 - label.indexOf(q);
  if (haystack.includes(q)) return 300;

  // Subsequence: every character of the query appears in order.
  let i = 0;
  for (const ch of label) {
    if (ch === q[i]) i += 1;
    if (i === q.length) return 150 - label.length;
  }
  return -1;
}

export function search(index: SearchItem[], query: string, limit = 9): SearchItem[] {
  if (!query.trim()) {
    return index.filter((i) => i.kind === "page").slice(0, limit);
  }
  return index
    .map((item) => ({ item, score: scoreMatch(item, query) }))
    .filter((r) => r.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((r) => r.item);
}
