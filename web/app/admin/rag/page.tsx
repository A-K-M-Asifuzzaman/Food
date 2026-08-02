import { Caption, Panel } from "../../components/comic";
import { BarRow } from "../../components/charts/BarRow";
import { ragReport } from "@/lib/reports";

export default function RagPage() {
  const overall = ragReport.answers?.overall;
  const byCat = ragReport.answers?.by_category ?? {};
  const retrieval = ragReport.retrieval;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl">Retrieval operations</h1>
        <p className="text-sm text-[var(--text-dim)] mt-1">
          Quality of the hybrid retriever and the grounded generator, measured on a{" "}
          {ragReport.gold_cases}-case gold set whose answers were known before the system was
          asked.
        </p>
      </div>

      {overall && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["answers correct", `${overall.answered_correct}%`, "excluding out-of-scope"],
            ["refusal accuracy", `${overall.refusal_accuracy}%`, `${overall.false_refusals} false refusals`],
            ["grounded", `${overall.grounded_rate}%`, "every figure traced to a source"],
            ["evaluation cost", `$${overall.total_cost_usd.toFixed(4)}`, `${overall.wall_seconds.toFixed(0)}s wall clock`],
          ].map(([label, value, note]) => (
            <div key={label} className="panel p-4">
              <p className="text-xs uppercase tracking-widest text-[var(--text-dim)]">{label}</p>
              <p className="figures text-2xl mt-1">{value}</p>
              <p className="text-xs text-[var(--text-dim)] mt-1">{note}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel className="p-5">
          <h2 className="font-display text-lg">Retrieval — answerable at rank 1</h2>
          <p className="text-xs text-[var(--text-dim)] mt-1 mb-4">
            Whether the top hit actually contains what the question asks for.
          </p>
          <BarRow
            data={Object.entries(retrieval).map(([cat, r]) => ({
              label: cat,
              value: r["answerable@1"],
              note: `strict recall@1 ${r["recall@1"]}% · MRR ${r.mrr} · nDCG ${r.ndcg}`,
            }))}
          />
        </Panel>

        <Panel className="p-5">
          <h2 className="font-display text-lg">Answers correct</h2>
          <p className="text-xs text-[var(--text-dim)] mt-1 mb-4">
            Scored by exact numeric match against the knowledge base, not by a judge model.
          </p>
          <BarRow
            data={Object.entries(byCat).map(([cat, m]) => ({
              label: cat,
              value: m.correct,
              note: `${m.n} cases · median ${m.median_ms} ms · ${m.grounded}% grounded`,
            }))}
          />
        </Panel>
      </div>

      <Caption className="max-w-4xl">
        Strict recall@1 reads 64.6% on nutrient lookups, and that is a labelling artefact
        rather than a failure: every miss returned a portion document where a macros document
        was labelled, and all seventeen contained the correct figure. Both metrics are kept —
        strict recall stays comparable with published IR numbers, answerable@1 measures
        whether the pipeline can answer.
      </Caption>

      <Panel className="p-5">
        <h2 className="font-display text-lg">Cost control</h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-3 text-sm">
          {[
            ["Out-of-scope questions", "$0.00", "CRAG declines them in under 130 ms without calling the API at all"],
            ["Per answered question", "~$0.00035", "roughly 2,900 questions per dollar on gpt-4.1-mini"],
            ["Daily ceiling", "$1.00", "past it the pipeline serves deterministic template answers from the same records"],
          ].map(([label, value, note]) => (
            <div key={label}>
              <p className="text-xs uppercase tracking-widest text-[var(--text-dim)]">{label}</p>
              <p className="figures text-xl mt-0.5">{value}</p>
              <p className="text-xs text-[var(--text-dim)] mt-1">{note}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-[var(--text-dim)]">
          Per-day spend and grounding failures from live traffic are not shown: they need the
          metrics middleware writing to Firestore. The figures above are from the last
          evaluation run, and are labelled as such rather than presented as production
          telemetry.
        </p>
      </Panel>
    </div>
  );
}
