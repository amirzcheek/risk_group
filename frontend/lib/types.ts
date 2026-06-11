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
