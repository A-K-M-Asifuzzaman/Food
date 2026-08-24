"use client";

import { useEffect, useId, useRef, useState } from "react";

/** A mermaid diagram, themed to match the page it sits on. */
export function Mermaid({ chart, className = "" }: { chart: string; className?: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState("");
  const [failed, setFailed] = useState(false);
  // Mermaid ids must be unique per render or two diagrams collide in the DOM.
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");

  useEffect(() => {
    let alive = true;

    const render = async () => {
      const mermaid = (await import("mermaid")).default;
      const css = getComputedStyle(document.documentElement);
      const v = (name: string, fallback: string) =>
        css.getPropertyValue(name).trim() || fallback;

      const ink = v("--line", "#0b0b0f");
      const panel = v("--panel", "#ffffff");
      const text = v("--text", "#0b0b0f");
      const red = v("--color-red", "#e62429");
      const blue = v("--color-blue", "#1b4ce0");

      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        fontFamily: "var(--font-sans), ui-sans-serif, system-ui",
        themeVariables: {
          background: "transparent",
          primaryColor: panel,
          primaryTextColor: text,
          primaryBorderColor: ink,
          secondaryColor: panel,
          tertiaryColor: panel,
          lineColor: ink,
          textColor: text,
          mainBkg: panel,
          nodeBorder: ink,
          clusterBkg: "transparent",
          clusterBorder: ink,
          edgeLabelBackground: panel,
          fontSize: "14px",
        },
        flowchart: { curve: "linear", padding: 14, nodeSpacing: 42, rankSpacing: 46 },
      });

      try {
        const { svg } = await mermaid.render(`m${id}`, chart);
        if (alive) setSvg(svg);
      } catch {
        // A malformed diagram must not blank the page around it.
        if (alive) setFailed(true);
      }
    };

    void render();

    // Re-render on theme change: the colours are baked into the SVG at render time, so
    // a diagram drawn in light mode stays light until it is redrawn.
    const observer = new MutationObserver(() => void render());
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    const scheme = window.matchMedia("(prefers-color-scheme: dark)");
    const onScheme = () => void render();
    scheme.addEventListener("change", onScheme);

    return () => {
      alive = false;
      observer.disconnect();
      scheme.removeEventListener("change", onScheme);
    };
  }, [chart, id]);

  if (failed) {
    return (
      <pre className="text-xs overflow-x-auto p-3 border-2 border-[var(--line)]">{chart}</pre>
    );
  }

  return (
    <div
      ref={host}
      className={`mermaid-host overflow-x-auto ${className}`}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
