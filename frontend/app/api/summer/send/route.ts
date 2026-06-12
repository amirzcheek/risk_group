// Серверный прокси: отправка писем должникам (всем или одному). Только деканат/админ.
import { NextRequest, NextResponse } from "next/server";
import { backendFetch, isAdmin } from "@/lib/api";
import type { SummerSendResponse } from "@/lib/types";

export async function POST(req: NextRequest) {
  if (!(await isAdmin())) {
    return NextResponse.json(
      { error: "Доступ только для деканата/админа." },
      { status: 403 }
    );
  }
  let body: unknown = {};
  try {
    body = await req.json();
  } catch {
    body = {};
  }
  try {
    const data = await backendFetch<SummerSendResponse>("/summer/send", {
      method: "POST",
      body,
      withToken: true,
    });
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
