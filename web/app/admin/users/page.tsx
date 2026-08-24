"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../../components/AuthProvider";
import { SpiderBar } from "../../components/SpiderBar";

type Person = {
  uid: string;
  email: string | null;
  predictions: number;
  questions: number;
  abstained: number;
  mean_confidence: number;
  first_seen: string;
  last_seen: string;
  top_dishes: [string, number][];
};

type Analytics = {
  enabled: boolean;
  error?: string;
  backend?: string;
  days: number;
  scanned: { predictions: number; questions: number; limit: number };
  totals: {
    predictions: number;
    questions: number;
    feedback: number;
    sessions: number;
    abstained: number;
    thumbs_down: number;
  };
  users: Person[];
  daily: {
    day: string;
    predictions: number;
    abstained: number;
    mean_confidence: number;
    mean_set_size: number;
    mean_ms: number;
  }[];
  spend: { day: string; questions: number; cost_usd: number; refused: number }[];
  top_dishes: { title: string; count: number; mean_confidence: number; abstained: number }[];
  review_queue: { at: string; title: string; confidence: number; set_size: number }[];
  negative_feedback: { at: string; food_class: string; note: string | null; email?: string }[];
};

function day(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** Every account, and what each one has been analysing. */
export default function AdminUsers() {
  const { authFetch } = useAuth();
  const [data, setData] = useState<Analytics | null>(null);
  const [days, setDays] = useState(14);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await authFetch(`/api/analytics?days=${days}`, { cache: "no-store" });
      const payload = await res.json();
      if (!res.ok) setError(payload.error ?? "Could not load analytics.");
      else {
        setData(payload as Analytics);
        setError(null);
      }
    } catch {
      setError("The model service is unreachable.");
    }
  }, [authFetch, days]);

  useEffect(() => {
    void load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  if (error) {
    return (
      <div className="panel p-5">
        <h1 className="font-display text-xl">People</h1>
        <p className="mt-2 text-sm text-[var(--text-dim)]">{error}</p>
      </div>
    );
  }

  if (!data) return <SpiderBar label="Reading the record" />;

  if (!data.enabled) {
    return (
      <div className="panel p-5">
        <h1 className="font-display text-xl">Storage is not configured</h1>
        <p className="mt-2 text-sm text-[var(--text-dim)] max-w-prose">
          The service is running without a database, so predictions are answered but not kept.
          Set FIREBASE_CREDENTIALS (or MONGODB_URI) on the model service and this page fills
          in. {data.error && <span className="figures">{data.error}</span>}
        </p>
      </div>
    );
  }

  const peak = Math.max(1, ...data.daily.map((d) => d.predictions));
  const truncated = data.scanned.predictions >= data.scanned.limit;

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-display text-2xl">People</h1>
          <p className="text-sm text-[var(--text-dim)] mt-1">
            Every signed-in account and what it has analysed. Stored in {data.backend}.
          </p>
        </div>
        <div className="flex gap-1" role="group" aria-label="Time range">
          {[7, 14, 30, 90].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setDays(n)}
              className="ink-edge px-3 py-1.5 text-sm"
              style={
                days === n ? { background: "var(--color-red)", color: "#f4f1e8" } : undefined
              }
            >
              {n}d
            </button>
          ))}
        </div>
      </div>

      {truncated && (
        <p
          className="ink-edge px-3 py-2 text-sm"
          style={{ background: "var(--color-amber)", color: "#0b0b0f" }}
        >
          Showing the most recent {data.scanned.limit.toLocaleString()} predictions. Older rows
          exist and are counted in the totals, but the per-day and per-person breakdowns below
          cover only what was read.
        </p>
      )}

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        {[
          ["accounts", String(data.totals.sessions), `over ${data.days} days`],
          ["predictions", data.totals.predictions.toLocaleString(), "all time"],
          ["questions", data.totals.questions.toLocaleString(), "all time"],
          [
            "declined",
            String(data.totals.abstained),
            `${data.totals.thumbs_down} marked wrong`,
          ],
        ].map(([label, value, note]) => (
          <div key={label} className="panel p-4">
            <p className="text-xs uppercase tracking-widest text-[var(--text-dim)]">{label}</p>
            <p className="figures text-2xl mt-1">{value}</p>
            <p className="text-xs text-[var(--text-dim)] mt-1">{note}</p>
          </div>
        ))}
      </div>

      {/* Volume per day. A bar per day, labelled — with this few points a
          sparkline would hide the only thing worth reading, which is whether
          anybody used it yesterday. */}
      <div className="panel p-5">
        <h2 className="font-display text-lg">Predictions per day</h2>
        {data.daily.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--text-dim)]">No predictions in this window.</p>
        ) : (
          <div className="mt-4 flex items-end justify-start gap-1.5 h-40 overflow-x-auto">
            {data.daily.map((d) => (
              <div key={d.day} className="flex flex-col items-center gap-1 min-w-[2.2rem] max-w-[4.5rem] flex-1">
                <span className="figures text-[10px] text-[var(--text-dim)]">
                  {d.predictions}
                </span>
                <div className="w-full flex flex-col justify-end h-28">
                  {d.abstained > 0 && (
                    <div
                      style={{
                        height: `${(d.abstained / peak) * 100}%`,
                        background: "var(--color-amber)",
                      }}
                      title={`${d.abstained} declined`}
                    />
                  )}
                  <div
                    style={{
                      height: `${((d.predictions - d.abstained) / peak) * 100}%`,
                      background: "var(--color-red)",
                    }}
                  />
                </div>
                <span className="text-[10px] text-[var(--text-dim)] whitespace-nowrap">
                  {day(d.day)}
                </span>
              </div>
            ))}
          </div>
        )}
        <p className="mt-3 text-xs text-[var(--text-dim)]">
          <span
            className="inline-block w-2.5 h-2.5 align-middle mr-1"
            style={{ background: "var(--color-red)" }}
          />
          answered
          <span
            className="inline-block w-2.5 h-2.5 align-middle ml-4 mr-1"
            style={{ background: "var(--color-amber)" }}
          />
          declined as uncertain
        </p>
      </div>

      {/* The people table. */}
      <div className="panel p-0 overflow-x-auto max-w-full">
        <div className="p-5 pb-3">
          <h2 className="font-display text-lg">Accounts</h2>
          <p className="text-xs text-[var(--text-dim)] mt-1">
            Sorted by volume. Ranked by predictions in the window, not by sign-up date.
          </p>
        </div>
        <table className="w-full text-sm min-w-[46rem]">
          <thead>
            <tr className="border-y-2 border-[var(--line)]">
              {["Account", "Predictions", "Declined", "Questions", "Mean conf.", "Most analysed", "Last seen"].map(
                (h) => (
                  <th key={h} className="text-left font-display uppercase tracking-wide px-5 py-2.5">
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {data.users.map((p) => (
              <tr key={p.uid} className="border-b border-[var(--line)]/15">
                <td className="px-5 py-2.5">
                  <span className="block truncate max-w-[14rem]">{p.email ?? "—"}</span>
                  <span className="figures text-[10px] text-[var(--text-dim)]">{p.uid}</span>
                </td>
                <td className="px-5 py-2.5 figures">{p.predictions}</td>
                <td
                  className="px-5 py-2.5 figures"
                  style={p.abstained ? { color: "var(--color-amber)" } : undefined}
                >
                  {p.abstained}
                </td>
                <td className="px-5 py-2.5 figures">{p.questions}</td>
                <td className="px-5 py-2.5 figures">
                  {(p.mean_confidence * 100).toFixed(1)}%
                </td>
                <td className="px-5 py-2.5">
                  {p.top_dishes.map(([title, n]) => `${title} (${n})`).join(", ") || "—"}
                </td>
                <td className="px-5 py-2.5 figures text-xs">{day(p.last_seen)}</td>
              </tr>
            ))}
            {data.users.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-8 text-center text-sm text-[var(--text-dim)]">
                  Nobody has analysed anything in this window.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="panel p-5">
          <h2 className="font-display text-lg">Most analysed dishes</h2>
          {data.top_dishes.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--text-dim)]">Nothing yet.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {data.top_dishes.map((d) => (
                <li key={d.title}>
                  <div className="flex justify-between gap-3 text-sm">
                    <span className="truncate">{d.title}</span>
                    <span className="figures shrink-0">
                      {d.count} · {(d.mean_confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div
                    className="h-1.5 mt-1"
                    style={{
                      width: `${(d.count / data.top_dishes[0].count) * 100}%`,
                      background: "var(--color-blue)",
                    }}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="panel p-5">
          <h2 className="font-display text-lg">Questions and spend</h2>
          {data.spend.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--text-dim)]">
              No questions in this window, so nothing was spent.
            </p>
          ) : (
            <table className="w-full text-sm mt-3">
              <thead>
                <tr className="border-b-2 border-[var(--line)]">
                  {["Day", "Questions", "Refused", "Cost"].map((h) => (
                    <th key={h} className="text-left font-display uppercase text-xs py-1.5">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.spend.map((s) => (
                  <tr key={s.day} className="border-b border-[var(--line)]/12">
                    <td className="py-1.5 figures text-xs">{day(s.day)}</td>
                    <td className="py-1.5 figures">{s.questions}</td>
                    <td className="py-1.5 figures">{s.refused}</td>
                    <td className="py-1.5 figures">${s.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
                <tr>
                  <td className="py-2 font-semibold">total</td>
                  <td className="py-2 figures font-semibold">
                    {data.spend.reduce((a, s) => a + s.questions, 0)}
                  </td>
                  <td />
                  <td className="py-2 figures font-semibold">
                    ${data.spend.reduce((a, s) => a + s.cost_usd, 0).toFixed(4)}
                  </td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* The review queue. These two lists are the only signal here that a
          labelled test split cannot produce. */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="panel p-5">
          <h2 className="font-display text-lg">Declined by the model</h2>
          <p className="text-xs text-[var(--text-dim)] mt-1">
            Low confidence or too many candidates. Worth looking at as a batch: a cluster of
            one dish means the training data is thin there.
          </p>
          {data.review_queue.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--text-dim)]">Nothing outstanding.</p>
          ) : (
            <ul className="mt-3 space-y-1.5 text-sm max-h-64 overflow-y-auto">
              {data.review_queue.map((r, i) => (
                <li key={`${r.at}-${i}`} className="flex justify-between gap-3">
                  <span className="truncate">{r.title}</span>
                  <span className="figures text-xs shrink-0">
                    {(r.confidence * 100).toFixed(1)}% · {r.set_size} candidates · {day(r.at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="panel p-5">
          <h2 className="font-display text-lg">Marked wrong by a person</h2>
          <p className="text-xs text-[var(--text-dim)] mt-1">
            A thumbs-down on a confident prediction is the most valuable row in this console —
            it is a labelled error the test split does not contain.
          </p>
          {data.negative_feedback.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--text-dim)]">None so far.</p>
          ) : (
            <ul className="mt-3 space-y-1.5 text-sm max-h-64 overflow-y-auto">
              {data.negative_feedback.map((f, i) => (
                <li key={`${f.at}-${i}`}>
                  <div className="flex justify-between gap-3">
                    <span className="truncate">{f.food_class.replace(/_/g, " ")}</span>
                    <span className="figures text-xs shrink-0">{day(f.at)}</span>
                  </div>
                  {f.note && <p className="text-xs text-[var(--text-dim)]">{f.note}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
