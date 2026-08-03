import { NextResponse } from "next/server";

import { forwardAuth } from "@/lib/upstream";

const UPSTREAM = process.env.FOODGENOME_API;

export async function POST(request: Request) {
  if (!UPSTREAM) {
    return NextResponse.json(
      { error: "The model service is not connected, so there is no model to explain." },
      { status: 503 },
    );
  }

  const form = await request.formData().catch(() => null);
  const file = form?.get("image");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "No image supplied." }, { status: 400 });
  }

  const upstreamForm = new FormData();
  upstreamForm.append("image", file);

  const foodClass = form?.get("food_class");
  const query =
    typeof foodClass === "string" && foodClass
      ? `?food_class=${encodeURIComponent(foodClass)}`
      : "";

  try {
    const res = await fetch(`${UPSTREAM}/explain${query}`, {
      method: "POST",
      headers: forwardAuth(request),
      body: upstreamForm,
    });
    if (!res.ok) {
      return NextResponse.json(
        { error: `Explain service returned ${res.status}.` },
        { status: 502 },
      );
    }
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "Explain service unreachable." }, { status: 503 });
  }
}
