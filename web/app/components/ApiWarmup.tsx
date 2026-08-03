"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Status = "checking" | "cold" | "warming" | "ready" | "demo" | "unreachable";

/** Wakes the model service and shows a spider spinning the web while it loads.
 *
 *  The service sleeps on the free tier, and the first request afterwards pays
 *  roughly thirty seconds of container wake plus backbone download. Without
 *  this, a first-time visitor uploads a photo and watches a button do nothing
 *  for half a minute, which reads as broken.
 *
 *  So the page asks the service to start loading the moment it opens, and shows
 *  honest progress while it does. By the time a photo is chosen the model is
 *  usually resident and the prediction is immediate.
 *
 *  The bar is deliberately **not** a fake percentage. There is no progress
 *  signal to report — the service tells us "loaded" or "not loaded" and nothing
 *  in between — so the spider walks a fixed circuit and the elapsed seconds are
 *  shown as the honest measure of how long it has taken.
 */
export function ApiWarmup({ onReady }: { onReady?: () => void } = {}) {
  const [status, setStatus] = useState<Status>("checking");
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef<number | null>(null);
  const notified = useRef(false);

  const finish = useCallback(() => {
    setStatus("ready");
    if (!notified.current) {
      notified.current = true;
      onReady?.();
    }
  }, [onReady]);

  useEffect(() => {
    let cancelled = false;
    let poll: ReturnType<typeof setInterval> | null = null;

    (async () => {
      try {
        const res = await fetch("/api/warm", { cache: "no-store" });
        const data = await res.json();
        if (cancelled) return;

        if (data.status === "ready") return finish();
        if (data.status === "demo") return setStatus("demo");
        if (data.status === "unreachable") return setStatus("unreachable");

        // Cold. Kick the load off and poll until the backbones are resident.
        setStatus("warming");
        startedAt.current = Date.now();
        void fetch("/api/warm", { method: "POST" });

        poll = setInterval(async () => {
          try {
            const r = await fetch("/api/warm", { cache: "no-store" });
            const d = await r.json();
            if (cancelled) return;
            setElapsed(Math.round((Date.now() - (startedAt.current ?? Date.now())) / 1000));
            if (d.status === "ready") {
              if (poll) clearInterval(poll);
              finish();
            }
          } catch {
            /* a failed poll during a container wake is expected; keep trying */
          }
        }, 3000);
      } catch {
        if (!cancelled) setStatus("unreachable");
      }
    })();

    return () => {
      cancelled = true;
      if (poll) clearInterval(poll);
    };
  }, [finish]);

  if (status === "ready" || status === "checking") return null;

  if (status === "demo") {
    return (
      <div className="panel-flat px-4 py-2.5 text-sm flex items-center gap-2 flex-wrap">
        <span
          className="ink-edge px-2 py-0.5 text-xs font-semibold shrink-0"
          style={{ background: "var(--color-amber)", color: "#0b0b0f" }}
        >
          ! Demo mode
        </span>
        <span className="text-[var(--text-dim)]">
          No model service is connected, so predictions are illustrative and every result
          says so.
        </span>
      </div>
    );
  }

  if (status === "unreachable") {
    return (
      <div className="panel-flat px-4 py-2.5 text-sm flex items-center gap-2 flex-wrap">
        <span
          className="ink-edge px-2 py-0.5 text-xs font-semibold shrink-0"
          style={{ background: "var(--color-red)", color: "#f4f1e8" }}
        >
          ✗ Offline
        </span>
        <span className="text-[var(--text-dim)]">
          The model service is not responding. Uploads will fall back to demo responses.
        </span>
      </div>
    );
  }

  return (
    <div className="panel px-4 py-3" role="status" aria-live="polite">
      <div className="flex items-center gap-3 flex-wrap">
        <svg viewBox="0 0 44 24" className="w-16 h-8 shrink-0" aria-hidden="true">
          {/* The strand the spider walks along. */}
          <path
            d="M2 12 Q22 18 42 12"
            fill="none"
            stroke="var(--line)"
            strokeWidth="1.3"
            opacity="0.45"
          />
          <g className="warm-spider">
            <g stroke="var(--line)" strokeWidth="1.4" strokeLinecap="round" fill="none">
              <path d="M-3.2 -1.6 -6 -4.4M3.2 -1.6 6 -4.4M-3.6 0.4 -7 0M3.6 0.4 7 0M-3.2 2.4 -6 4.4M3.2 2.4 6 4.4" />
            </g>
            <ellipse cx="0" cy="1" rx="3" ry="3.6" fill="var(--color-red)" stroke="var(--line)" strokeWidth="1.2" />
            <circle cx="0" cy="-2.4" r="1.7" fill="var(--line)" />
          </g>
        </svg>

        <div className="min-w-0">
          <p className="font-display text-sm uppercase tracking-wide">Waking the model</p>
          <p className="text-xs text-[var(--text-dim)]">
            The service sleeps when idle. Loading two backbones — usually about 30 seconds
            {elapsed > 0 && <> · <span className="figures">{elapsed}s</span></>}
          </p>
        </div>

        <span className="ml-auto text-xs text-[var(--text-dim)] hidden sm:block">
          you can choose a photo meanwhile
        </span>
      </div>
    </div>
  );
}
