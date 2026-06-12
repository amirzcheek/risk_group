import type { Metadata } from "next";
import { NavLinks } from "@/components/nav-links";
import { isAdmin } from "@/lib/api";
import "./globals.css";

export const metadata: Metadata = {
  title: "Группа риска — Early Warning (KNUS Digital)",
  description: "Раннее выявление студентов с риском отчисления. Сигнал для эдвайзеров.",
};

// Рендерим динамически, чтобы роль пользователя (для показа админ-пунктов меню)
// читалась в рантайме, а не «запекалась» на этапе сборки.
export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const admin = await isAdmin();
  return (
    <html lang="ru">
      <head>
        {/* Шрифт портала KNUS Digital */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <header className="topbar-wrap">
          <div className="mx-auto max-w-6xl px-4">
            <div className="topbar">
              <div className="topbar-left">
                <a className="brand" href="https://ai.knus.edu.kz/">
                  KNUS Digital
                </a>
                <span className="brand-sep">/</span>
                <span className="agent-name">Группа риска</span>
              </div>
              <nav className="topbar-right">
                <NavLinks isAdmin={admin} />
                <a className="portal-btn" href="https://ai.knus.edu.kz/">
                  ← На портал
                </a>
              </nav>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 py-6 text-xs text-[var(--sub)]">
          Доступ к списку риска ограничен ролью и логируется. Это вероятностный
          сигнал, а не приговор — решение остаётся за человеком.
        </footer>
      </body>
    </html>
  );
}
