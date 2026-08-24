"use client";

import { usePathname } from "next/navigation";

import { SpiderWebBackground } from "./SpiderWebBackground";

/** The web, behind every page. */

const QUIET = ["/analyze", "/admin", "/history", "/login"];

export function SiteWeb() {
  const pathname = usePathname() ?? "/";

  if (pathname === "/") return null;

  const quiet = QUIET.some((p) => pathname.startsWith(p));

  return (
    <SpiderWebBackground
      className="fixed inset-0 h-full w-full -z-10"
      origin={quiet ? [1, 0] : [0, 0]}
      rotate={quiet ? 0.29 : 0.02}
      arc={quiet ? 0.36 : 0.22}
      spokes={quiet ? 14 : 16}
      rings={quiet ? 8 : 9}
      reach={1.15}
      opacity={quiet ? 0.13 : 0.2}
    />
  );
}
