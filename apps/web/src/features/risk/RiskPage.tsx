import { useCallback, useState } from "react";
import { useApi, useWs } from "@core/hooks";
import { fmtDate, fmtTime, fmtNum, translateApiError } from "@core/utils";
import { StatusBadge, ErrorAlert, InfoTooltip, useToast } from "@shared/ui";
import { useT } from "@core/i18n";
import { useAuth } from "@core/auth";
import { ShieldOff } from "lucide-react";
import { riskApi } from "./api";
import type { RiskRule, RiskAlert } from "./types";

const RULE_PREFIXES = [
  "max_position_weight",
  "max_order_notional",
  "daily_drawdown",
  "fat_finger",
  "max_daily_trades",
  "max_order_vs_adv",
] as const;

type RuleDescKey = typeof RULE_PREFIXES[number];

function getRuleDescKey(name: string): RuleDescKey | null {
  return RULE_PREFIXES.find((p) => name.startsWith(p)) ?? null;
}

export function RiskPage() {
  const { t } = useT();
  const { toast } = useToast();
  const { hasRole } = useAuth();
  const canManageRisk = hasRole("risk_manager");
  const { data: rules, error: rulesError, refresh: refreshRules } = useApi<RiskRule[]>(riskApi.rules);
  const { data: alerts, error: alertsError, refresh: refreshAlerts, setData: setAlerts } = useApi<RiskAlert[]>(riskApi.alerts);
  const [killMsg, setKillMsg] = useState<string | null>(null);
  const [killLoading, setKillLoading] = useState(false);
  const [toggling, setToggling] = useState<string | null>(null);

  useWs("alerts", useCallback((msg: unknown) => {
    const a = msg as RiskAlert;
    if (a && typeof a.timestamp === "string") {
      setAlerts((prev) => (prev ? [a, ...prev].slice(0, 100) : [a]));
    }
  }, [setAlerts]));

  const handleToggle = async (name: string, enabled: boolean) => {
    const action = enabled ? t.risk.disableRule : t.risk.enableRule;
    if (!window.confirm(`${action}: ${name}?`)) return;

    setToggling(name);
    try {
      await riskApi.toggleRule(name, !enabled);
      refreshRules();
      toast("success", t.toast.ruleSaved);
    } catch {
      toast("error", t.common.requestFailed);
    } finally {
      setToggling(null);
    }
  };

  const handleKill = async () => {
    if (!confirm(t.risk.killConfirm)) return;
    setKillLoading(true);
    try {
      const resp = await riskApi.killSwitch();
      setKillMsg(resp.message);
      toast("success", t.toast.killSwitchActivated);
    } catch (err) {
      setKillMsg(translateApiError(err instanceof Error ? err.message : t.common.requestFailed, t));
    } finally {
      setKillLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">{t.risk.title}</h2>
        {canManageRisk && (
          <button onClick={handleKill}
            disabled={killLoading}
            aria-label={t.risk.killSwitch}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors">
            <ShieldOff size={16} /> {killLoading ? "..." : t.risk.killSwitch}
          </button>
        )}
      </div>

      {killMsg && <div className="bg-red-500/10 text-red-400 rounded-xl p-4 text-sm">{killMsg}</div>}

      {rulesError && <ErrorAlert message={rulesError} onRetry={refreshRules} />}
      {!rulesError && (
        <div className="bg-slate-50 dark:bg-surface rounded-xl p-5 border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none">
          <p className="text-base font-semibold text-slate-500 dark:text-slate-400 mb-3">{t.risk.riskRules}</p>
          <div className="space-y-2">
            {rules?.map((r) => {
              const descKey = getRuleDescKey(r.name);
              const description = descKey ? t.risk.ruleDescriptions[descKey] : null;
              return (
                <div key={r.name} className="flex items-center justify-between py-2 border-b border-slate-100 dark:border-surface-light/50">
                  <span className="font-medium text-sm flex items-center">
                    {r.name}
                    {description && <InfoTooltip description={description} />}
                  </span>
                  {canManageRisk ? (
                    <button
                      onClick={() => handleToggle(r.name, r.enabled)}
                      disabled={toggling === r.name}
                      role="switch"
                      aria-checked={r.enabled}
                      className={`px-3 py-1 rounded-md text-xs font-semibold transition-colors disabled:opacity-50 ${
                        r.enabled
                          ? "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400"
                          : "bg-slate-100 dark:bg-slate-500/20 text-slate-600 dark:text-slate-400"
                      }`}
                    >
                      {r.enabled ? t.risk.enabled : t.risk.disabled}
                    </button>
                  ) : (
                    <span className={`px-3 py-1 rounded-md text-xs font-semibold ${
                      r.enabled
                        ? "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400"
                        : "bg-slate-100 dark:bg-slate-500/20 text-slate-600 dark:text-slate-400"
                    }`}>
                      {r.enabled ? t.risk.enabled : t.risk.disabled}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {alertsError && <ErrorAlert message={alertsError} onRetry={refreshAlerts} />}
      {!alertsError && (
        <div className="bg-slate-50 dark:bg-surface rounded-xl p-5 border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none" role="alert" aria-live="polite">
          <p className="text-base font-semibold text-slate-500 dark:text-slate-400 mb-3">{t.risk.recentAlerts}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-surface-light">
                  <th className="text-left py-2">{t.risk.time}</th>
                  <th className="text-left py-2">{t.risk.rule}</th>
                  <th className="text-left py-2">{t.risk.severity}</th>
                  <th className="text-right py-2">{t.risk.value}</th>
                  <th className="text-right py-2">{t.risk.threshold}</th>
                  <th className="text-left py-2">{t.risk.action}</th>
                  <th className="text-left py-2">{t.risk.message}</th>
                </tr>
              </thead>
              <tbody>
                {alerts?.map((a, i) => (
                  <tr key={`${a.timestamp}-${a.rule_name}-${i}`} className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30">
                    <td className="py-2 whitespace-nowrap">
                      <span className="text-slate-400">{fmtDate(a.timestamp)}</span> {fmtTime(a.timestamp)}
                    </td>
                    <td className="py-2">{a.rule_name}</td>
                    <td className="py-2"><StatusBadge status={a.severity} /></td>
                    <td className="text-right py-2">{fmtNum(a.metric_value, 4)}</td>
                    <td className="text-right py-2">{fmtNum(a.threshold, 4)}</td>
                    <td className="py-2 text-sm">{a.action_taken}</td>
                    <td className="py-2 text-sm text-slate-400 max-w-xs truncate">{a.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(!alerts || alerts.length === 0) && (
              <p className="text-center text-slate-500 py-8">{t.risk.noAlerts}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
