"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

// Пункты навигации в стиле прошлых агентов (таблетки с активным состоянием).
const LINKS = [
  { href: "/", label: "Список риска" },
  { href: "/summary", label: "Сводка" },
];

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1.5">
      {LINKS.map((l) => {
        const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
        return (
          <Link
            key={l.href}
            href={l.href}
            className={clsx(
              "rounded-md px-3 py-1.5 text-sm font-semibold transition-colors",
              active
                ? "bg-[#eef1f7] text-[#2356c7]"
                : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700"
            )}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
