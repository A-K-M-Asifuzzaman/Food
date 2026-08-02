"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import type { SearchItem } from "@/lib/search";

import { CommandPalette } from "./CommandPalette";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { href: "/analyze", label: "Analyse" },
  { href: "/dishes", label: "Dishes" },
  { href: "/explore", label: "The web" },
  { href: "/benchmarks", label: "Benchmarks" },
  { href: "/methods", label: "Method" },
];

export function SiteHeader({ searchIndex }: { searchIndex: SearchItem[] }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    pathname === href || (href !== "/" && pathname.startsWith(href));

  return (
    <header className="sticky top-0 z-50 border-b-3 border-[var(--line)] bg-[var(--page)]">
      <div className="mx-auto max-w-6xl px-5 py-3 flex items-center justify-between gap-4">
        <Link href="/" className="font-display text-xl tracking-tight shrink-0">
          FOODGENOME<span style={{ color: "var(--color-red)" }}>·</span>AI
        </Link>

        <div className="flex items-center gap-3">
          <CommandPalette index={searchIndex} />
          <ThemeToggle />
        </div>

        <nav className="hidden md:flex items-center gap-1" aria-label="Main">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(item.href) ? "page" : undefined}
              className="px-3 py-1.5 text-sm uppercase tracking-widest border-2 border-transparent"
              style={
                isActive(item.href)
                  ? {
                      borderColor: "var(--line)",
                      background: "var(--color-red)",
                      color: "#f4f1e8",
                    }
                  : undefined
              }
            >
              {item.label}
            </Link>
          ))}
          <Link
            href="/admin"
            className="ml-2 px-3 py-1.5 text-sm uppercase tracking-widest ink-edge"
            style={{ background: "var(--color-blue)", color: "#f4f1e8" }}
          >
            Admin
          </Link>
        </nav>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="md:hidden ink-edge px-3 py-1.5 text-sm font-display uppercase"
          aria-expanded={open}
          aria-controls="mobile-nav"
        >
          {open ? "Close" : "Menu"}
        </button>
      </div>

      {open && (
        <nav
          id="mobile-nav"
          className="md:hidden border-t-2 border-[var(--line)] px-5 py-3 flex flex-col gap-1"
          aria-label="Main"
        >
          {[...NAV, { href: "/admin", label: "Admin" }].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className="py-2 uppercase tracking-widest text-sm"
              style={isActive(item.href) ? { color: "var(--color-red)" } : undefined}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
