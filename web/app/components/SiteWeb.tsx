"use client";

import { usePathname } from "next/navigation";

import { SpiderWebBackground } from "./SpiderWebBackground";

/** The web, behind every page.
 *
 *  Fixed rather than absolute, so it stays put while the page scrolls past it —
 *  a web that scrolls away is a decoration, one that stays is a backdrop.
 *
 *  The home page is the exception. Its hero already carries a web anchored to
 *  the corner the spider hangs from, and that one has to scroll with him or the
 *  strand he is holding drifts off his hand. Rendering both would put two
 *  lattices at different depths on the busiest page on the site.
 *
 *  Reading routes get a heavier web than working ones: nobody is trying to
 *  compare a nutrient table through a lattice, but a page of prose can carry it.
 */

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
