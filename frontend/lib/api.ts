// Серверный клиент к бэкенду группы риска.
//
// Используется ТОЛЬКО в серверных route handlers (app/api/*) и серверных
// компонентах. Адрес бэкенда и сервисный токен живут в переменных окружения
// сервера Next и НЕ попадают в браузер. Так список риска (чувствительные данные)
// не светится напрямую клиенту, а проходит через серверный прокси.

const API_BASE = process.env.RISK_API_BASE || "http://localhost:8000";
const ACTOR = process.env.RISK_ACTOR || "unknown";
const SERVICE_TOKEN = process.env.RISK_SERVICE_TOKEN || "";

// Роль текущего пользователя берётся ИЗ ПОРТАЛА per-request: шлюз/SSO портала
// проставляет заголовок x-user-role для каждого запроса к этому приложению.
// Раздел «Должники/Летник» доступен только роли портала "admin".
// RISK_ROLE — локальный фоллбэк для разработки, когда заголовка портала нет.
const PORTAL_ROLE_HEADER = "x-user-role";
const ADMIN_ROLE = "admin";

export async function getRole(): Promise<string> {
  try {
    const { headers } = await import("next/headers");
    const h = await headers();
    const fromPortal = h.get(PORTAL_ROLE_HEADER);
    if (fromPortal) return fromPortal.trim().toLowerCase();
  } catch {
    /* нет контекста заголовков — используем фоллбэк ниже */
  }
  return (process.env.RISK_ROLE || "advisor").toLowerCase();
}

export async function isAdmin(): Promise<boolean> {
  return (await getRole()) === ADMIN_ROLE;
}

interface FetchOptions {
  method?: string;
  body?: unknown;
  withToken?: boolean;
}

export async function backendFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    // Идентификатор смотрящего — для журнала доступа на бэкенде.
    "X-Actor": ACTOR,
  };
  if (opts.withToken && SERVICE_TOKEN) {
    headers["X-Service-Token"] = SERVICE_TOKEN;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method || "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Бэкенд вернул ${res.status}: ${text}`);
  }
  return (await res.json()) as T;
}
