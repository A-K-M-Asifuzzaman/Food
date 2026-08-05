"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import type { SearchItem } from "@/lib/search";

import { CommandPalette } from "./CommandPalette";
import { SoundToggle } from "./SoundToggle";
import { ThemeToggle } from "./ThemeToggle";
import { useAuth } from "./AuthProvider";
import { UserMenu } from "./UserMenu";

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
  const { isAdmin } = useAuth();

  const isActive = (href: string) =>
    pathname === href || (href !== "/" && pathname.startsWith(href));

  return (
    <header className="sticky top-0 z-50 border-b-3 border-[var(--line)] bg-[var(--page)]">
      <div className="mx-auto max-w-6xl px-5 py-3 flex items-center justify-between gap-4">
        <Link href="/" className="font-display text-xl tracking-tight shrink-0 py-1.5">
          FOODGENOME<span style={{ color: "var(--color-red)" }}>·</span>AI
        </Link>

        <div className="flex items-center gap-3">
          <CommandPalette index={searchIndex} />
          <SoundToggle />
          <ThemeToggle />
        </div>

        <nav className="hidden lg:flex items-center gap-1" aria-label="Main">
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
          {isAdmin && (
            <Link
              href="/admin"
              className="ml-2 px-3 py-1.5 text-sm uppercase tracking-widest ink-edge"
              style={{ background: "var(--color-blue)", color: "#f4f1e8" }}
            >
              Admin
            </Link>
          )}
          <span className="ml-2">
            <UserMenu compact />
          </span>
        </nav>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="lg:hidden ink-edge px-4 py-2 text-sm font-display uppercase"
          aria-expanded={open}
          aria-controls="mobile-nav"
        >
          {open ? "Close" : "Menu"}
        </button>
      </div>

      {open && (
        <nav
          id="mobile-nav"
          className="lg:hidden border-t-2 border-[var(--line)] px-5 py-2 flex flex-col"
          aria-label="Main"
        >
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className="py-3 uppercase tracking-widest text-sm"
              style={isActive(item.href) ? { color: "var(--color-red)" } : undefined}
            >
              {item.label}
            </Link>
          ))}

          {/* The account and its pages, kept apart from the site's sections.
              "My predictions" is not a place on the site — it is a view of your
              own record, and listing it beside Dishes and Benchmarks implies it
              belongs to everyone. */}
          <AccountSection onNavigate={() => setOpen(false)} />
        </nav>
      )}
    </header>
  );
}

/** The account block at the foot of the mobile menu.
 *
 *  On a phone there is no room for a dropdown that has to be opened before it
 *  can be read, so the menu shows the whole thing at once: who you are, then
 *  the pages that belong to you, indented under it.
 */
function AccountSection({ onNavigate }: { onNavigate: () => void }) {
  const { user, loading, isAdmin, signOut } = useAuth();

  if (loading) return null;

  if (!user) {
    return (
      <div className="mt-2 pt-3 border-t-2 border-[var(--line)]/25">
        <Link
          href="/login"
          onClick={onNavigate}
          className="block text-center ink-edge px-4 py-3 font-display uppercase tracking-wide"
          style={{ background: "var(--color-red)", color: "#f4f1e8" }}
        >
          Sign in
        </Link>
      </div>
    );
  }

  const label = user.displayName || user.email || "Account";

  return (
    <div className="mt-2 pt-3 pb-1 border-t-2 border-[var(--line)]/25">
      <div className="flex items-center gap-2">
        <span
          className="w-7 h-7 grid place-items-center font-display text-sm shrink-0"
          style={{ background: "var(--color-red)", color: "#f4f1e8" }}
          aria-hidden="true"
        >
          {label.trim().charAt(0).toUpperCase()}
        </span>
        <span className="min-w-0">
          <span className="block text-sm truncate">{label}</span>
          {user.email && user.email !== label && (
            <span className="block text-xs text-[var(--text-dim)] truncate">{user.email}</span>
          )}
        </span>
        {isAdmin && (
          <span
            className="ml-auto ink-edge px-1.5 py-0.5 text-[10px] uppercase tracking-widest shrink-0"
            style={{ background: "var(--color-blue)", color: "#f4f1e8" }}
          >
            admin
          </span>
        )}
      </div>

      <div className="mt-1 pl-9 flex flex-col">
        <Link
          href="/history"
          onClick={onNavigate}
          className="py-2.5 text-sm uppercase tracking-widest"
        >
          My predictions
        </Link>
        {isAdmin && (
          <Link
            href="/admin"
            onClick={onNavigate}
            className="py-2.5 text-sm uppercase tracking-widest"
          >
            Admin console
          </Link>
        )}
        <button
          type="button"
          onClick={() => {
            onNavigate();
            void signOut();
          }}
          className="py-2.5 text-sm uppercase tracking-widest text-left"
          style={{ color: "var(--color-red)" }}
        >
          Sign out
        </button>
      </div>
    </div>
  );
}
