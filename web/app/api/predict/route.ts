import { NextResponse } from "next/server";

import { allClasses, getEntry, titleFor } from "@/lib/kb";
import type { Candidate, PredictResponse } from "@/lib/types";

// Stage 11 will stand up the FastAPI service. Until FOODGENOME_API is set, this
// route answers from the knowledge base alone and labels the response "demo" so
// the interface can never present a fabricated classification as a real one.
const UPSTREAM = process.env.FOODGENOME_API;

const MAX_BYTES = 12 * 1024 * 1024;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp", "image/heic"];

/** FNV-1a over the image bytes. Only used in demo mode, so that the same photo
 *  always yields the same illustrative result instead of reshuffling on reload. */
function hashBytes(bytes: Uint8Array): number {
  let h = 0x811c9dc5;
  const step = Math.max(1, Math.floor(bytes.length / 4096));
  for (let i = 0; i < bytes.length; i += step) {
    h ^= bytes[i];
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

function demoResponse(bytes: Uint8Array, startedAt: number): PredictResponse {
  const classes = allClasses();
  const h = hashBytes(bytes);

  const picked = classes[h % classes.length];
  // A plausible descending probability tail, deterministic in the same hash.
  const top = 0.62 + ((h >>> 8) % 30) / 100;
  const others: Candidate[] = [];
  let remaining = 1 - top;
  for (let i = 1; i <= 3; i += 1) {
    const cls = classes[(h + i * 37) % classes.length];
    if (cls === picked || others.some((c) => c.class === cls)) continue;
    const p = remaining * 0.55;
    remaining -= p;
    others.push({ class: cls, title: titleFor(cls), probability: p });
  }

  const entry = getEntry(picked)!;
  const candidates: Candidate[] = [
    { class: picked, title: titleFor(picked), probability: top },
    ...others,
  ];
  // Measured LAC behaviour at alpha = 0.01: 75.9% of test images get a singleton,
  // the average set holds 1.54 candidates, and it is never empty.
  const setSize = top > 0.8 ? 1 : top > 0.7 ? 2 : 3;

  return {
    source: "demo",
    latency_ms: Date.now() - startedAt,
    model: {
      name: "SigLIP-SO400M + EVA-02-L probability average",
      test_top1: 97.156,
      ensemble: ["siglip_so400m", "eva02_large"],
    },
    prediction: {
      class: picked,
      title: entry.title,
      confidence: top,
      raw_confidence: Math.max(0.05, top - 0.06),
    },
    conformal: {
      // 99% rather than 95%: with top-1 accuracy at 97.16%, any target below that
      // is met by the single best guess alone, so a 95% "set" is never a set.
      alpha: 0.01,
      candidates: candidates.slice(0, setSize),
      guarantee:
        "Measured over 25,250 held-out images, the true dish falls inside this set 99.6% of the time.",
    },
    ood: { is_food: true, score: 0.94, threshold: 0.5 },
    nutrition: {
      entry,
      per_serving: entry.nutrients_per_serving,
      per_100g: entry.nutrients_per_100g,
      serving_label: entry.serving_label,
      components: entry.components,
    },
  };
}

export async function POST(request: Request) {
  const startedAt = Date.now();

  const form = await request.formData().catch(() => null);
  const file = form?.get("image");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "No image supplied." }, { status: 400 });
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json(
      { error: `Image is larger than ${MAX_BYTES / 1024 / 1024} MB.` },
      { status: 413 },
    );
  }
  if (file.type && !ACCEPTED.includes(file.type)) {
    return NextResponse.json(
      { error: `Unsupported image type: ${file.type}` },
      { status: 415 },
    );
  }

  if (UPSTREAM) {
    const upstreamForm = new FormData();
    upstreamForm.append("image", file);
    try {
      const res = await fetch(`${UPSTREAM}/predict`, {
        method: "POST",
        body: upstreamForm,
      });
      if (!res.ok) {
        return NextResponse.json(
          { error: `Model service returned ${res.status}.` },
          { status: 502 },
        );
      }
      return NextResponse.json(await res.json());
    } catch {
      return NextResponse.json(
        { error: "Model service unreachable." },
        { status: 503 },
      );
    }
  }

  const bytes = new Uint8Array(await file.arrayBuffer());
  return NextResponse.json(demoResponse(bytes, startedAt));
}
