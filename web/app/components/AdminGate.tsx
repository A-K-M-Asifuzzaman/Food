"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "./AuthProvider";
import { SpiderBar } from "./SpiderBar";

/** Who is allowed to see the console. */
export function AdminGate({ children }: { children: React.ReactNode }) {
  const { user, loading, isAdmin } = useAuth();
  const pathname = usePathname();

  if (loading) {
    return <SpiderBar label="Checking your session" />;
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
