// Серверный прокси: сводка по факультетам/группам.
import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/api";
import type { SummaryResponse } from "@/lib/types";

export async function GET() {
  try {
    const data = await backendFetch<SummaryResponse>("/summary");
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
