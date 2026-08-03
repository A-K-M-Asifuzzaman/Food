import type { Metadata } from "next";
import Link from "next/link";

import { AdminGate } from "../components/AdminGate";
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
 *  Restricted to the operator accounts in ADMIN_EMAILS. The gate here is
 *  presentation; the endpoints behind it check the same list against a verified
 *  ID token, so editing this component in devtools buys a page of 403s.
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
              style={{ background: "var(--color-blue)", color: "#f4f1e8" }}
            >
              operators only
            </span>
          </div>
          <Link href="/" className="text-sm uppercase tracking-widest hover:underline">
            ← Public site
          </Link>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-5 py-6 grid gap-6 lg:grid-cols-[13rem_1fr]">
        <AdminNav />
        <div className="min-w-0">
          <AdminGate>{children}</AdminGate>
        </div>
      </div>
    </div>
  );
}
