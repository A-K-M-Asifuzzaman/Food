import { NextResponse } from "next/server";

import { forwardAuth, relay, UPSTREAM } from "@/lib/upstream";

// Grounded answers require the model service.

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
    return relay(res, "Answer service");
  } catch {
    return NextResponse.json({ error: "Answer service unreachable." }, { status: 503 });
  }
}
