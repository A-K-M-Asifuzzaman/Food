import type { ReactNode } from "react";

/** The comic print kit.
 *
 *  These wrap the CSS in `comic.css` so a page composes panels rather than
 *  remembering class strings, and so the print rules stay in one place when the
 *  language is extended.
 */

/** Display type with plate misregistration.
 *
 *  The cyan and magenta layers are `aria-hidden` duplicates: a screen reader
 *  must hear the word once, not three times. They are also the reason this is a
 *  component — hand-writing three stacked spans per heading is how the offset
 *  ends up inconsistent across a site.
 */
export function InkSplit({
  children,
  className = "",
}: {
  children: string;
  className?: string;
}) {
  return <span className={`ink-split ${className}`}>{children}</span>;
}

type PanelProps = {
  children: ReactNode;
  className?: string;
  tilt?: "left" | "right" | "none";
  raised?: boolean;
  web?: boolean;
  as?: "div" | "section" | "article" | "aside";
};

export function Panel({
  children,
  className = "",
  tilt = "none",
  raised = false,
  web = false,
  as: Tag = "div",
}: PanelProps) {
  const tilts = { left: "panel-tilt-l", right: "panel-tilt-r", none: "" };
  return (
    <Tag
      className={[
        raised ? "panel-raised" : "panel",
        tilts[tilt],
        web ? "web-corner" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </Tag>
  );
}

/** The yellow narration box. Reserved for methodology asides — the voice that
 *  explains rather than the voice that reports. Overusing it would flatten that
 *  distinction, so it is deliberately not a general-purpose callout. */
export function Caption({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <aside className={`caption-box px-4 py-3 text-sm ${className}`}>{children}</aside>
  );
}

export function Sfx({
  children,
  className = "",
}: {
  children: string;
  className?: string;
}) {
  return <span className={`sfx-burst ${className}`}>{children}</span>;
}

export function GutterRule({ className = "" }: { className?: string }) {
  return <div className={`gutter-rule ${className}`} aria-hidden="true" />;
}

/** Section heading with a panel number, the way a comic page numbers its beats. */
export function Beat({
  n,
  title,
  lede,
}: {
  n: string;
  title: string;
  lede?: string;
}) {
  return (
    <div className="speed-lines">
      <p className="figures text-sm" style={{ color: "var(--color-red)" }}>
        {n}
      </p>
      <h2 className="font-display text-3xl sm:text-4xl leading-none mt-1">
        <InkSplit>{title}</InkSplit>
      </h2>
      {lede && <p className="mt-3 max-w-prose text-[var(--text-dim)]">{lede}</p>}
    </div>
  );
}

/** A statistic rendered as a panel. Figures are the product, so they get the
 *  mono face with tabular figures and the largest type on the card. */
export function StatPanel({
  value,
  label,
  note,
  accent = "var(--color-red)",
  tilt = "none",
}: {
  value: string;
  label: string;
  note?: string;
  accent?: string;
  tilt?: "left" | "right" | "none";
}) {
  return (
    <Panel tilt={tilt} className="p-5 halftone-shade">
      <p className="figures text-3xl sm:text-4xl leading-none" style={{ color: accent }}>
        {value}
      </p>
      <p className="font-display text-sm uppercase tracking-wide mt-2">{label}</p>
      {note && <p className="text-xs text-[var(--text-dim)] mt-1">{note}</p>}
    </Panel>
  );
}
