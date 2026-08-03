"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "./AuthProvider";

/** Who is allowed to see the console.
 *
 *  This check is for the interface. It is not the security boundary and must
 *  not be mistaken for one: every endpoint behind this page checks the same
 *  admin list against a token verified with Google's public keys, and returns
 *  403 to anyone else regardless of what the browser decided to render. Someone
 *  editing this component in their devtools gets a dashboard full of error
 *  messages, which is the correct outcome.
 */
export function AdminGate({ children }: { children: React.ReactNode }) {
  const { user, loading, isAdmin } = useAuth();
  const pathname = usePathname();

  if (loading) {
    return <p className="text-sm text-[var(--text-dim)]">Checking your session…</p>;
  }

  if (!user) {
    return (
      <div className="panel p-6 max-w-lg">
        <h2 className="font-display text-xl">Sign in required</h2>
        <p className="mt-2 text-sm text-[var(--text-dim)]">
          The console shows live traffic, per-account usage and spend, none of which is
          public.
        </p>
        <Link
          href={`/login?next=${encodeURIComponent(pathname || "/admin")}`}
          className="inline-block mt-4 ink-edge px-4 py-2 font-display uppercase tracking-wide"
          style={{ background: "var(--color-red)", color: "#f4f1e8" }}
        >
          Sign in
        </Link>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="panel p-6 max-w-lg">
        <h2 className="font-display text-xl">Not your console</h2>
        <p className="mt-2 text-sm text-[var(--text-dim)]">
          You are signed in as {user.email}, which is not on the operator list. Your own
          record is on the history page.
        </p>
        <div className="mt-4 flex gap-3 flex-wrap">
          <Link
            href="/history"
            className="ink-edge px-4 py-2 font-display uppercase tracking-wide"
            style={{ background: "var(--color-red)", color: "#f4f1e8" }}
          >
            My predictions
          </Link>
          <Link href="/" className="ink-edge px-4 py-2 font-display uppercase tracking-wide">
            Public site
          </Link>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
