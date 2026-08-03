import { forwardAuth, relay, UPSTREAM } from "@/lib/upstream";

// Aggregates across every account. Admin-only, checked upstream against a
// verified token — this route relays, it does not decide.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: Request) {
  if (!UPSTREAM) {
    return Response.json({ error: "The model service is not connected." }, { status: 503 });
  }
  const days = new URL(request.url).searchParams.get("days") ?? "14";
  try {
    const res = await fetch(`${UPSTREAM}/analytics?days=${encodeURIComponent(days)}`, {
      cache: "no-store",
      headers: forwardAuth(request),
    });
    return relay(res, "Analytics");
  } catch {
    return Response.json({ error: "Model service unreachable." }, { status: 503 });
  }
}
