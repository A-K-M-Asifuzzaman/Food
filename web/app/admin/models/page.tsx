import { Panel } from "../../components/comic";
import { BarRow } from "../../components/charts/BarRow";
import { ensembleReport, labelFor, probes } from "@/lib/reports";

export default function ModelsPage() {
  const best = ensembleReport.best;
  const solo = probes.filter((p) => p.backbones.length === 1);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl">Model registry</h1>
        <p className="text-sm text-[var(--text-dim)] mt-1">
          Every head that was trained, every combination that was evaluated, and whether the
          differences between them survive a significance test.
        </p>
      </div>

      <Panel className="p-5">
        <h2 className="font-display text-lg">Single heads on test</h2>
        <p className="text-xs text-[var(--text-dim)] mt-1 mb-4">
          MLP probes over cached frozen features. Emphasis marks the member that carries the
          ensemble.
        </p>
        <BarRow
          data={solo
            .slice()
            .sort((a, b) => b.test_top1 - a.test_top1)
            .map((p) => ({
              label: labelFor(p.name),
              value: p.test_top1,
              note: `${(p.params / 1e6).toFixed(2)}M parameters, trained in ${p.minutes.toFixed(1)} minutes`,
            }))}
          max={100}
          emphasis="SigLIP-SO400M"
        />
      </Panel>

      <Panel className="p-0 overflow-x-auto">
        <div className="p-5 pb-3">
          <h2 className="font-display text-lg">Full ablation</h2>
          <p className="text-xs text-[var(--text-dim)] mt-1">
            All subsets, probability and logit space, plus weights fitted on validation only.
            Never on test.
          </p>
        </div>
        <table className="w-full text-sm min-w-[40rem]">
          <thead>
            <tr className="border-y-2 border-[var(--line)]">
              {["Members", "Method", "Weights", "Top-1", "Top-5"].map((h) => (
                <th key={h} className="text-left font-display uppercase tracking-wide px-5 py-2.5">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ensembleReport.results.map((r, i) => (
              <tr
                key={`${r.members.join("+")}-${r.method}`}
                className="border-b border-[var(--line)]/15"
                style={i === 0 ? { background: "var(--color-amber)", color: "#0b0b0f" } : undefined}
              >
                <td className="px-5 py-2">{r.members.map(labelFor).join(" + ")}</td>
                <td className="px-5 py-2">{r.method}</td>
                <td className="px-5 py-2 figures text-xs">{r.weights.join(" / ")}</td>
                <td className="px-5 py-2 figures font-semibold">{r.test_top1.toFixed(3)}</td>
                <td className="px-5 py-2 figures">{r.test_top5.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div className="grid gap-4 md:grid-cols-2">
        {Object.entries(ensembleReport.mcnemar).map(([label, m]) => (
          <Panel key={label} className="p-5">
            <p className="text-xs uppercase tracking-widest text-[var(--text-dim)]">
              McNemar exact test
            </p>
            <p className="text-sm font-semibold mt-1">{label}</p>
            <div className="flex items-baseline gap-3 mt-3">
              <p className="figures text-2xl">
                p = {m.p < 0.000001 ? "<1e-6" : m.p.toFixed(6)}
              </p>
              <span
                className="text-xs uppercase px-2 py-0.5 ink-edge"
                style={{
                  background: m.significant ? "var(--color-green)" : "var(--color-amber)",
                  color: m.significant ? "#fff" : "#0b0b0f",
                }}
              >
                {m.significant ? "✓ significant" : "! not significant"}
              </span>
            </div>
            <p className="text-xs text-[var(--text-dim)] mt-2">
              Discordant pairs: {m.a_only} / {m.b_only}. Only images where the two systems
              disagree carry information about which is better.
            </p>
          </Panel>
        ))}
      </div>

      <Panel className="p-5">
        <h2 className="font-display text-lg">Why ensembling helps so little</h2>
        <p className="text-xs text-[var(--text-dim)] mt-1 mb-4">
          Share of the first model&apos;s errors that the second also gets wrong. Ensembling
          only pays when members fail on different images.
        </p>
        <BarRow
          data={Object.entries(ensembleReport.agreement.pairs).map(([pair, v]) => {
            const [a, b] = pair.split(" vs ");
            return {
              label: `${labelFor(a).split("-")[0]} / ${labelFor(b).split("-")[0]}`,
              value: v.shared_error_rate,
              note: `both correct ${v.both_correct}% · both wrong ${v.both_wrong}%`,
            };
          })}
          max={100}
        />
        <p className="mt-4 text-sm text-[var(--text-dim)]">
          Oracle accuracy — if a perfect combiner always picked a member that was right — is{" "}
          <span className="figures">{ensembleReport.agreement.oracle_top1}%</span>. Only{" "}
          <span className="figures">{ensembleReport.agreement.all_wrong}%</span> of test
          images defeat every member. Against a shipped {best.test_top1}%, that remaining gap
          is the ceiling of this approach.
        </p>
      </Panel>
    </div>
  );
}
