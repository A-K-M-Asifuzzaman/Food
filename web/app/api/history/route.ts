import { forwardAuth, relay, UPSTREAM } from "@/lib/upstream";

// A person's own record, scoped server-side to the uid in their token. There
// is no query parameter for whose history to fetch, deliberately: the only
// answer this route can give is "yours".
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: Request) {
  if (!UPSTREAM) {
    return Response.json({ error: "The model service is not connected." }, { status: 503 });
  }
  try {
    const res = await fetch(`${UPSTREAM}/history`, {
      cache: "no-store",
      headers: forwardAuth(request),
    });
    return relay(res, "History");
  } catch {
    return Response.json({ error: "Model service unreachable." }, { status: 503 });
  }
}

export async function DELETE(request: Request) {
  if (!UPSTREAM) {
    return Response.json({ error: "The model service is not connected." }, { status: 503 });
  }
  try {
    const res = await fetch(`${UPSTREAM}/history`, {
      method: "DELETE",
      headers: forwardAuth(request),
    });
    return relay(res, "History");
  } catch {
    return Response.json({ error: "Model service unreachable." }, { status: 503 });
  }
}
