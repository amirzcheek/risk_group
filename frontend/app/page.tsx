"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Card, CardBody, RiskBadge, RiskBar, Disclaimer } from "@/components/ui";
import type { RiskListResponse, RiskStudent } from "@/lib/types";

export default function RiskListPage() {
  const [items, setItems] = useState<RiskStudent[]>([]);
  const [disclaimer, setDisclaimer] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [faculty, setFaculty] = useState("");
  const [group, setGroup] = useState("");
  const [level, setLevel] = useState("");
  // Полный список факультетов — берём один раз из неотфильтрованной выборки,
  // чтобы выпадающий список не схлопывался после применения фильтра.
  const [allFaculties, setAllFaculties] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (faculty) qs.set("faculty", faculty);
      if (group) qs.set("group", group);
      if (level) qs.set("level", level);
      const res = await fetch(`/api/risk?${qs.toString()}`);
      const data: RiskListResponse & { error?: string } = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || "Ошибка загрузки");
      setItems(data.items);
      setDisclaimer(data.disclaimer);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [faculty, group, level]);

  useEffect(() => {
    load();
  }, [load]);

  // Один раз грузим полный список факультетов (без фильтров) для выпадающего меню.
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/risk");
        const data: RiskListResponse & { error?: string } = await res.json();
        if (res.ok && !data.error) {
          const facs = Array.from(
            new Set(data.items.map((i) => i.faculty).filter(Boolean))
          ) as string[];
          setAllFaculties(facs.sort());
        }
      } catch {
        /* список факультетов не критичен — молча игнорируем */
      }
    })();
  }, []);

  const faculties = allFaculties;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-zinc-800">Студенты группы риска</h1>
          <p className="text-sm text-zinc-500">
            Список флагов последнего еженедельного прогона. Отсортировано по уровню риска.
          </p>
        </div>
        <div className="text-sm text-zinc-500">Найдено: <b>{items.length}</b></div>
      </div>

      <Disclaimer text={disclaimer} />

      {/* Фильтры */}
      <Card>
        <CardBody className="flex flex-wrap gap-3 items-end">
          <label className="text-sm">
            <span className="block text-zinc-500 mb-1">Факультет</span>
            <select
              className="border rounded-md px-2 py-1.5 min-w-48"
              value={faculty}
              onChange={(e) => setFaculty(e.target.value)}
            >
              <option value="">Все</option>
              {faculties.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="block text-zinc-500 mb-1">Группа</span>
            <input
              className="border rounded-md px-2 py-1.5 w-32"
              placeholder="напр. ИТ-22"
              value={group}
              onChange={(e) => setGroup(e.target.value)}
            />
          </label>
          <label className="text-sm">
            <span className="block text-zinc-500 mb-1">Уровень риска</span>
            <select
              className="border rounded-md px-2 py-1.5"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
            >
              <option value="">Любой</option>
              <option value="high">Высокий</option>
              <option value="medium">Средний</option>
              <option value="low">Низкий</option>
            </select>
          </label>
          <button
            type="button"
            onClick={load}
            className="ml-auto rounded-md bg-zinc-800 text-white px-4 py-1.5 text-sm hover:bg-zinc-700"
          >
            Обновить
          </button>
        </CardBody>
      </Card>

      {loading && <p className="text-zinc-500">Загрузка…</p>}
      {error && (
        <Card>
          <CardBody className="text-red-600 text-sm">
            Не удалось получить данные: {error}
            <div className="text-zinc-500 mt-1">
              Проверьте, что бэкенд запущен и выполнен батч-скоринг (python scoring.py).
            </div>
          </CardBody>
        </Card>
      )}

      {!loading && !error && (
        <Card>
          <table className="w-full text-sm">
            <thead className="text-left text-zinc-500 border-b">
              <tr>
                <th className="px-4 py-2 font-medium">Студент</th>
                <th className="px-4 py-2 font-medium">Группа</th>
                <th className="px-4 py-2 font-medium">Факультет</th>
                <th className="px-4 py-2 font-medium">Риск</th>
                <th className="px-4 py-2 font-medium">Уровень</th>
                <th className="px-4 py-2 font-medium">Ключевые факторы</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.student_id} className="border-b last:border-0 hover:bg-zinc-50">
                  <td className="px-4 py-2">
                    <Link href={`/student/${s.student_id}`} className="text-blue-600 hover:underline">
                      {s.student_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-zinc-700">{s.study_group}</td>
                  <td className="px-4 py-2 text-zinc-600">{s.faculty}</td>
                  <td className="px-4 py-2"><RiskBar proba={s.risk_proba} level={s.risk_level} /></td>
                  <td className="px-4 py-2"><RiskBadge level={s.risk_level} /></td>
                  <td className="px-4 py-2 text-zinc-500">
                    {s.top_factors.slice(0, 2).map((f) => f.description).join("; ")}
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-zinc-400">
                    Нет студентов под выбранные фильтры.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
