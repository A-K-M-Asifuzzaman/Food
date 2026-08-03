"use client";

import { useCallback, useRef, useState } from "react";

import type { PredictResponse } from "@/lib/types";

import { AskPanel } from "./AskPanel";
import { useAuth } from "./AuthProvider";
import { SignInGate } from "./SignInGate";
import { FeedbackBar } from "./FeedbackBar";
import { ExplainPanel } from "./ExplainPanel";
import { ResultPanels } from "./ResultPanels";
import { WebLoader } from "./WebLoader";

type State =
  | { phase: "idle" }
  | { phase: "working"; preview: string }
  | { phase: "done"; preview: string; result: PredictResponse; file: File }
  | { phase: "error"; preview?: string; message: string };

export function Analyzer() {
  const { user, loading, authFetch } = useAuth();
  const [state, setState] = useState<State>({ phase: "idle" });
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const analyze = useCallback(async (file: File) => {
    const preview = URL.createObjectURL(file);
    setState({ phase: "working", preview });

    const body = new FormData();
    body.append("image", file);

    try {
      const res = await authFetch("/api/predict", { method: "POST", body });
      const payload = await res.json();
      if (!res.ok) {
        setState({ phase: "error", preview, message: payload.error ?? "Request failed." });
        return;
      }
      setState({ phase: "done", preview, result: payload as PredictResponse, file });
    } catch {
      setState({
        phase: "error",
        preview,
        message: "Could not reach the analyzer. Check your connection and try again.",
      });
    }
  }, [authFetch]);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file) void analyze(file);
    },
    [analyze],
  );

  const preview = "preview" in state ? state.preview : undefined;

  // A prediction is filed against an account, so the account comes first. The
  // gate is here rather than on the route so the page's explanation, the
  // warm-up bar and the disclaimer all still render — a signed-out visitor
  // should be able to read what this does before being asked to join.
  if (!loading && !user) return <SignInGate />;

  return (
    <div className="w-full">
      <div className="grid gap-6 lg:grid-cols-5">
        {/* Dropzone */}
        <div className="lg:col-span-2">
          <div
            id="dropzone"
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className="panel p-6 transition-transform"
            style={{
              transform: dragging ? "translate(-2px,-2px)" : undefined,
              borderColor: dragging ? "var(--color-red)" : undefined,
            }}
          >
            <h2 className="font-display text-2xl">Drop a plate</h2>
            <p className="mt-1 text-sm text-[var(--text-dim)]">
              JPEG, PNG or WebP. The photo is analysed and never stored.
            </p>

            {preview ? (
              // eslint-disable-next-line @next/next/no-img-element -- blob: preview, not an optimisable asset
              <img
                src={preview}
                alt="The dish you uploaded"
                className="mt-4 w-full aspect-4/3 object-cover ink-edge"
              />
            ) : (
              <div className="mt-4 w-full aspect-4/3 halftone ink-edge grid place-items-center">
                <span className="sfx text-5xl opacity-25">?</span>
              </div>
            )}

            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void analyze(file);
              }}
            />

            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={state.phase === "working"}
              className="mt-4 w-full ink-edge px-4 py-3 font-display text-lg uppercase tracking-wide disabled:opacity-60"
              style={{ background: "var(--color-red)", color: "#f4f1e8" }}
            >
              {state.phase === "working" ? "Reading…" : "Choose a photo"}
            </button>
          </div>
        </div>

        {/* Result column */}
        <div className="lg:col-span-3">
          {state.phase === "idle" && (
            <div className="panel-flat halftone p-8 h-full grid place-items-center text-center">
              <div>
                <p className="font-display text-2xl">Nothing on the plate yet</p>
                <p className="mt-2 text-sm text-[var(--text-dim)] max-w-sm">
                  Every result shows its calibrated confidence, the full candidate set it
                  cannot rule out, and the USDA record behind each number.
                </p>
              </div>
            </div>
          )}

          {state.phase === "working" && (
            <div className="panel p-8 h-full grid place-items-center">
              <WebLoader
                label="Spinning the strand"
                sub="Reading the genome of your plate…"
              />
            </div>
          )}

          {state.phase === "error" && (
            <div className="panel p-8 h-full">
              <p className="sfx text-4xl" style={{ color: "var(--color-red)" }}>
                KRAK
              </p>
              <p className="mt-2 font-display text-xl">That didn&apos;t work</p>
              <p className="mt-2 text-[var(--text-dim)]">{state.message}</p>
              <button
                type="button"
                onClick={() => setState({ phase: "idle" })}
                className="mt-4 ink-edge px-4 py-2 font-semibold"
              >
                Try another photo
              </button>
            </div>
          )}

          {state.phase === "done" && (
            <div className="panel-flat halftone p-6 h-full grid place-items-center text-center">
              <div>
                <p className="font-display text-2xl">{state.result.prediction.title}</p>
                <p className="figures text-4xl mt-2">
                  {(state.result.prediction.confidence * 100).toFixed(1)}%
                </p>
                <p className="mt-2 text-sm text-[var(--text-dim)]">Full breakdown below</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {state.phase === "done" && (
        <div className="mt-6 space-y-6">
          <ResultPanels result={state.result} />
          {state.result.source === "model" && (
            <FeedbackBar
              foodClass={state.result.prediction.class}
              title={state.result.prediction.title}
            />
          )}
          {/* Only offered when the prediction came from the real model. There is
              nothing to explain about, or ask of, a demo response. */}
          {state.result.source === "model" && state.result.ood.is_food && (
            <div className="grid gap-6 lg:grid-cols-2">
              <ExplainPanel file={state.file} foodClass={state.result.prediction.class} />
              <AskPanel
                foodClass={state.result.prediction.class}
                title={state.result.prediction.title}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
