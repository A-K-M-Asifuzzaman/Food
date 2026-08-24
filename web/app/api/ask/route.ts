import { NextResponse } from "next/server";

import { forwardAuth } from "@/lib/upstream";

// Grounded answers require the model service.
const UPSTREAM = process.env.FOODGENOME_API;

export async function POST(request: Request) {
  if (!UPSTREAM) {
    return NextResponse.json(
      {
        error:
          "The answer service is not connected. Questions are answered only from the USDA knowledge base, never generated without it.",
      },
      { status: 503 },
    );
  }

  const body = await request.json().catch(() => null);
  const question = typeof body?.question === "string" ? body.question.trim() : "";

  if (question.length < 2) {
    return NextResponse.json({ error: "Ask a question first." }, { status: 400 });
  }
  if (question.length > 400) {
    return NextResponse.json({ error: "That question is too long." }, { status: 413 });
  }

  try {
    const res = await fetch(`${UPSTREAM}/ask`, {
      method: "POST",
      headers: forwardAuth(request, { "Content-Type": "application/json" }),
      body: JSON.stringify({ question, food_class: body?.food_class ?? null }),
    });
    if (!res.ok) {
      return NextResponse.json(
        { error: `Answer service returned ${res.status}.` },
        { status: 502 },
      );
    }
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "Answer service unreachable." }, { status: 503 });
  }
}
