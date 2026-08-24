import Link from "next/link";

import { Panel } from "../../components/comic";
import { BarRow } from "../../components/charts/BarRow";
import { getKb } from "@/lib/kb";

export default function KnowledgeBasePage() {
  const kb = getKb();
  const composite = kb.entries.filter((e) => e.method === "composite");
  const flagged = kb.entries.filter((e) => e.review_flags.length > 0);

  const byCuisine = Object.entries(
    kb.entries.reduce<Record<string, number>>((acc, e) => {
      acc[e.cuisine] = (acc[e.cuisine] ?? 0) + 1;
      return acc;
    }, {}),
  )
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  const thin = composite
    .map((e) => ({ e, n: e.components?.length ?? 0 }))
    .sort((a, b) => a.n - b.n)
    .slice(0, 8);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl">Knowledge base audit</h1>
        <p className="text-sm text-[var(--text-dim)] mt-1">
          {kb.num_classes} classes, {kb.entries.length} profiles, {Object.keys(kb.nutrients).length}{" "}
          nutrients each. {kb.basis}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["coverage", `${kb.entries.length}/${kb.num_classes}`, "every class has a profile"],
          ["measured", `${kb.entries.length - composite.length}`, "direct USDA record"],
          ["composed", `${composite.length}`, "weighted ingredients"],
          ["review flags", `${flagged.length}`, flagged.length === 0 ? "nothing outstanding" : "needs attention"],
        ].map(([label, value, note]) => (
          <div key={label} className="panel p-4">
            <p className="text-xs uppercase tracking-widest text-[var(--text-dim)]">{label}</p>
            <p className="figures text-2xl mt-1">{value}</p>
            <p className="text-xs text-[var(--text-dim)] mt-1">{note}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel className="p-5">
          <h2 className="font-display text-lg">Classes by cuisine</h2>
          <p className="text-xs text-[var(--text-dim)] mt-1 mb-4">
            Top eight of {new Set(kb.entries.map((e) => e.cuisine)).size} represented.
          </p>
          <BarRow
            data={byCuisine.map(([c, n]) => ({ label: c, value: n }))}
            max={Math.max(...byCuisine.map(([, n]) => n))}
            unit=""
          />
        </Panel>

        <Panel className="p-5">
          <h2 className="font-display text-lg">Thinnest compositions</h2>
          <p className="text-xs text-[var(--text-dim)] mt-1 mb-3">
            Dishes approximated from the fewest ingredient records carry the most
            uncertainty. These are the entries to revisit first.
          </p>
          <ul className="space-y-1.5 text-sm">
            {thin.map(({ e, n }) => (
              <li key={e.class} className="flex items-baseline justify-between gap-3">
                <Link href={`/dishes/${e.class}`} className="hover:underline truncate">
                  {e.title}
                </Link>
                <span className="figures text-xs shrink-0" style={{ color: n <= 2 ? "var(--color-amber)" : undefined }}>
                  {n} record{n === 1 ? "" : "s"}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel className="p-5">
        <h2 className="font-display text-lg">Provenance policy</h2>
        <p className="mt-2 text-sm text-[var(--text-dim)] max-w-prose">
          A composed figure is not the same kind of fact as a measured one, so the two are
          never presented alike. Every dish page, every API response and every retrieved
          document states which it is, and the {composite.length} composed entries list the
          USDA records and gram weights they were built from. The alternative — quietly
          averaging ingredients and reporting the result as a measurement — would be the
          single easiest way for this project to be confidently wrong.
        </p>
      </Panel>
    </div>
  );
}
