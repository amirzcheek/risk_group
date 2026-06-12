"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

// Основные пункты навигации (доступны всем ролям).
const LINKS = [
  { href: "/", label: "Список риска" },
  { href: "/summary", label: "Сводка" },
];

export function NavLinks({ isAdmin = false }: { isAdmin?: boolean }) {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <>
      {LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={clsx("nav-pill", isActive(l.href) && "active")}
        >
          {l.label}
        </Link>
      ))}
      {/* Админ-пилюля «Рассылка должникам» — видна только админам (роль портала admin),
          по аналогии с пунктом «Админка» в топбаре портала. */}
      {isAdmin && (
        <Link href="/summer" className={clsx("admin-pill", isActive("/summer") && "active")}>
          Рассылка должникам
        </Link>
      )}
    </>
  );
}
