"use client";

import { useEffect, useState } from "react";
import { Card, CardBody, Disclaimer } from "@/components/ui";
import type { SummaryResponse, SummaryGroup } from "@/lib/types";

export default function SummaryPage() {
  const [groups, setGroups] = useState<SummaryGroup[]>([]);
  const [disclaimer, setDisclaimer] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/summary");
        const data: SummaryResponse & { error?: string } = await res.json();
        if (!res.ok || data.error) throw new Error(data.error || "Ошибка загрузки");
        setGroups(data.groups);
        setDisclaimer(data.disclaimer);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Агрегация по факультетам.
  const byFaculty = new Map<string, { total: number; flagged: number }>();
  for (const g of groups) {
    const key = g.faculty || "—";
    const acc = byFaculty.get(key) || { total: 0, flagged: 0 };
    acc.total += Number(g.total);
    acc.flagged += Number(g.flagged);
    byFaculty.set(key, acc);
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-zinc-800">Сводка по факультетам и группам</h1>
        <p className="text-sm text-zinc-500">Сколько студентов в зоне риска по последнему прогону.</p>
      </div>
      <Disclaimer text={disclaimer} />

      {loading && <p className="text-zinc-500">Загрузка…</p>}
      {error && <Card><CardBody className="text-red-600 text-sm">{error}</CardBody></Card>}

      {!loading && !error && (
        <>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-3">
            {Array.from(byFaculty.entries()).map(([fac, v]) => (
              <Card key={fac}>
                <CardBody>
                  <p className="text-sm text-zinc-500">{fac}</p>
                  <p className="text-2xl font-semibold text-zinc-800 mt-1">
                    {v.flagged}
                    <span className="text-base font-normal text-zinc-400"> / {v.total}</span>
                  </p>
                  <p className="text-xs text-zinc-400">в зоне риска / всего</p>
                </CardBody>
              </Card>
            ))}
          </div>

          <Card>
            <table className="w-full text-sm">
              <thead className="text-left text-zinc-500 border-b">
                <tr>
                  <th className="px-4 py-2 font-medium">Факультет</th>
                  <th className="px-4 py-2 font-medium">Группа</th>
                  <th className="px-4 py-2 font-medium">В зоне риска</th>
                  <th className="px-4 py-2 font-medium">Всего</th>
                  <th className="px-4 py-2 font-medium">Доля</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g, i) => {
                  const share = g.total ? Math.round((Number(g.flagged) / Number(g.total)) * 100) : 0;
                  return (
                    <tr key={i} className="border-b last:border-0 hover:bg-zinc-50">
                      <td className="px-4 py-2 text-zinc-600">{g.faculty}</td>
                      <td className="px-4 py-2 text-zinc-700">{g.study_group}</td>
                      <td className="px-4 py-2 font-medium text-zinc-800">{g.flagged}</td>
                      <td className="px-4 py-2 text-zinc-500">{g.total}</td>
                      <td className="px-4 py-2 text-zinc-500">{share}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
