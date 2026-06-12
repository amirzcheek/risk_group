"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardBody, RiskBadge, RiskBar, FactorList, Disclaimer } from "@/components/ui";
import type { RiskStudent } from "@/lib/types";

export default function StudentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [student, setStudent] = useState<RiskStudent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/student/${encodeURIComponent(id)}`);
        const data: RiskStudent & { error?: string } = await res.json();
        if (!res.ok || data.error) throw new Error(data.error || "Студент не найден");
        setStudent(data);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  if (loading) return <p className="text-zinc-500">Загрузка…</p>;
  if (error || !student)
    return (
      <div className="space-y-3">
        <Link href="/" className="text-[var(--accent)] text-sm hover:underline">← К списку</Link>
        <Card><CardBody className="text-red-600 text-sm">{error || "Нет данных"}</CardBody></Card>
      </div>
    );

  return (
    <div className="space-y-4">
      <Link href="/" className="text-[var(--accent)] text-sm hover:underline">← К списку группы риска</Link>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-800">Студент {student.student_id}</h1>
          <p className="text-sm text-zinc-500">
            {student.faculty} · группа {student.study_group} · {student.program}
          </p>
        </div>
        <RiskBadge level={student.risk_level} />
      </div>

      <Disclaimer text={student.disclaimer} />

      <div className="grid md:grid-cols-3 gap-4">
        <Card>
          <CardBody>
            <p className="text-sm text-zinc-500 mb-2">Уровень риска</p>
            <RiskBar proba={student.risk_proba} level={student.risk_level} />
            <p className="text-xs text-zinc-400 mt-2">
              Вероятность отчисления по модели на неделю отсечки. Период: {student.term}.
            </p>
          </CardBody>
        </Card>
        <Card className="md:col-span-2">
          <CardBody>
            <p className="text-sm text-zinc-500 mb-3">
              Почему студент в группе риска — вклад факторов (объяснение модели)
            </p>
            <FactorList factors={student.top_factors} />
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardBody className="text-xs text-zinc-400">
          Версия модели: {student.model_version || "—"} · оценка от {student.scored_at || "—"}.
          Это инструмент поддержки эдвайзера: рекомендуется связаться со студентом,
          уточнить ситуацию и при необходимости предложить помощь.
        </CardBody>
      </Card>
    </div>
  );
}
