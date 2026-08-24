"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { search, type SearchItem } from "@/lib/search";

/** ⌘K navigation over every page and all 101 dishes. */

const KIND_LABEL: Record<SearchItem["kind"], string> = {
  page: "Page",
  dish: "Dish",
  action: "Action",
};

const KIND_COLOUR: Record<SearchItem["kind"], string> = {
  page: "var(--color-blue)",
  dish: "var(--color-red)",
  action: "var(--color-amber)",
};

export function CommandPalette({ index }: { index: SearchItem[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const opener = useRef<HTMLElement | null>(null);

  const results = useMemo(() => search(index, query), [index, query]);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setCursor(0);
    opener.current?.focus();
  }, []);

  const go = useCallback(
    (item: SearchItem) => {
      close();
      router.push(item.href);
    },
    [close, router],
  );

  // Global shortcut.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        opener.current = document.activeElement as HTMLElement;
        setOpen((v) => !v);
      }
      if (e.key === "Escape" && open) close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 20);
      return () => clearTimeout(t);
    }
  }, [open]);

  useEffect(() => setCursor(0), [query]);

  useEffect(() => {
    listRef.current?.children[cursor]?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  if (!open) {
    return (
      <button
        type="button"
        onClick={(e) => {
          opener.current = e.currentTarget;
          setOpen(true);
        }}
        className="hidden lg:flex items-center gap-2 ink-edge px-3 py-1.5 text-sm text-[var(--text-dim)]"
        aria-label="Open the command palette"
      >
        <span>Search…</span>
        <kbd className="figures text-xs px-1.5 py-0.5 ink-edge">⌘K</kbd>
      </button>
    );
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[12vh] px-4"
      style={{ background: "rgba(11,11,15,0.55)" }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search FoodGenome AI"
        className="panel-raised w-full max-w-xl overflow-hidden animate-snap"
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b-3 border-[var(--line)]">
          <span aria-hidden="true" style={{ color: "var(--color-red)" }}>
            ▸
          </span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setCursor((c) => (c + 1) % Math.max(1, results.length));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setCursor((c) => (c - 1 + results.length) % Math.max(1, results.length));
              } else if (e.key === "Enter" && results[cursor]) {
                e.preventDefault();
                go(results[cursor]);
              }
            }}
            placeholder="Search dishes and pages…"
            className="flex-1 bg-transparent outline-none text-lg min-w-0"
            aria-controls="palette-results"
            aria-activedescendant={results[cursor] ? `palette-${results[cursor].id}` : undefined}
          />
          <kbd className="figures text-xs px-1.5 py-0.5 ink-edge shrink-0">esc</kbd>
        </div>

        {results.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-[var(--text-dim)]">
            Nothing matches “{query}”. The knowledge base covers 101 dish categories.
          </p>
        ) : (
          <ul id="palette-results" ref={listRef} role="listbox" className="max-h-80 overflow-y-auto">
            {results.map((item, i) => (
              <li
                key={item.id}
                id={`palette-${item.id}`}
                role="option"
                aria-selected={i === cursor}
              >
                <button
                  type="button"
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => go(item)}
                  className="w-full text-left px-4 py-2.5 flex items-center gap-3"
                  style={{
                    background: i === cursor ? "var(--color-amber)" : undefined,
                    color: i === cursor ? "#0b0b0f" : undefined,
                  }}
                >
                  <span
                    className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 ink-edge shrink-0"
                    style={{ background: KIND_COLOUR[item.kind], color: "#f4f1e8" }}
                  >
                    {KIND_LABEL[item.kind]}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block truncate">{item.label}</span>
                    {item.sub && (
                      <span
                        className="block text-xs truncate"
                        style={{ color: i === cursor ? "#0b0b0f" : "var(--text-dim)" }}
                      >
                        {item.sub}
                      </span>
                    )}
                  </span>
                  {i === cursor && <span className="figures text-xs shrink-0">↵</span>}
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="flex items-center gap-4 px-4 py-2 border-t-2 border-[var(--line)] text-xs text-[var(--text-dim)]">
          <span>
            <kbd className="figures">↑↓</kbd> navigate
          </span>
          <span>
            <kbd className="figures">↵</kbd> open
          </span>
          <span className="ml-auto figures">{results.length} results</span>
        </div>
      </div>
    </div>
  );
}
