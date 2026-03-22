import { get, put, post } from "@core/api";
import type { RiskRule, RiskAlert } from "./types";

export const riskApi = {
  rules: () => get<RiskRule[]>("/api/v1/risk/rules"),
  toggleRule: (name: string, enabled: boolean) => put<RiskRule>(`/api/v1/risk/rules/${name}`, { enabled }),
  alerts: () => get<RiskAlert[]>("/api/v1/risk/alerts"),
  killSwitch: () => post<{ detail: string }>("/api/v1/risk/kill-switch"),
};
