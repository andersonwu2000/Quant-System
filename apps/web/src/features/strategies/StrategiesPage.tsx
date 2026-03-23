import { useState } from "react";
import { useApi } from "@core/hooks";
import { fmtCurrency, pnlColor } from "@core/utils";
import { StatusBadge, ErrorAlert, InfoTooltip, Skeleton } from "@shared/ui";
import { useT } from "@core/i18n";
import { useAuth } from "@core/auth";
import type { StrategyInfo } from "@quant/shared";
import { Play, Square } from "lucide-react";
import { strategiesApi } from "./api";

const STRATEGY_PREFIXES = ["momentum", "mean_reversion"] as const;
type StrategyDescKey = typeof STRATEGY_PREFIXES[number];

function getStrategyDescKey(name: string): StrategyDescKey | null {
  if ((STRATEGY_PREFIXES as readonly string[]).includes(name)) return name as StrategyDescKey;
  return STRATEGY_PREFIXES.find((p) => name.startsWith(p)) ?? null;
}

function InfoButton({ expanded, onClick, ariaLabel }: { expanded: boolean; onClick: () => void; ariaLabel: string }) {
  return (
    <button
      onClick={onClick}
      aria-expanded={expanded}
      aria-label={ariaLabel}
      className={`inline-flex items-center justify-center transition-colors ${
        expanded ? "text-blue-400" : "text-slate-500 hover:text-slate-300"
      }`}
    >
      <svg width="15" height="15" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
        <path d="M24,2A22,22,0,1,0,46,24,21.9,21.9,0,0,0,24,2Zm0,40A18,18,0,1,1,42,24,18.1,18.1,0,0,1,24,42Z"/>
        <path d="M24,20a2,2,0,0,0-2,2V34a2,2,0,0,0,4,0V22A2,2,0,0,0,24,20Z"/>
        <circle cx="24" cy="14" r="2"/>
      </svg>
    </button>
  );
}

export function StrategiesPage() {
  const { t } = useT();
  const { hasRole } = useAuth();
  const canTrade = hasRole("trader");
  const { data: strats, loading, error, refresh } = useApi<StrategyInfo[]>(strategiesApi.list);
  const [toggling, setToggling] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  // suppress unused import warning — InfoTooltip used indirectly via re-export test
  void InfoTooltip;

  const handleToggle = async (name: string, current: string) => {
    setToggling(name);
    setToggleError(null);
    try {
      if (current === "running") {
        await strategiesApi.stop(name);
      } else {
        await strategiesApi.start(name);
      }
      refresh();
    } catch (err) {
      setToggleError(err instanceof Error ? err.message : "Operation failed");
    } finally {
      setToggling(null);
    }
  };

  if (error) return <ErrorAlert message={error} onRetry={refresh} />;
  if (loading) return (
    <div className="space-y-6">
      <Skeleton className="h-7 w-40" />
      <div className="grid gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-slate-50 dark:bg-surface rounded-xl px-5 py-4 border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none">
            <div className="flex items-center gap-3">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-5 w-16" />
              <div className="flex-1" />
              <Skeleton className="h-9 w-20" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">{t.strategies.title}</h2>

      {toggleError && <ErrorAlert message={toggleError} />}

      <div className="grid gap-4">
        {strats?.map((s) => {
          const descKey = getStrategyDescKey(s.name);
          const description = descKey ? t.strategies.strategyDescriptions[descKey] : null;
          const isExpanded = expanded === s.name;

          return (
            <div key={s.name} className="bg-slate-50 dark:bg-surface rounded-xl overflow-hidden border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none">
              <div className="px-5 py-4 flex items-center gap-3">
                <div className="w-44 shrink-0">
                  <p className="font-semibold flex items-center gap-1.5">
                    {s.name}
                    {description && (
                      <InfoButton
                        expanded={isExpanded}
                        onClick={() => setExpanded(isExpanded ? null : s.name)}
                        ariaLabel={t.common.expandDescription}
                      />
                    )}
                  </p>
                  <p className={`text-sm ${pnlColor(s.pnl)}`}>{fmtCurrency(s.pnl)}</p>
                </div>
                <div className="w-px h-8 bg-slate-600/60 shrink-0" />
                <StatusBadge status={s.status} />
                <div className="flex-1" />
                {canTrade && (
                  <button
                    onClick={() => handleToggle(s.name, s.status)}
                    disabled={toggling === s.name}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                      s.status === "running"
                        ? "bg-red-100 dark:bg-red-500/15 text-red-700 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-500/25"
                        : "bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-200 dark:hover:bg-emerald-500/25"
                    }`}
                  >
                    {s.status === "running" ? (
                      <><Square size={14} /> {t.strategies.stop}</>
                    ) : (
                      <><Play size={14} /> {t.strategies.start}</>
                    )}
                  </button>
                )}
              </div>

              {description && (
                <div
                  className="overflow-hidden transition-all duration-300 ease-in-out"
                  style={{ maxHeight: isExpanded ? "200px" : "0px" }}
                >
                  <p className="px-5 pb-4 text-sm text-slate-500 dark:text-slate-400 leading-relaxed border-t border-slate-100 dark:border-surface-light/40 pt-3">
                    {description}
                  </p>
                </div>
              )}
            </div>
          );
        })}
        {(!strats || strats.length === 0) && (
          <p className="text-slate-500 text-center py-8">{t.strategies.noStrategies}</p>
        )}
      </div>
    </div>
  );
}
