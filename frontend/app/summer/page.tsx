"use client";

import { Fragment, useEffect, useState } from "react";
import { Card, CardBody } from "@/components/ui";
import type {
  Debtor,
  DebtorsResponse,
  SummerEmail,
  SummerNotifyResponse,
  SummerSendResponse,
  SummerSendResult,
} from "@/lib/types";

function kzt(v: number) {
  return v.toLocaleString("ru-RU").replace(/,/g, " ") + " ₸";
}

const STATUS_LABEL: Record<SummerSendResult["status"], string> = {
  sent: "Отправлено",
  "dry-run": "Демо (не отправлено)",
  error: "Ошибка",
};
const STATUS_CLASS: Record<SummerSendResult["status"], string> = {
  sent: "text-green-700 bg-green-100",
  "dry-run": "text-amber-700 bg-amber-100",
  error: "text-red-700 bg-red-100",
};

export default function SummerPage() {
  const [items, setItems] = useState<Debtor[]>([]);
  const [creditCost, setCreditCost] = useState(0);
  const [threshold, setThreshold] = useState(50);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [faculty, setFaculty] = useState("");

  // Подготовленные письма (предпросмотр) и статусы отправки.
  const [emails, setEmails] = useState<Record<string, SummerEmail>>({});
  const [preparing, setPreparing] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [sendStatus, setSendStatus] = useState<Record<string, SummerSendResult["status"]>>({});
  const [sendingAll, setSendingAll] = useState(false);
  const [sendingId, setSendingId] = useState<string | null>(null);
  const [batchInfo, setBatchInfo] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/debtors");
        if (res.status === 403) {
          setForbidden(true);
          return;
        }
        const data: DebtorsResponse & { error?: string } = await res.json();
        if (!res.ok || data.error) throw new Error(data.error || "Ошибка загрузки");
        setItems(data.items);
        setCreditCost(data.credit_cost);
        setThreshold(data.threshold);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function prepareEmails() {
    if (!confirm(`Сформировать письма для ${items.length} должников (предпросмотр)?`)) return;
    setPreparing(true);
    try {
      const res = await fetch("/api/summer/notify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data: SummerNotifyResponse & { error?: string } = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || "Ошибка подготовки писем");
      const map: Record<string, SummerEmail> = {};
      for (const e of data.notifications) map[e.student_id] = e;
      setEmails(map);
    } catch (e) {
      alert(String(e));
    } finally {
      setPreparing(false);
    }
  }

  function applyResults(data: SummerSendResponse) {
    setSendStatus((prev) => {
      const next = { ...prev };
      for (const r of data.results) next[r.student_id] = r.status;
      return next;
    });
    const mode = data.mode === "dry-run" ? " (ДЕМО-режим: SMTP не настроен, письма не уходят)" : "";
    setBatchInfo(
      `Готово${mode}: отправлено ${data.sent}, демо ${data.dry_run}, ошибок ${data.errors} из ${data.total}.`
    );
  }

  async function sendAll() {
    if (
      !confirm(
        `Отправить письма ВСЕМ должникам (${items.length})?\n\n` +
          "Действие необратимо. Письма с суммами к оплате уйдут на почты студентов " +
          "(если настроен SMTP; иначе — демо-режим без отправки)."
      )
    )
      return;
    setSendingAll(true);
    setBatchInfo(null);
    try {
      const res = await fetch("/api/summer/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data: SummerSendResponse & { error?: string } = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || "Ошибка отправки");
      applyResults(data);
    } catch (e) {
      alert(String(e));
    } finally {
      setSendingAll(false);
    }
  }

  async function sendOne(d: Debtor) {
    if (
      !confirm(
        `Отправить письмо студенту ${d.fio} (${d.email ?? "нет email"})?\n\n` +
          "Действие необратимо (если настроен SMTP; иначе — демо-режим)."
      )
    )
      return;
    setSendingId(d.student_id);
    try {
      const res = await fetch("/api/summer/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id: d.student_id }),
      });
      const data: SummerSendResponse & { error?: string } = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || "Ошибка отправки");
      applyResults(data);
    } catch (e) {
      alert(String(e));
    } finally {
      setSendingId(null);
    }
  }

  if (forbidden)
    return (
      <Card>
        <CardBody className="text-sm text-zinc-600">
          <p className="font-medium text-zinc-800 mb-1">Доступ ограничен</p>
          Раздел «Летний семестр · Должники» доступен только деканату/админу (роль портала
          admin).
        </CardBody>
      </Card>
    );

  const faculties = Array.from(new Set(items.map((i) => i.faculty).filter(Boolean))) as string[];
  const filtered = faculty ? items.filter((i) => i.faculty === faculty) : items;
  const totalSum = filtered.reduce((s, d) => s + d.amount_due, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-800">Летний семестр · Должники</h1>
          <p className="text-sm text-zinc-500">
            Студенты с задолженностями (итоговый балл ниже {threshold}). Стоимость кредита:{" "}
            {kzt(creditCost)}.
          </p>
        </div>
        <div className="text-sm text-zinc-500">
          Должников: <b>{filtered.length}</b> · сумма к оплате: <b>{kzt(totalSum)}</b>
        </div>
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
        ⚠️ Конфиденциально (ФИО, email, суммы). Доступ — только деканат/админ, действия логируются.
        Рассылка необратима — отправляйте осознанно.
      </div>

      <Card>
        <CardBody className="flex flex-wrap items-end gap-3">
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
          <button
            type="button"
            onClick={prepareEmails}
            disabled={preparing || items.length === 0}
            className="ml-auto rounded-[14px] border border-[var(--line)] px-4 py-1.5 text-sm font-semibold text-[var(--sub)] hover:bg-[var(--line-soft)] disabled:opacity-50"
          >
            {preparing ? "Готовлю…" : "Сформировать письма (предпросмотр)"}
          </button>
          <button
            type="button"
            onClick={sendAll}
            disabled={sendingAll || items.length === 0}
            className="rounded-[14px] bg-red-600 text-white px-4 py-1.5 text-sm font-bold hover:bg-red-700 disabled:opacity-50"
          >
            {sendingAll ? "Отправляю…" : `Отправить письма всем (${items.length})`}
          </button>
        </CardBody>
      </Card>

      {loading && <p className="text-zinc-500">Загрузка…</p>}
      {error && <Card><CardBody className="text-red-600 text-sm">{error}</CardBody></Card>}

      {batchInfo && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">
          {batchInfo}
        </div>
      )}

      {!loading && !error && (
        <Card>
          <table className="w-full text-sm">
            <thead className="text-left text-zinc-500 border-b">
              <tr>
                <th className="px-4 py-2 font-medium">ФИО</th>
                <th className="px-4 py-2 font-medium">Группа</th>
                <th className="px-4 py-2 font-medium">Задолженности</th>
                <th className="px-4 py-2 font-medium">Кредиты</th>
                <th className="px-4 py-2 font-medium">К оплате</th>
                <th className="px-4 py-2 font-medium">Письмо</th>
                <th className="px-4 py-2 font-medium">Отправка</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((d) => (
                <Fragment key={d.student_id}>
                  <tr className="border-b last:border-0 hover:bg-zinc-50">
                    <td className="px-4 py-2 text-zinc-800">{d.fio}</td>
                    <td className="px-4 py-2 text-zinc-600">{d.study_group}</td>
                    <td className="px-4 py-2 text-zinc-500">
                      {d.disciplines.map((x) => x.name).join(", ")}
                    </td>
                    <td className="px-4 py-2 tabular-nums">{d.total_credits}</td>
                    <td className="px-4 py-2 tabular-nums font-medium text-zinc-800">{kzt(d.amount_due)}</td>
                    <td className="px-4 py-2">
                      {emails[d.student_id] ? (
                        <button
                          type="button"
                          onClick={() => setOpenId(openId === d.student_id ? null : d.student_id)}
                          className="text-[var(--accent)] hover:underline"
                        >
                          {openId === d.student_id ? "Скрыть" : "Письмо"}
                        </button>
                      ) : (
                        <span className="text-zinc-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      {sendStatus[d.student_id] ? (
                        <span
                          className={
                            "inline-block rounded-full px-2 py-0.5 text-xs font-medium " +
                            STATUS_CLASS[sendStatus[d.student_id]]
                          }
                        >
                          {STATUS_LABEL[sendStatus[d.student_id]]}
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => sendOne(d)}
                          disabled={sendingId === d.student_id}
                          className="text-[var(--accent)] hover:underline disabled:opacity-50"
                        >
                          {sendingId === d.student_id ? "…" : "Отправить"}
                        </button>
                      )}
                    </td>
                  </tr>
                  {openId === d.student_id && emails[d.student_id] && (
                    <tr className="bg-zinc-50">
                      <td colSpan={7} className="px-4 py-3">
                        <div className="text-xs text-zinc-500 mb-1">
                          Кому: {emails[d.student_id].email} · Тема: {emails[d.student_id].subject}
                        </div>
                        <pre className="whitespace-pre-wrap text-sm text-zinc-700 bg-white border rounded-md p-3">
                          {emails[d.student_id].body}
                        </pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-zinc-400">
                    Должников не найдено.
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
