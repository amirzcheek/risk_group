// Типы данных, приходящих с бэкенда системы группы риска.

export type RiskLevel = "high" | "medium" | "low";

export interface Factor {
  feature: string;
  description: string;
  value: number;
  contribution: number;
}

export interface RiskStudent {
  student_id: string;
  term: string;
  faculty: string | null;
  study_group: string | null;
  program: string | null;
  risk_proba: number;
  risk_level: RiskLevel;
  is_flagged: boolean;
  top_factors: Factor[];
  model_version?: string;
  scored_at?: string;
  disclaimer?: string;
}

export interface RiskListResponse {
  count: number;
  disclaimer: string;
  items: RiskStudent[];
}

export interface SummaryGroup {
  faculty: string | null;
  study_group: string | null;
  total: number;
  flagged: number;
}

export interface SummaryResponse {
  groups: SummaryGroup[];
  disclaimer: string;
}

// ── Летний семестр / должники (доступ только деканат/админ) ──

export interface DebtDiscipline {
  code: string;
  name: string;
  credits: number;
  mark: number;
}

export interface Debtor {
  student_id: string;
  fio: string;
  email: string | null;
  faculty: string | null;
  study_group: string | null;
  term: string;
  disciplines: DebtDiscipline[];
  total_credits: number;
  credit_cost: number;
  amount_due: number;
}

export interface DebtorsResponse {
  count: number;
  credit_cost: number;
  threshold: number;
  items: Debtor[];
}

export interface SummerEmail {
  student_id: string;
  fio: string;
  email: string | null;
  subject: string;
  body: string;
  amount_due: number;
  total_credits: number;
}

export interface SummerNotifyResponse {
  count: number;
  notifications: SummerEmail[];
}

export interface SummerSendResult {
  student_id: string;
  fio: string;
  email: string | null;
  status: "sent" | "dry-run" | "error";
  detail: string;
}

export interface SummerSendResponse {
  mode: "sent" | "dry-run";
  total: number;
  sent: number;
  dry_run: number;
  errors: number;
  results: SummerSendResult[];
}
