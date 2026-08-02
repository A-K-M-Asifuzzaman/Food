"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const SECTIONS = [
  { href: "/admin", label: "Overview", note: "system at a glance" },
  { href: "/admin/models", label: "Models", note: "registry & ablations" },
  { href: "/admin/reliability", label: "Reliability", note: "calibration & conformal" },
  { href: "/admin/rag", label: "Retrieval", note: "RAG quality & spend" },
  { href: "/admin/knowledge-base", label: "Knowledge base", note: "101-class audit" },
];

export function AdminNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Admin sections">
      <ul className="flex lg:flex-col gap-2 overflow-x-auto lg:overflow-visible">
        {SECTIONS.map((s) => {
          const active = pathname === s.href;
          return (
            <li key={s.href} className="shrink-0">
              <Link
                href={s.href}
                aria-current={active ? "page" : undefined}
                className="block px-3 py-2 border-2 whitespace-nowrap lg:whitespace-normal"
                style={{
                  borderColor: active ? "var(--line)" : "transparent",
                  background: active ? "var(--panel)" : undefined,
                  boxShadow: active ? "3px 3px 0 var(--line)" : undefined,
                }}
              >
                <span className="font-display text-sm uppercase tracking-wide">{s.label}</span>
                <span className="hidden lg:block text-xs text-[var(--text-dim)]">{s.note}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
