import { NextResponse } from "next/server";

import { forwardAuth, relay } from "@/lib/upstream";

const UPSTREAM = process.env.FOODGENOME_API;

// Counters live in the model service's memory, so they are read on every request rather
// than cached.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: Request) {
  if (!UPSTREAM) {
    return NextResponse.json({ error: "The model service is not connected." }, { status: 503 });
  }
  try {
    const res = await fetch(`${UPSTREAM}/stats`, {
      cache: "no-store",
      headers: forwardAuth(request),
    });
    return relay(res, "Stats");
  } catch {
    return NextResponse.json({ error: "Model service unreachable." }, { status: 503 });
  }
}
