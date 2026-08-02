import { Caption, Panel } from "../../components/comic";
import { ReliabilityDiagram } from "../../components/charts/ReliabilityDiagram";
import { calibration, conformalReport } from "@/lib/reports";

type ConformalMethod = {
  qhat: number;
  coverage: number;
  avg_set_size: number;
  median_set_size: number;
  max_set_size: number;
  singleton_rate: number;
  empty_rate: number;
};

const METHODS = ["lac", "aps", "lac_top1", "aps_top1"] as const;

export default function ReliabilityPage() {
  const cal = calibration.ensemble;
  const before = cal.test_before;
  const after = cal.test_after;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl">Reliability</h1>
        <p className="text-sm text-[var(--text-dim)] mt-1">
          Whether the confidence the model reports matches how often it is right, and what
          guarantee the prediction set actually carries.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <Panel className="p-5">
          <h2 className="font-display text-lg">Reliability diagram</h2>
          <p className="text-xs text-[var(--text-dim)] mt-1 mb-4">
            Below the diagonal is over-confident; above it is under-confident. This ensemble
            sat <strong>above</strong> the line — it was systematically too modest.
          </p>
          <ReliabilityDiagram before={before.bins} after={after.bins} />
        </Panel>

        <div className="space-y-4">
          {[
            ["Temperature", cal.temperature.toFixed(4), cal.temperature < 1 ? "sharpens an under-confident model" : "softens an over-confident one"],
            ["ECE", `${before.ece.toFixed(5)} → ${after.ece.toFixed(5)}`, `${(before.ece / after.ece).toFixed(1)}× improvement`],
            ["MCE", `${before.mce.toFixed(4)} → ${after.mce.toFixed(4)}`, "worst single bin"],
            ["Brier", `${before.brier.toFixed(4)} → ${after.brier.toFixed(4)}`, "lower is better"],
            ["NLL", `${before.nll.toFixed(4)} → ${after.nll.toFixed(4)}`, "lower is better"],
            ["Mean confidence", `${(before.mean_confidence * 100).toFixed(1)}% → ${(after.mean_confidence * 100).toFixed(1)}%`, `accuracy is ${after.top1.toFixed(2)}%`],
          ].map(([label, value, note]) => (
            <div key={label} className="panel-tight p-3">
              <p className="text-xs uppercase tracking-widest text-[var(--text-dim)]">{label}</p>
              <p className="figures text-lg mt-0.5">{value}</p>
              <p className="text-xs text-[var(--text-dim)] mt-0.5">{note}</p>
            </div>
          ))}
        </div>
      </div>

      <Caption className="max-w-4xl">
        Accuracy is unchanged by calibration — {before.top1.toFixed(3)}% before and after.
        Temperature scaling is monotonic, so it cannot reorder predictions. What it changes is
        whether the number attached to a prediction means anything, and mean confidence moving
        from {(before.mean_confidence * 100).toFixed(1)}% to{" "}
        {(after.mean_confidence * 100).toFixed(1)}% against {after.top1.toFixed(2)}% accuracy
        is the whole point.
      </Caption>

      <Panel className="p-0 overflow-x-auto">
        <div className="p-5 pb-3">
          <h2 className="font-display text-lg">Conformal prediction sets</h2>
          <p className="text-xs text-[var(--text-dim)] mt-1">
            Calibrated on {conformalReport.calibration_samples.toLocaleString()} validation
            images, measured on {conformalReport.test_samples.toLocaleString()} test images.
            Coverage is a property of the procedure, not a claim about any one image.
          </p>
        </div>
        <table className="w-full text-sm min-w-[44rem]">
          <thead>
            <tr className="border-y-2 border-[var(--line)]">
              {["Target", "Method", "Coverage", "Mean size", "Singletons", "Empty", "Max"].map((h) => (
                <th key={h} className="text-left font-display uppercase tracking-wide px-5 py-2.5">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {conformalReport.results.flatMap((row) =>
              METHODS.map((method) => {
                const m = row[method] as ConformalMethod | undefined;
                if (!m) return null;
                const shipped = row.alpha === 0.01 && method === "lac_top1";
                return (
                  <tr
                    key={`${row.alpha}-${method}`}
                    className="border-b border-[var(--line)]/15"
                    style={shipped ? { background: "var(--color-green)", color: "#fff" } : undefined}
                  >
                    <td className="px-5 py-2 figures">{row.target_coverage}%</td>
                    <td className="px-5 py-2 uppercase text-xs">
                      {method.replace("_", " ")}
                      {shipped && <span className="ml-2 font-semibold">shipped</span>}
                    </td>
                    <td className="px-5 py-2 figures font-semibold">{m.coverage.toFixed(2)}%</td>
                    <td className="px-5 py-2 figures">{m.avg_set_size.toFixed(3)}</td>
                    <td className="px-5 py-2 figures">{m.singleton_rate.toFixed(1)}%</td>
                    <td className="px-5 py-2 figures">{m.empty_rate.toFixed(1)}%</td>
                    <td className="px-5 py-2 figures">{m.max_set_size}</td>
                  </tr>
                );
              }),
            )}
          </tbody>
        </table>
      </Panel>

      <Panel className="p-5">
        <h2 className="font-display text-lg">Two findings worth keeping</h2>
        <div className="mt-3 grid gap-4 md:grid-cols-2 text-sm">
          <div>
            <p className="font-semibold">95% coverage is not a meaningful target here.</p>
            <p className="text-[var(--text-dim)] mt-1">
              Top-1 accuracy is 97.16%, so any target below that is already met by the single
              best guess — the threshold collapses to zero and the &ldquo;set&rdquo; contains
              one class. The machinery only does work at 99%.
            </p>
          </div>
          <div>
            <p className="font-semibold">Calibration and deployment must use the same rule.</p>
            <p className="text-[var(--text-dim)] mt-1">
              An earlier version forced the top-1 class in at test time but scored without it
              during calibration. That silently rescued the images whose top score exceeded
              the threshold and produced 99.1% coverage against a 90% target — the guarantee
              was void, and the number looked better for it.
            </p>
          </div>
        </div>
      </Panel>
    </div>
  );
}
