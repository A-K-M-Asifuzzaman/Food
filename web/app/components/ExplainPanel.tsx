"use client";

import { useState } from "react";

type ExplainResponse = {
  overlay: string;
  title: string;
  backbone: string;
  grid: number[];
  peak_fraction: number;
  method: string;
  latency_ms: number;
};

/** Grad-CAM, presented with its own limitations attached.
 *
 *  Measured on this model, attribution lands in the outer ring of the frame at
 *  0.87x chance — better than random, but not sharply on the food. Showing a
 *  heatmap without that context invites a viewer to read precision into it that
 *  the method does not have, and the first time they notice it highlighting a
 *  tablecloth they will stop believing everything else on the page.
 *
 *  So `peak_fraction` is displayed rather than hidden, and a diffuse map is
 *  labelled diffuse.
 */
export function ExplainPanel({ file, foodClass }: { file: File; foodClass: string }) {
  const [result, setResult] = useState<ExplainResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    const body = new FormData();
    body.append("image", file);
    body.append("food_class", foodClass);
    try {
      const res = await fetch("/api/explain", { method: "POST", body });
      const payload = await res.json();
      if (!res.ok) setError(payload.error ?? "Could not produce an explanation.");
      else setResult(payload as ExplainResponse);
    } catch {
      setError("Could not reach the explain service.");
    } finally {
      setBusy(false);
    }
  }

  const diffuse = result ? result.peak_fraction > 0.2 : false;

  return (
    <section className="panel p-6">
      <div className="flex items-baseline justify-between gap-4 flex-wrap">
        <h3 className="font-display text-xl">Where the model looked</h3>
        {!result && (
          <button
            type="button"
            onClick={() => void run()}
            disabled={busy}
            className="ink-edge px-3 py-1.5 text-sm font-semibold disabled:opacity-50"
          >
            {busy ? "Computing…" : "Show attribution"}
          </button>
        )}
      </div>

      {!result && !error && (
        <p className="mt-2 text-sm text-[var(--text-dim)]">
          Grad-CAM over the final transformer block, back through the pooling head to the
          patch grid. Computed on demand — it needs a second forward and backward pass.
        </p>
      )}

      {error && (
        <p className="mt-3 text-sm" style={{ color: "var(--color-red)" }}>
          {error}
        </p>
      )}

      {result && (
        <div className="mt-4 animate-panel-in">
          {/* eslint-disable-next-line @next/next/no-img-element -- server-composited data URI */}
          <img
            src={result.overlay}
            alt={`Attribution heatmap for ${result.title}. Brighter red marks image regions that contributed more to the prediction.`}
            className="w-full ink-edge"
          />

          <dl className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            {[
              ["Backbone", result.backbone.replace(/_/g, "-")],
              ["Patch grid", result.grid.join("×")],
              ["Concentration", `${(result.peak_fraction * 100).toFixed(1)}%`],
              ["Computed in", `${result.latency_ms} ms`],
            ].map(([k, v]) => (
              <div key={k as string} className="panel-tight p-2">
                <dt className="text-xs uppercase tracking-wide text-[var(--text-dim)]">{k}</dt>
                <dd className="figures">{v}</dd>
              </div>
            ))}
          </dl>

          <p className="mt-4 text-sm text-[var(--text-dim)]">
            {diffuse ? (
              <>
                <strong style={{ color: "var(--color-amber)" }}>This map is diffuse.</strong>{" "}
                A large share of the frame scored above half intensity, so it indicates a
                region rather than an object. The classifier reads a globally pooled feature
                vector, so position is partly discarded before it ever sees the image —
                attribution has to be recovered back through that pooling.
              </>
            ) : (
              <>
                Attribution is concentrated on a small part of the frame, which is the
                behaviour you want: the prediction rests on a specific region rather than
                the whole picture.
              </>
            )}
          </p>
        </div>
      )}
    </section>
  );
}
