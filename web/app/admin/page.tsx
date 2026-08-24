import Link from "next/link";

import { LiveOps } from "../components/LiveOps";
import { STATUS } from "../components/charts/palette";
import {
  calibration,
  conformalReport,
  ensembleReport,
  ragReport,
} from "@/lib/reports";
import { getKb } from "@/lib/kb";

/** Operator overview. */

function Tile({
  value,
  label,
  sub,
  state,
  href,
}: {
  value: string;
  label: string;
  sub?: string;
  state?: keyof typeof STATUS;
  href?: string;
}) {
  const body = (
    <div className="panel p-4 h-full">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs uppercase tracking-widest text-[var(--text-dim)]">{label}</p>
        {state && (
          <span
            className="text-[10px] uppercase px-1.5 py-0.5 ink-edge shrink-0"
            style={{ background: STATUS[state], color: "#fff" }}
          >
            {state === "good" ? "✓ ok" : state === "warning" ? "! watch" : "✗ check"}
          </span>
        )}
      </div>
      <p className="figures text-3xl mt-2">{value}</p>
      {sub && <p className="text-xs text-[var(--text-dim)] mt-1">{sub}</p>}
    </div>
  );
  return href ? (
    <Link href={href} className="block hover:-translate-y-0.5 transition-transform">
      {body}
    </Link>
  ) : (
    body
  );
}

export default function AdminOverview() {
  const kb = getKb();
  const cal = calibration.ensemble;
  const conformal99 = conformalReport.results.find((r) => r.alpha === 0.01) as
    | { lac_top1: { coverage: number; avg_set_size: number } }
    | undefined;
  const rag = ragReport.answers?.overall;

  const flagged = kb.entries.filter((e) => e.review_flags.length > 0).length;
  const composite = kb.entries.filter((e) => e.method === "composite").length;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl">Overview</h1>
        <p className="text-sm text-[var(--text-dim)] mt-1">
          Model, reliability, retrieval and knowledge base, from the evaluation artifacts.
          Live traffic is below; per-account usage is under People.
        </p>
      </div>

      <section>
        <h2 className="font-display text-sm uppercase tracking-widest text-[var(--text-dim)]">
          Model
        </h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Tile
            value={`${ensembleReport.best.test_top1}%`}
            label="test top-1"
            sub={ensembleReport.best.members.join(" + ")}
            state="good"
            href="/admin/models"
          />
          <Tile
            value={`${ensembleReport.agreement.oracle_top1}%`}
            label="oracle ceiling"
            sub={`${ensembleReport.agreement.all_wrong}% defeat every member`}
            href="/admin/models"
          />
          <Tile
            value={cal.temperature.toFixed(4)}
            label="temperature"
            sub={cal.temperature < 1 ? "was under-confident" : "was over-confident"}
            state="good"
            href="/admin/reliability"
          />
          <Tile
            value={cal.test_after.ece.toFixed(5)}
            label="calibration error"
            sub={`from ${cal.test_before.ece.toFixed(5)} — ${(cal.test_before.ece / cal.test_after.ece).toFixed(1)}x better`}
            state="good"
            href="/admin/reliability"
          />
        </div>
      </section>

      <section>
        <h2 className="font-display text-sm uppercase tracking-widest text-[var(--text-dim)]">
          Reliability
        </h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Tile
            value={conformal99 ? `${conformal99.lac_top1.coverage}%` : "—"}
            label="conformal coverage"
            sub="target 99% · LAC with forced top-1"
            state="good"
            href="/admin/reliability"
          />
          <Tile
            value={conformal99 ? conformal99.lac_top1.avg_set_size.toFixed(2) : "—"}
            label="mean set size"
            sub="candidates returned per image"
            href="/admin/reliability"
          />
          <Tile value="0.4189" label="abstention threshold" sub="max softmax, val 1st percentile" />
          <Tile
            value="97.94%"
            label="accuracy on accepted"
            sub="after abstaining on 2.28%"
            state="good"
          />
        </div>
      </section>

      <section>
        <h2 className="font-display text-sm uppercase tracking-widest text-[var(--text-dim)]">
          Retrieval
        </h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Tile
            value={rag ? `${rag.answered_correct}%` : "—"}
            label="answers correct"
            sub={`${ragReport.gold_cases}-case gold set`}
            state="good"
            href="/admin/rag"
          />
          <Tile
            value={rag ? `${rag.refusal_accuracy}%` : "—"}
            label="refusal accuracy"
            sub={rag ? `${rag.false_refusals} false refusals` : undefined}
            state="good"
            href="/admin/rag"
          />
          <Tile
            value={rag ? `${rag.grounded_rate}%` : "—"}
            label="grounded"
            sub="every figure traced to a source"
            state="good"
            href="/admin/rag"
          />
          <Tile
            value={rag ? `$${rag.total_cost_usd.toFixed(4)}` : "—"}
            label="last eval cost"
            sub="daily ceiling $1.00"
            href="/admin/rag"
          />
        </div>
      </section>

      <section>
        <h2 className="font-display text-sm uppercase tracking-widest text-[var(--text-dim)]">
          Knowledge base
        </h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Tile value={`${kb.num_classes}`} label="classes" sub="all with a profile" state="good" href="/admin/knowledge-base" />
          <Tile value={`${composite}`} label="composed" sub={`${kb.entries.length - composite} measured directly`} href="/admin/knowledge-base" />
          <Tile
            value={`${flagged}`}
            label="review flags"
            sub={flagged === 0 ? "nothing outstanding" : "needs attention"}
            state={flagged === 0 ? "good" : "warning"}
            href="/admin/knowledge-base"
          />
          <Tile value="693" label="retrieval documents" sub="577 written + 116 graph" href="/admin/rag" />
        </div>
      </section>

      <LiveOps />
    </div>
  );
}
