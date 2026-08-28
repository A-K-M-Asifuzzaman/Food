"use client";

import { useEffect, useState } from "react";

import { useAuth } from "./AuthProvider";
import { SpiderBar } from "./SpiderBar";

type Stats = {
  uptime_seconds: number;
  requests: number;
  errors: number;
  error_rate: number;
  endpoints: Record<string, { count: number; errors: number; p50_ms: number | null; p95_ms: number | null; p99_ms: number | null }>;
  predictions: {
    total: number;
    abstained: number;
    recent: { at: number; title: string; confidence: number; set_size: number; abstained: boolean; ms: number }[];
  };
  retrieval: { questions: number; refusals: number; grounding_failures: number; openai_cost_usd: number };
  feedback: { up: number; down: number; recent: { at: number; food_class: string; helpful: boolean; note: string | null }[] };
  memory: { rss_mb?: number };
  model: { name: string; loaded: boolean; device: string; test_top1: number; temperature: number };
  note: string;
};

function ago(ts: number): string {
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}

function duration(s: number): string {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

/** Live operational data from the running model service. */
export function LiveOps() {
  const { authFetch } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await authFetch("/api/stats", { cache: "no-store" });
        const data = await res.json();
        if (!alive) return;
        if (!res.ok) setError(data.error ?? "unavailable");
        else {
          setStats(data as Stats);
          setError(null);
        }
      } catch {
        if (alive) setError("unreachable");
      }
    };
    void load();
    const t = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [authFetch]);

  if (error) {
    return (
      <div className="panel p-5">
        <h2 className="font-display text-lg">Live operations</h2>
        <p className="mt-2 text-sm text-[var(--text-dim)]">
          The model service is not reachable ({error}). It sleeps after about two days idle
          and takes a minute to wake — open{" "}
          <a href="/analyze" className="underline" style={{ color: "var(--color-blue)" }}>
            the analyser
          </a>{" "}
          to wake it.
        </p>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="panel p-5">
        <SpiderBar label="Reading counters" />
      </div>
    );
  }

  const conf = (v: number) => `${(v * 100).toFixed(1)}%`;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <h2 className="font-display text-sm uppercase tracking-widest text-[var(--text-dim)]">
            Live operations
          </h2>
          <span className="text-xs text-[var(--text-dim)]">
            refreshes every 15s · window {duration(stats.uptime_seconds)}
          </span>
        </div>

        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["requests", String(stats.requests), `${stats.error_rate}% errors`],
            ["predictions", String(stats.predictions.total), `${stats.predictions.abstained} abstained`],
            ["questions", String(stats.retrieval.questions), `${stats.retrieval.refusals} refused`],
            ["memory", stats.memory.rss_mb ? `${(stats.memory.rss_mb / 1024).toFixed(2)} GB` : "—", stats.model.device],
          ].map(([label, value, note]) => (
            <div key={label} className="panel p-4">
              <p className="text-xs uppercase tracking-widest text-[var(--text-dim)]">{label}</p>
              <p className="figures text-2xl mt-1">{value}</p>
              <p className="text-xs text-[var(--text-dim)] mt-1">{note}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Latency percentiles */}
      <div className="panel p-0 overflow-x-auto max-w-full">
        <div className="p-5 pb-3">
          <h3 className="font-display text-lg">Latency by endpoint</h3>
          <p className="text-xs text-[var(--text-dim)] mt-1">
            Nearest-rank percentiles over the last 500 requests to each route.
          </p>
        </div>
        <table className="w-full text-sm min-w-[34rem]">
          <thead>
            <tr className="border-y-2 border-[var(--line)]">
              {["Endpoint", "Requests", "Errors", "p50", "p95", "p99"].map((h) => (
                <th key={h} className="text-left font-display uppercase tracking-wide px-5 py-2.5">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(stats.endpoints).map(([path, s]) => (
              <tr key={path} className="border-b border-[var(--line)]/15">
                <td className="px-5 py-2 figures text-xs">{path}</td>
                <td className="px-5 py-2 figures">{s.count}</td>
                <td className="px-5 py-2 figures" style={s.errors ? { color: "var(--color-red)" } : undefined}>
                  {s.errors}
                </td>
                <td className="px-5 py-2 figures">{s.p50_ms ?? "—"}</td>
                <td className="px-5 py-2 figures">{s.p95_ms ?? "—"}</td>
                <td className="px-5 py-2 figures">{s.p99_ms ?? "—"}</td>
              </tr>
            ))}
            {Object.keys(stats.endpoints).length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-6 text-center text-sm text-[var(--text-dim)]">
                  No requests since this container started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Prediction feed, including the review queue */}
        <div className="panel p-5">
          <h3 className="font-display text-lg">Prediction feed</h3>
          <p className="text-xs text-[var(--text-dim)] mt-1 mb-3">
            Most recent first. Rows marked <span style={{ color: "var(--color-amber)" }}>abstained</span>{" "}
            are the low-confidence review queue — the model declined rather than guessed.
          </p>
          {stats.predictions.recent.length === 0 ? (
            <p className="text-sm text-[var(--text-dim)]">Nothing predicted yet.</p>
          ) : (
            <ul className="space-y-1 max-h-72 overflow-y-auto text-sm">
              {stats.predictions.recent.map((p, i) => (
                <li
                  key={`${p.at}-${i}`}
                  className="flex items-baseline gap-2 py-1 border-b border-[var(--line)]/12"
                >
                  <span className="flex-1 truncate">{p.title}</span>
                  <span className="figures text-xs">{conf(p.confidence)}</span>
                  <span className="figures text-xs text-[var(--text-dim)]">set {p.set_size}</span>
                  {p.abstained && (
                    <span
                      className="text-[10px] uppercase px-1 ink-edge shrink-0"
                      style={{ background: "var(--color-amber)", color: "#0b0b0f" }}
                    >
                      abstained
                    </span>
                  )}
                  <span className="figures text-xs text-[var(--text-dim)] shrink-0">{ago(p.at)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Cost and grounding */}
        <div className="panel p-5">
          <h3 className="font-display text-lg">Retrieval and spend</h3>
          <dl className="mt-3 space-y-2 text-sm">
            {[
              ["questions answered", String(stats.retrieval.questions)],
              ["refused as out of scope", String(stats.retrieval.refusals)],
              ["grounding failures", String(stats.retrieval.grounding_failures)],
              ["OpenAI spend this window", `$${stats.retrieval.openai_cost_usd.toFixed(5)}`],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 border-b border-[var(--line)]/12 pb-1.5">
                <dt className="text-[var(--text-dim)]">{k}</dt>
                <dd className="figures">{v}</dd>
              </div>
            ))}
          </dl>

          <h3 className="font-display text-lg mt-6">User feedback</h3>
          <p className="text-xs text-[var(--text-dim)] mt-1">
            A thumbs-down on a confident prediction is the case worth re-examining, and it
            appears in no accuracy metric computed on a labelled split.
          </p>
          <div className="mt-3 flex gap-4">
            <span className="figures text-xl" style={{ color: "var(--color-green)" }}>
              ▲ {stats.feedback.up}
            </span>
            <span className="figures text-xl" style={{ color: "var(--color-red)" }}>
              ▼ {stats.feedback.down}
            </span>
          </div>
          {stats.feedback.recent.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm max-h-32 overflow-y-auto">
              {stats.feedback.recent.map((f, i) => (
                <li key={`${f.at}-${i}`} className="flex items-baseline gap-2">
                  <span style={{ color: f.helpful ? "var(--color-green)" : "var(--color-red)" }}>
                    {f.helpful ? "▲" : "▼"}
                  </span>
                  <span className="flex-1 truncate">{f.food_class.replace(/_/g, " ")}</span>
                  <span className="figures text-xs text-[var(--text-dim)]">{ago(f.at)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <p className="text-xs text-[var(--text-dim)]">
        {stats.note}. Model: {stats.model.name} on {stats.model.device}, temperature{" "}
        {stats.model.temperature}.
      </p>
    </div>
  );
}
