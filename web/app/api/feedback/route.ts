import { NextResponse } from "next/server";

import { forwardAuth, relay, UPSTREAM } from "@/lib/upstream";

export async function POST(request: Request) {
  if (!UPSTREAM) {
    return NextResponse.json({ error: "Not connected." }, { status: 503 });
  }
  const body = await request.json().catch(() => null);
  if (!body?.food_class || typeof body.helpful !== "boolean") {
    return NextResponse.json({ error: "Malformed feedback." }, { status: 400 });
  }
  try {
    const res = await fetch(`${UPSTREAM}/feedback`, {
      method: "POST",
      headers: forwardAuth(request, { "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    return relay(res, "Feedback");
  } catch {
    return NextResponse.json({ error: "Model service unreachable." }, { status: 503 });
  }
}
