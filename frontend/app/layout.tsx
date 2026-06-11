import type { Metadata } from "next";
import Link from "next/link";
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
          <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
            <Link href="/" className="font-semibold text-zinc-800">
              Группа риска · Early Warning
            </Link>
            <nav className="flex gap-4 text-sm text-zinc-600">
              <Link href="/" className="hover:text-zinc-900">Список риска</Link>
              <Link href="/summary" className="hover:text-zinc-900">Сводка</Link>
            </nav>
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
