// Серверный прокси: список группы риска. Браузер обращается сюда, а не к бэкенду.
import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/api";
import type { RiskListResponse } from "@/lib/types";

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const qs = new URLSearchParams();
  for (const key of ["faculty", "group", "level"]) {
    const v = sp.get(key);
    if (v) qs.set(key, v);
  }
  try {
    const data = await backendFetch<RiskListResponse>(`/risk?${qs.toString()}`);
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
