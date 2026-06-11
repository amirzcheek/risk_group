import type { Metadata } from "next";
import Link from "next/link";
import { NavLinks } from "@/components/nav-links";
import "./globals.css";

export const metadata: Metadata = {
  title: "Группа риска — Early Warning (KNUS)",
  description: "Раннее выявление студентов с риском отчисления. Сигнал для эдвайзеров.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <header className="border-b bg-white">
          <div className="mx-auto max-w-6xl px-5 py-3 flex items-center gap-4 flex-wrap">
            <Link href="/" className="text-[17px] font-bold text-zinc-800">
              Группа риска · Early Warning
            </Link>
            <NavLinks />
            <a
              href="https://ai.knus.edu.kz/"
              className="ml-auto inline-block whitespace-nowrap rounded-md border px-3 py-1.5 text-sm font-semibold text-[#2356c7] transition-colors hover:border-[#2356c7] hover:bg-[#eef1f7]"
            >
              ← Вернуться на портал
            </a>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 py-6 text-xs text-zinc-400">
          Доступ к списку риска ограничен ролью (эдвайзер/декан) и логируется.
          Это вероятностный сигнал, а не приговор — решение остаётся за человеком.
        </footer>
      </body>
    </html>
  );
}
