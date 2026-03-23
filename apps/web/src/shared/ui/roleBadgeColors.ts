import type { UserRole } from "@core/api";

export const ROLE_BADGE_COLORS: Record<UserRole, string> = {
  viewer: "bg-slate-200 dark:bg-slate-500/20 text-slate-600 dark:text-slate-400",
  researcher: "bg-cyan-100 dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-400",
  trader: "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400",
  risk_manager: "bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400",
  admin: "bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-400",
};
