// Серверный прокси: детальный профиль риска студента.
import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/api";
import type { RiskStudent } from "@/lib/types";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const data = await backendFetch<RiskStudent>(`/student/${encodeURIComponent(id)}`);
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
