"use client";

import { useState } from "react";

type Citation = { n: number; title: string; kind: string; doc_id: string };

type AskResponse = {
  answer: string;
  mode: "generated" | "template" | "insufficient";
  grounded: boolean;
  grounding?: { checked?: number; reason?: string };
  citations: Citation[];
  usage?: { model: string; cost_usd: number };
  latency_ms: number;
};

const SUGGESTIONS = [
  "How much sodium is in this?",
  "Is this a good source of protein?",
  "What is this made of?",
  "What dishes are similar to this?",
];

/** How the answer was produced. Stating this is not a technical detail — a
 *  reader deciding whether to trust a nutrition figure needs to know whether a
 *  model wrote it, whether its numbers were checked, and what happened if they
 *  failed the check. */
const MODES = {
  generated: {
    label: "Verified against sources",
    colour: "var(--color-green)",
    mark: "✓",
    note: "Every number in this answer was checked against the retrieved USDA records.",
  },
  template: {
    label: "Read directly from the record",
    colour: "var(--color-blue)",
    mark: "≡",
    note: "Returned straight from the knowledge base rather than written by a model.",
  },
  insufficient: {
    label: "Outside the knowledge base",
    colour: "var(--color-amber)",
    mark: "!",
    note: "Nothing in the 101-dish knowledge base addresses this question.",
  },
} as const;

export function AskPanel({ foodClass, title }: { foodClass: string; title: string }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(text: string) {
    const q = text.trim();
    if (q.length < 2 || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, food_class: foodClass }),
      });
      const payload = await res.json();
      if (!res.ok) setError(payload.error ?? "That did not work.");
      else setResult(payload as AskResponse);
    } catch {
      setError("Could not reach the answer service.");
    } finally {
      setBusy(false);
    }
  }

  const mode = result ? MODES[result.mode] : null;

  return (
    <section className="panel p-6">
      <h3 className="font-display text-xl">Ask about this {title.toLowerCase()}</h3>
      <p className="mt-1 text-sm text-[var(--text-dim)]">
        Answered only from USDA records. Say &ldquo;this&rdquo; — the dish is already known.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void submit(question);
        }}
        className="mt-4 flex gap-2"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="How much sodium is in this?"
          maxLength={400}
          className="flex-1 ink-edge px-3 py-2 bg-transparent min-w-0"
          aria-label="Your question"
        />
        <button
          type="submit"
          disabled={busy || question.trim().length < 2}
          className="ink-edge px-4 py-2 font-display uppercase tracking-wide shrink-0 disabled:opacity-50"
          style={{ background: "var(--color-blue)", color: "#f4f1e8" }}
        >
          {busy ? "…" : "Ask"}
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setQuestion(s);
              void submit(s);
            }}
            disabled={busy}
            className="panel-flat px-2 py-1 text-xs disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>

      {error && (
        <p className="mt-4 text-sm" style={{ color: "var(--color-red)" }}>
          {error}
        </p>
      )}

      {result && mode && (
        <div className="mt-5 animate-panel-in">
          <p className="text-base leading-relaxed">{result.answer}</p>

          <div className="mt-4 flex items-center gap-2 flex-wrap">
            <span
              className="ink-edge px-2 py-0.5 text-xs font-semibold"
              style={{ background: mode.colour, color: "#0b0b0f" }}
            >
              {mode.mark} {mode.label}
            </span>
            <span className="figures text-xs text-[var(--text-dim)]">
              {result.latency_ms} ms
            </span>
            {result.grounding?.checked ? (
              <span className="figures text-xs text-[var(--text-dim)]">
                {result.grounding.checked} figures verified
              </span>
            ) : null}
          </div>

          <p className="mt-2 text-xs text-[var(--text-dim)]">{mode.note}</p>

          {result.grounding?.reason && (
            <p className="mt-2 text-xs" style={{ color: "var(--color-amber)" }}>
              The generated answer was withheld: {result.grounding.reason}.
            </p>
          )}

          {result.citations.length > 0 && (
            <ol className="mt-4 space-y-1 text-sm">
              {result.citations.map((c) => (
                <li key={c.doc_id} className="flex gap-2">
                  <span className="figures shrink-0" style={{ color: "var(--color-blue)" }}>
                    [{c.n}]
                  </span>
                  <span>
                    {c.title}
                    <span className="text-[var(--text-dim)]"> — {c.kind.replace(/_/g, " ")}</span>
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  );
}
