// Серверный прокси: список должников (летний семестр). Только деканат/админ.
import { NextRequest, NextResponse } from "next/server";
import { backendFetch, isAdmin } from "@/lib/api";
import type { DebtorsResponse } from "@/lib/types";

export async function GET(req: NextRequest) {
  if (!(await isAdmin())) {
    return NextResponse.json(
      { error: "Доступ только для деканата/админа." },
      { status: 403 }
    );
  }
  const sp = req.nextUrl.searchParams;
  const qs = new URLSearchParams();
  for (const key of ["term", "threshold"]) {
    const v = sp.get(key);
    if (v) qs.set(key, v);
  }
  try {
    // withToken: чувствительная операция защищена сервисным токеном на бэкенде.
    const data = await backendFetch<DebtorsResponse>(`/debtors?${qs.toString()}`, {
      withToken: true,
    });
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
