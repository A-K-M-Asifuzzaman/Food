/** An anonymous, browser-generated visitor id.
 *
 *  There is no account system here and no server-side identity. This id is
 *  created in the browser, kept in localStorage, and sent as an `X-Session-Id`
 *  header so a visitor can see their own history and the admin console can
 *  count distinct sessions rather than raw requests.
 *
 *  It carries no personal data, it is not derived from anything about the
 *  device, and clearing site data ends it permanently — which the history page
 *  says, with a button that does exactly that.
 */

const KEY = "foodgenome.session";

export function sessionId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem(KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(KEY, id);
  }
  return id;
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY);
}

/** Headers to attach to any request that should be attributed to this visitor. */
export function sessionHeaders(): Record<string, string> {
  const id = sessionId();
  return id ? { "X-Session-Id": id } : {};
}
