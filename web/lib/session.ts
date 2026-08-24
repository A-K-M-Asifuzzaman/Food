/** An anonymous, browser-generated visitor id. */

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
