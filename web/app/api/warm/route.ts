import { NextResponse } from "next/server";

const UPSTREAM = process.env.FOODGENOME_API;

export const dynamic = "force-dynamic";

/** Readiness, and a nudge to start loading. */
export async function GET() {
  if (!UPSTREAM) return NextResponse.json({ status: "demo" });
  try {
    const res = await fetch(`${UPSTREAM}/health`, { cache: "no-store" });
    if (!res.ok) return NextResponse.json({ status: "unreachable" }, { status: 502 });
    const health = await res.json();
    return NextResponse.json({
      status: health.model_loaded ? "ready" : "cold",
      uptime: health.uptime_seconds ?? null,
    });
  } catch {
    return NextResponse.json({ status: "unreachable" }, { status: 503 });
  }
}

export async function POST() {
  if (!UPSTREAM) return NextResponse.json({ status: "demo" });
  try {
    // The Space may be asleep; waking it is exactly what this call is for, so a long
    // timeout here is correct rather than a hang.
    const res = await fetch(`${UPSTREAM}/warm`, {
      method: "POST",
      signal: AbortSignal.timeout(120_000),
    });
    return NextResponse.json(res.ok ? await res.json() : { status: "unreachable" });
  } catch {
    return NextResponse.json({ status: "unreachable" });
  }
}
