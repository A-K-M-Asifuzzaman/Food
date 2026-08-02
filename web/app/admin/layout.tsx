import type { Metadata } from "next";
import Link from "next/link";

import { AdminNav } from "../components/AdminNav";

export const metadata: Metadata = {
  title: "Admin console — FoodGenome AI",
  robots: { index: false, follow: false },
};

/** The operator surface.
 *
 *  Deliberately plainer than the public site: an operator reads numbers under
 *  time pressure, and the print flourishes that make a landing page memorable
 *  make a dashboard slower to scan. Same tokens, less ink.
 *
 *  Not authenticated yet. Everything it shows is already public on /benchmarks,
 *  so nothing is leaked today — but the live prediction feed and cost data in
 *  section 3.1 are not public, and the gate has to exist before those land.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex-1 w-full">
      <div className="border-b-3 border-[var(--line)] bg-[var(--panel)]">
        <div className="mx-auto max-w-7xl px-5 py-3 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-baseline gap-3">
            <span className="font-display text-lg">ADMIN CONSOLE</span>
            <span
              className="text-[10px] uppercase tracking-widest px-2 py-0.5 ink-edge"
              style={{ background: "var(--color-amber)", color: "#0b0b0f" }}
            >
              unauthenticated · pre-launch
            </span>
          </div>
          <Link href="/" className="text-sm uppercase tracking-widest hover:underline">
            ← Public site
          </Link>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-5 py-6 grid gap-6 lg:grid-cols-[13rem_1fr]">
        <AdminNav />
        <div className="min-w-0">{children}</div>
      </div>
    </div>
  );
}
