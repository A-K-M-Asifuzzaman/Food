"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

/** Day / night as a spider on a strand. */

export const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem('foodgenome-theme');
    if (stored === 'light' || stored === 'dark') {
      document.documentElement.dataset.theme = stored;
    }
  } catch (e) {}
})();
`;

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("foodgenome-theme");
    if (stored === "light" || stored === "dark") {
      setTheme(stored);
      return;
    }
    // No explicit choice: mirror the system, and keep mirroring it.
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setTheme(mq.matches ? "dark" : "light");
    const onChange = (e: MediaQueryListEvent) => {
      if (!localStorage.getItem("foodgenome-theme")) setTheme(e.matches ? "dark" : "light");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  function choose(next: Theme) {
    setTheme(next);
    document.documentElement.dataset.theme = next;
    localStorage.setItem("foodgenome-theme", next);
  }

  // Render nothing until the client knows which state to show.
  if (theme === null) {
    return <div className="w-[4.25rem] h-8 shrink-0" aria-hidden="true" />;
  }

  const dark = theme === "dark";

  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label={`Switch to ${dark ? "light" : "dark"} theme`}
      title={`Switch to ${dark ? "light" : "dark"} theme`}
      onClick={() => choose(dark ? "light" : "dark")}
      className="theme-toggle relative w-[4.25rem] h-8 shrink-0 ink-edge overflow-hidden"
      style={{ background: dark ? "var(--color-blue-deep)" : "var(--color-amber)" }}
    >
      {/* The strand the spider travels along. */}
      <svg
        viewBox="0 0 68 32"
        className="absolute inset-0 w-full h-full pointer-events-none"
        aria-hidden="true"
      >
        <path
          d="M4 16 Q34 22 64 16"
          fill="none"
          stroke="var(--line)"
          strokeWidth="1.4"
          opacity="0.5"
        />
        {/* Sun on the light end, moon on the night end. */}
        <circle cx="13" cy="16" r="4" fill="var(--line)" opacity={dark ? 0.28 : 0.9} />
        <path
          d="M55 11.5a5.2 5.2 0 1 0 4.6 7.7A6 6 0 0 1 55 11.5Z"
          fill="var(--line)"
          opacity={dark ? 0.95 : 0.28}
        />
      </svg>

      {/* The spider. Eight legs, drawn rather than emoji so it inherits the ink
          colour and stays crisp at any zoom. */}
      <span
        className="theme-knob absolute top-1/2 grid place-items-center"
        style={{
          left: dark ? "calc(100% - 1.6rem)" : "0.55rem",
          width: "1.05rem",
          height: "1.05rem",
          transform: "translate(-50%, -50%)",
        }}
      >
        <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true">
          <g
            stroke={dark ? "#f4f1e8" : "#0b0b0f"}
            strokeWidth="1.7"
            strokeLinecap="round"
            fill="none"
          >
            <path d="M9 7 4 3M15 7l5-4M8 11 2 9M16 11l6-2M8 15l-6 3M16 15l6 3M9.5 18 6 22M14.5 18l3.5 4" />
          </g>
          <ellipse cx="12" cy="12.5" rx="4.3" ry="5" fill={dark ? "#f4f1e8" : "#0b0b0f"} />
          <circle cx="12" cy="7.6" r="2.4" fill={dark ? "#f4f1e8" : "#0b0b0f"} />
        </svg>
      </span>
    </button>
  );
}
