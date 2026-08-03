import { NextResponse } from "next/server";

const UPSTREAM = process.env.FOODGENOME_API;

// Counters live in the model service's memory, so they are read on every
// request rather than cached. A stale operations dashboard is worse than a slow
// one: the whole point is seeing what is happening now.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  if (!UPSTREAM) {
    return NextResponse.json({ error: "The model service is not connected." }, { status: 503 });
  }
  try {
    const res = await fetch(`${UPSTREAM}/stats`, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: `Stats returned ${res.status}.` }, { status: 502 });
    }
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "Model service unreachable." }, { status: 503 });
  }
}
