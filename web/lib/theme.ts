/** Day / night, as an external store the toggle can subscribe to. */

export type Theme = "light" | "dark";

export const THEME_KEY = "foodgenome-theme";

const listeners = new Set<() => void>();
const announce = () => listeners.forEach((listener) => listener());

let media: MediaQueryList | null = null;

/** Follows the system too, so an unset preference keeps mirroring it. */
export function subscribeTheme(listener: () => void): () => void {
  listeners.add(listener);
  if (listeners.size === 1) {
    media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", announce);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      media?.removeEventListener("change", announce);
      media = null;
    }
  };
}

function stored(): Theme | null {
  try {
    const value = window.localStorage.getItem(THEME_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    // Private browsing denies reads.
    return null;
  }
}

export function themeSnapshot(): Theme {
  return stored() ?? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}

/** The server cannot know; the toggle holds a blank until hydration settles it. */
export function serverThemeSnapshot(): Theme {
  return "light";
}

export function chooseTheme(next: Theme): void {
  document.documentElement.dataset.theme = next;
  try {
    window.localStorage.setItem(THEME_KEY, next);
  } catch {
    // Private browsing denies writes; the choice still applies for this page.
  }
  announce();
}
