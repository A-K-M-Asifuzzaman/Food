"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** What a signed-out visitor sees where the analyser would be.
 *
 *  Deliberately not a wall. It says what an account buys, states plainly what
 *  is stored, and carries the same one-tap Google route as the login page, so
 *  the whole detour is a single press for most people. The `next` parameter
 *  brings them straight back here rather than dropping them on the home page,
 *  which is the difference between a gate and an obstacle.
 */
export function SignInGate() {
  const pathname = usePathname();
  const href = `/login?next=${encodeURIComponent(pathname || "/analyze")}`;

  return (
    <div className="panel p-6 sm:p-10 text-center">
      {/* A web, spun across the empty frame. */}
      <svg viewBox="0 0 120 80" className="w-28 h-20 mx-auto" fill="none" aria-hidden="true">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <line
            key={i}
            x1="60"
            y1="4"
            x2={12 + i * 19.2}
            y2="74"
            stroke="var(--line)"
            strokeWidth="1.2"
            opacity="0.35"
          />
        ))}
        {[20, 38, 56].map((r) => (
          <path
            key={r}
            d={`M ${60 - r} ${4 + r * 1.1} Q 60 ${4 + r * 1.45} ${60 + r} ${4 + r * 1.1}`}
            stroke="var(--line)"
            strokeWidth="1.4"
            opacity="0.4"
          />
        ))}
        <circle cx="60" cy="4" r="4" fill="var(--color-red)" stroke="var(--line)" strokeWidth="1.6" />
      </svg>

      <h2 className="font-display text-2xl sm:text-3xl mt-4">SIGN IN TO ANALYSE</h2>
      <p className="mt-3 text-[var(--text-dim)] max-w-md mx-auto">
        Predictions are filed against an account, so yours stay yours. You get a running
        record of every dish you have analysed, the questions you asked about them, and the
        corrections you sent back.
      </p>

      <Link
        href={href}
        className="inline-block mt-6 ink-edge px-6 py-3 font-display text-lg uppercase tracking-wide"
        style={{ background: "var(--color-red)", color: "#f4f1e8" }}
      >
        Sign in
      </Link>

      <p className="mt-5 text-xs text-[var(--text-dim)] max-w-sm mx-auto">
        Your photograph is analysed and never stored. What is kept is the dish name, the
        confidence and the time — and you can delete all of it from your history page.
      </p>
    </div>
  );
}
