/** Helpers shared by the API proxy routes. */

export const UPSTREAM = process.env.FOODGENOME_API;

/** The caller's Authorization header, if they sent one. */
export function forwardAuth(request: Request, extra: HeadersInit = {}): Headers {
  const headers = new Headers(extra);
  const auth = request.headers.get("authorization");
  if (auth) headers.set("Authorization", auth);
  return headers;
}

function fallbackMessage(status: number, label: string): string {
  if (status === 401) return "Sign in first.";
  if (status === 403) return "Not permitted.";
  if (status === 413) return "That upload is too large.";
  if (status === 415) return "That file could not be read as an image.";
  return `${label} rejected the request (${status}).`;
}

/** FastAPI puts its message in `detail`; validation errors put a list there instead. */
function detailOf(body: unknown): string | null {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown } | undefined;
    if (typeof first?.msg === "string") return first.msg;
  }
  return null;
}

/**
 * Turn an upstream response into a JSON response.
 *
 * A 4xx is about the request, so its status and the service's own wording pass straight
 * through — an expired login, an oversized image and an unknown food class each have to
 * stay distinguishable from an outage. Only a 5xx becomes a 502, because that genuinely
 * is this proxy reporting that the thing behind it broke.
 */
export async function relay(res: Response, label: string) {
  if (res.ok) {
    return Response.json(await res.json());
  }
  if (res.status < 500) {
    const body = await res.json().catch(() => null);
    return Response.json(
      { error: detailOf(body) ?? fallbackMessage(res.status, label) },
      { status: res.status },
    );
  }
  return Response.json({ error: `${label} returned ${res.status}.` }, { status: 502 });
}
