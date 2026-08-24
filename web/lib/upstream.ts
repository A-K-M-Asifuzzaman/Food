/** Helpers shared by the API proxy routes. */

export const UPSTREAM = process.env.FOODGENOME_API;

/** The caller's Authorization header, if they sent one. */
export function forwardAuth(request: Request, extra: HeadersInit = {}): Headers {
  const headers = new Headers(extra);
  const auth = request.headers.get("authorization");
  if (auth) headers.set("Authorization", auth);
  return headers;
}

/** Turn an upstream response into a JSON response, preserving auth failures. */
export async function relay(res: Response, label: string) {
  if (res.status === 401 || res.status === 403) {
    const body = await res.json().catch(() => ({}));
    return Response.json(
      { error: body.detail ?? (res.status === 401 ? "Sign in first." : "Not permitted.") },
      { status: res.status },
    );
  }
  if (!res.ok) {
    return Response.json({ error: `${label} returned ${res.status}.` }, { status: 502 });
  }
  return Response.json(await res.json());
}
