// Минимальные UI-примитивы в духе shadcn/ui (Tailwind). Без внешних зависимостей.
import clsx from "clsx";
import type { RiskLevel, Factor } from "@/lib/types";

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx("rounded-xl border bg-white shadow-sm", className)}>{children}</div>
  );
}

export function CardBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("p-4", className)}>{children}</div>;
}

const LEVEL_LABEL: Record<RiskLevel, string> = {
  high: "Высокий риск",
  medium: "Средний риск",
  low: "Низкий риск",
};

const LEVEL_CLASS: Record<RiskLevel, string> = {
  high: "bg-red-100 text-red-700 border-red-200",
  medium: "bg-amber-100 text-amber-700 border-amber-200",
  low: "bg-green-100 text-green-700 border-green-200",
};

export function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span className={clsx("inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium", LEVEL_CLASS[level])}>
      {LEVEL_LABEL[level]}
    </span>
  );
}

export function RiskBar({ proba, level }: { proba: number; level: RiskLevel }) {
  const pct = Math.round(proba * 100);
  const barColor =
    level === "high" ? "bg-red-500" : level === "medium" ? "bg-amber-500" : "bg-green-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-28 rounded-full bg-zinc-200 overflow-hidden">
        <div className={clsx("h-full rounded-full", barColor)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm tabular-nums text-zinc-600">{pct}%</span>
    </div>
  );
}

// Наглядный вклад факторов: чем длиннее полоса, тем сильнее фактор толкает в риск.
export function FactorList({ factors }: { factors: Factor[] }) {
  if (!factors?.length) return <p className="text-sm text-zinc-400">Нет выраженных факторов.</p>;
  const max = Math.max(...factors.map((f) => f.contribution), 0.0001);
  return (
    <ul className="space-y-2">
      {factors.map((f) => (
        <li key={f.feature}>
          <div className="flex justify-between text-sm">
            <span className="text-zinc-700">{f.description}</span>
            <span className="text-zinc-400 tabular-nums">знач. {f.value}</span>
          </div>
          <div className="mt-1 h-1.5 w-full rounded-full bg-zinc-100 overflow-hidden">
            <div
              className="h-full rounded-full bg-red-400"
              style={{ width: `${Math.round((f.contribution / max) * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function Disclaimer({ text }: { text?: string }) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
      ⚠️ {text || "Это вероятностный сигнал системы раннего предупреждения, а не приговор. Решение и вмешательство остаются за эдвайзером/деканатом."}
    </div>
  );
}
