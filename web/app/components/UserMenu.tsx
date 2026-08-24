"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "./AuthProvider";

/** The signed-in account, or the way in. */
export function UserMenu({ compact = false }: { compact?: boolean }) {
  const { user, loading, isAdmin, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const menu = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!menu.current?.contains(e.target as Node)) setOpen(false);
    };
    const escape = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  // Reserve the space rather than collapsing it, so the header does not jump when
  // Firebase finishes restoring the session a beat after first paint.
  if (loading) return <span className="w-20 h-8" aria-hidden="true" />;

  if (!user) {
    return (
      <Link
        href="/login"
        className={`ink-edge font-display uppercase tracking-wide ${
          compact ? "px-3 py-1.5 text-sm" : "px-4 py-2"
        }`}
        style={{ background: "var(--color-red)", color: "#f4f1e8" }}
      >
        Sign in
      </Link>
    );
  }

  const label = user.displayName || user.email || "Account";
  const initial = label.trim().charAt(0).toUpperCase();

  return (
    <div className="relative" ref={menu}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 ink-edge px-2 py-1.5"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <span
          className="w-6 h-6 grid place-items-center font-display text-sm shrink-0"
          style={{ background: "var(--color-red)", color: "#f4f1e8" }}
          aria-hidden="true"
        >
          {initial}
        </span>
        <span className="text-sm max-w-[9rem] truncate hidden sm:block">{label}</span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-60 panel p-2 z-50"
          style={{ background: "var(--panel)" }}
        >
          <p className="px-2 py-1.5 text-xs text-[var(--text-dim)] truncate">{user.email}</p>
          {isAdmin && (
            <p className="px-2 pb-1.5">
              <span
                className="ink-edge px-1.5 py-0.5 text-[10px] uppercase tracking-widest"
                style={{ background: "var(--color-blue)", color: "#f4f1e8" }}
              >
                admin
              </span>
            </p>
          )}
          <Link
            href="/history"
            onClick={() => setOpen(false)}
            role="menuitem"
            className="block px-2 py-2 text-sm hover:underline"
          >
            My predictions
          </Link>
          {isAdmin && (
            <Link
              href="/admin"
              onClick={() => setOpen(false)}
              role="menuitem"
              className="block px-2 py-2 text-sm hover:underline"
            >
              Admin console
            </Link>
          )}
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              void signOut();
            }}
            className="w-full text-left px-2 py-2 text-sm hover:underline"
            style={{ color: "var(--color-red)" }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
