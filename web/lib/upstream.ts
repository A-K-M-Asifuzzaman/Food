/** Helpers shared by the API proxy routes.
 *
 *  Every route in `app/api` forwards to the model service, and every one of
 *  them has to carry the caller's Firebase ID token through. Doing that inline
 *  five times is how one route quietly ends up not doing it — and a route that
 *  drops the token does not fail loudly, it just files the prediction against
 *  nobody.
 */

export const UPSTREAM = process.env.FOODGENOME_API;

/** The caller's Authorization header, if they sent one.
 *
 *  Passed through untouched. This proxy deliberately does not verify the token
 *  itself: verification needs the Admin SDK and a service-account key, and that
 *  key belongs on the model service alone, not in a Vercel deployment that only
 *  needs to relay bytes.
 */
export function forwardAuth(request: Request, extra: HeadersInit = {}): Headers {
  const headers = new Headers(extra);
  const auth = request.headers.get("authorization");
  if (auth) headers.set("Authorization", auth);
  return headers;
}

/** Turn an upstream response into a JSON response, preserving auth failures.
 *
 *  401 and 403 must reach the browser as themselves. Collapsing them into 502
 *  would turn "sign in" and "you are not an admin" into "the server is broken",
 *  and the interface would have no way to tell a user what to do about it.
 */
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
