import type { Metadata } from "next";

import { Beat, Caption, GutterRule, Panel, StatPanel } from "../components/comic";
import { conformalReport, ensembleReport, labelFor, probes, ragReport } from "@/lib/reports";

export const metadata: Metadata = {
  title: "Benchmarks — FoodGenome AI",
  description:
    "Every measured result: the ablation table, McNemar significance tests, conformal coverage and the retrieval evaluation.",
};

export default function BenchmarksPage() {
  const rows = ensembleReport.results;
  const best = ensembleReport.best;
  const agreement = ensembleReport.agreement;
  const conformal99 = conformalReport.results.find((r) => r.alpha === 0.01) as
    | Record<string, { coverage: number; avg_set_size: number; singleton_rate: number }>
    | undefined;
  const lacTop1 = conformal99?.lac_top1;

  return (
    <main className="flex-1 w-full">
      <section className="mx-auto max-w-6xl px-5 pt-10 pb-6">
        <Beat
          n="—"
          title="THE EVIDENCE"
          lede={`Every figure on this page was written by an evaluation script, not typed in. The test split holds ${ensembleReport.n_test.toLocaleString()} images and was untouched until final evaluation; model selection used a ${ensembleReport.n_val.toLocaleString()}-image slice carved out of train.`}
        />
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <StatPanel value={`${best.test_top1}%`} label="test top-1" note={best.method} tilt="left" />
        <StatPanel
          value={`${best.test_top5}%`}
          label="test top-5"
          accent="var(--color-blue)"
        />
        <StatPanel
          value={`${agreement.oracle_top1}%`}
          label="oracle ceiling"
          note="if a perfect combiner always picked the right member"
          accent="var(--color-amber)"
          tilt="right"
        />
        <StatPanel
          value={lacTop1 ? `${lacTop1.coverage}%` : "—"}
          label="conformal coverage"
          note={lacTop1 ? `average ${lacTop1.avg_set_size} candidates` : undefined}
          accent="var(--color-green)"
        />
      </section>

      <GutterRule />

      {/* ── Single models ─────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 py-12">
        <Beat n="01" title="SINGLE HEADS" lede="Each probe trained on cached frozen features." />
        <Panel className="mt-6 p-0 overflow-x-auto">
          <table className="w-full text-sm min-w-[38rem]">
            <thead>
              <tr className="border-b-3 border-[var(--line)]">
                {["Head", "Params", "Val top-1", "Test top-1", "Test top-5", "Train"].map((h) => (
                  <th key={h} className="text-left font-display uppercase tracking-wide px-4 py-3">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {probes
                .slice()
                .sort((a, b) => b.test_top1 - a.test_top1)
                .map((p) => (
                  <tr key={p.name} className="border-b border-[var(--line)]/20">
                    <td className="px-4 py-2.5 font-semibold">{labelFor(p.name)}</td>
                    <td className="px-4 py-2.5 figures">{(p.params / 1e6).toFixed(2)} M</td>
                    <td className="px-4 py-2.5 figures">{p.val_top1.toFixed(2)}</td>
                    <td className="px-4 py-2.5 figures" style={{ color: "var(--color-red)" }}>
                      {p.test_top1.toFixed(2)}
                    </td>
                    <td className="px-4 py-2.5 figures">{p.test_top5.toFixed(2)}</td>
                    <td className="px-4 py-2.5 figures">{p.minutes.toFixed(1)} min</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </Panel>
      </section>

      {/* ── Ablation ──────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 pb-12">
        <Beat
          n="02"
          title="THE ABLATION"
          lede="Every subset of members, in probability and logit space, plus weights tuned on validation only."
        />
        <Panel className="mt-6 p-0 overflow-x-auto">
          <table className="w-full text-sm min-w-[42rem]">
            <thead>
              <tr className="border-b-3 border-[var(--line)]">
                {["Members", "Method", "Test top-1", "Test top-5"].map((h) => (
                  <th key={h} className="text-left font-display uppercase tracking-wide px-4 py-3">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const winner = i === 0;
                return (
                  <tr
                    key={`${r.members.join("+")}-${r.method}`}
                    className="border-b border-[var(--line)]/20"
                    style={winner ? { background: "var(--color-amber)", color: "#0b0b0f" } : undefined}
                  >
                    <td className="px-4 py-2.5">{r.members.map(labelFor).join(" + ")}</td>
                    <td className="px-4 py-2.5 text-[var(--text-dim)]" style={winner ? { color: "#0b0b0f" } : undefined}>
                      {r.method}
                    </td>
                    <td className="px-4 py-2.5 figures font-semibold">{r.test_top1.toFixed(3)}</td>
                    <td className="px-4 py-2.5 figures">{r.test_top5.toFixed(3)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>

        <Caption className="mt-6 max-w-3xl">
          The winner is a parameter-free average. A 3.97M-parameter gated fusion head, trained
          for 21.9 minutes, lost to it — and did not significantly beat its own best single
          input.
        </Caption>
      </section>

      {/* ── Significance ──────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 pb-12">
        <Beat
          n="03"
          title="IS IT REAL?"
          lede="A few tenths of a point on 25,250 images is inside the range where two systems differ by luck. Exact McNemar tests on paired predictions decide it."
        />
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {Object.entries(ensembleReport.mcnemar).map(([label, m]) => (
            <Panel key={label} className="p-5">
              <p className="text-sm font-semibold">{label}</p>
              <p className="figures text-2xl mt-2">
                p = {m.p < 0.000001 ? "<0.000001" : m.p.toFixed(6)}
              </p>
              <p
                className="mt-1 text-sm font-semibold"
                style={{ color: m.significant ? "var(--color-green)" : "var(--color-amber)" }}
              >
                {m.significant ? "✓ significant" : "! not significant"}
              </p>
              <p className="text-xs text-[var(--text-dim)] mt-2">
                {m.a_only} images only the first got right, {m.b_only} only the second.
              </p>
            </Panel>
          ))}
        </div>
      </section>

      {/* ── Error correlation ─────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 pb-12">
        <Beat
          n="04"
          title="WHY THE GAINS ARE SMALL"
          lede="Ensembling only helps when members fail on different images. These mostly fail on the same ones."
        />
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {Object.entries(agreement.pairs).map(([pair, v]) => {
            const [a, b] = pair.split(" vs ");
            return (
              <Panel key={pair} className="p-5">
                <p className="font-display text-sm">
                  {labelFor(a)} vs {labelFor(b)}
                </p>
                <p className="figures text-3xl mt-3" style={{ color: "var(--color-red)" }}>
                  {v.shared_error_rate.toFixed(1)}%
                </p>
                <p className="text-xs text-[var(--text-dim)] mt-1">
                  of the first model&apos;s errors are shared with the second
                </p>
                <dl className="mt-3 space-y-1 text-xs">
                  {[
                    ["both correct", v.both_correct],
                    ["only first", v.only_first],
                    ["only second", v.only_second],
                    ["both wrong", v.both_wrong],
                  ].map(([k, val]) => (
                    <div key={k as string} className="flex justify-between">
                      <dt className="text-[var(--text-dim)]">{k as string}</dt>
                      <dd className="figures">{(val as number).toFixed(2)}%</dd>
                    </div>
                  ))}
                </dl>
              </Panel>
            );
          })}
        </div>
        <Caption className="mt-6 max-w-3xl">
          The oracle — accuracy if a perfect combiner always picked a member that was right —
          is {agreement.oracle_top1}%. Only {agreement.all_wrong}% of test images defeat every
          model. That gap is the ceiling this approach can reach.
        </Caption>
      </section>

      <GutterRule />

      {/* ── RAG ───────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-5 py-12">
        <Beat
          n="05"
          title="RETRIEVAL AND ANSWERS"
          lede={`A ${ragReport.gold_cases}-case gold set whose ground truth is known before the system is asked, including questions it is supposed to refuse.`}
        />
        <Panel className="mt-6 p-0 overflow-x-auto">
          <table className="w-full text-sm min-w-[40rem]">
            <thead>
              <tr className="border-b-3 border-[var(--line)]">
                {["Category", "n", "R@1", "R@5", "Answerable@1", "Correct", "Refused"].map((h) => (
                  <th key={h} className="text-left font-display uppercase tracking-wide px-4 py-3">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(ragReport.retrieval).map(([cat, r]) => {
                const ans = ragReport.answers?.by_category[cat];
                return (
                  <tr key={cat} className="border-b border-[var(--line)]/20">
                    <td className="px-4 py-2.5">{cat.replace(/_/g, " ")}</td>
                    <td className="px-4 py-2.5 figures">{r.n}</td>
                    <td className="px-4 py-2.5 figures">{r["recall@1"].toFixed(1)}</td>
                    <td className="px-4 py-2.5 figures">{r["recall@5"].toFixed(1)}</td>
                    <td className="px-4 py-2.5 figures" style={{ color: "var(--color-blue)" }}>
                      {r["answerable@1"].toFixed(1)}
                    </td>
                    <td className="px-4 py-2.5 figures" style={{ color: "var(--color-green)" }}>
                      {ans ? ans.correct.toFixed(1) : "—"}
                    </td>
                    <td className="px-4 py-2.5 figures">{ans ? ans.refused.toFixed(0) : "—"}</td>
                  </tr>
                );
              })}
              {ragReport.answers?.by_category.out_of_scope && (
                <tr className="border-b border-[var(--line)]/20" style={{ background: "var(--color-amber)", color: "#0b0b0f" }}>
                  <td className="px-4 py-2.5">out of scope</td>
                  <td className="px-4 py-2.5 figures">
                    {ragReport.answers.by_category.out_of_scope.n}
                  </td>
                  <td className="px-4 py-2.5" colSpan={3}>
                    correct behaviour is refusal
                  </td>
                  <td className="px-4 py-2.5 figures font-semibold">
                    {ragReport.answers.by_category.out_of_scope.correct.toFixed(0)}
                  </td>
                  <td className="px-4 py-2.5 figures font-semibold">
                    {ragReport.answers.by_category.out_of_scope.refused.toFixed(0)}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Panel>

        {ragReport.answers && (
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatPanel
              value={`${ragReport.answers.overall.answered_correct}%`}
              label="answered correctly"
              accent="var(--color-green)"
            />
            <StatPanel
              value={`${ragReport.answers.overall.refusal_accuracy}%`}
              label="refusal accuracy"
              note={`${ragReport.answers.overall.false_refusals} false refusals`}
              accent="var(--color-blue)"
            />
            <StatPanel
              value={`${ragReport.answers.overall.grounded_rate}%`}
              label="grounded"
              note="every figure traced to a source"
              accent="var(--color-green)"
            />
            <StatPanel
              value={`$${ragReport.answers.overall.total_cost_usd.toFixed(4)}`}
              label="cost of the run"
              note={`${ragReport.gold_cases} questions`}
              accent="var(--color-amber)"
            />
          </div>
        )}

        <Caption className="mt-6 max-w-3xl">
          Strict recall@1 understates nutrient lookups: every miss returned a portion document
          where a macros document was labelled, and all of them contained the correct figure.
          Answerable@1 measures what matters — whether the top hit can actually support the
          answer.
        </Caption>
      </section>
    </main>
  );
}
