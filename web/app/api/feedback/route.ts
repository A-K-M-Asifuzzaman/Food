import { NextResponse } from "next/server";

const UPSTREAM = process.env.FOODGENOME_API;

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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return NextResponse.json(res.ok ? await res.json() : { error: "rejected" },
                             { status: res.ok ? 200 : 502 });
  } catch {
    return NextResponse.json({ error: "Model service unreachable." }, { status: 503 });
  }
}
