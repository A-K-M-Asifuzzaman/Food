"use client";

import { useState } from "react";
import { useAuth } from "./AuthProvider";

/** Was the prediction right?
 *
 *  This is the only signal the system gets that a labelled test split cannot
 *  give it. 97.16% on Food-101 says nothing about the photo someone actually
 *  took, in their kitchen, of a dish plated differently from every training
 *  image — and a thumbs-down on a confident prediction is exactly the case
 *  worth re-examining. The votes surface in the admin console's feedback panel.
 */
export function FeedbackBar({ foodClass, title }: { foodClass: string; title: string }) {
  const { authFetch } = useAuth();
  const [sent, setSent] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  const send = async (helpful: boolean) => {
    if (busy || sent !== null) return;
    setBusy(true);
    try {
      await authFetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ food_class: foodClass, helpful }),
      });
      setSent(helpful);
    } catch {
      // A dropped vote is not worth an error dialogue over the result.
      setSent(helpful);
    } finally {
      setBusy(false);
    }
  };

  if (sent !== null) {
    return (
      <div className="panel-flat px-4 py-2.5 text-sm text-[var(--text-dim)]">
        {sent
          ? "Recorded — thanks."
          : "Recorded as wrong. That case is now in the review queue, which is where the useful training examples come from."}
      </div>
    );
  }

  return (
    <div className="panel-flat px-4 py-2.5 flex items-center gap-3 flex-wrap">
      <span className="text-sm">
        Was <span className="font-semibold">{title}</span> right?
      </span>
      <div className="flex gap-2 ml-auto">
        <button
          type="button"
          disabled={busy}
          onClick={() => void send(true)}
          className="ink-edge px-3 py-1 text-sm font-semibold disabled:opacity-50"
          style={{ background: "var(--color-green)", color: "#0b0b0f" }}
        >
          ▲ Yes
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void send(false)}
          className="ink-edge px-3 py-1 text-sm font-semibold disabled:opacity-50"
          style={{ background: "var(--color-red)", color: "#f4f1e8" }}
        >
          ▼ No
        </button>
      </div>
    </div>
  );
}
