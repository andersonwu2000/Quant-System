import { useState, useMemo } from "react";
import { Microscope } from "lucide-react";
import { useT } from "@core/i18n";
import { MetricCard, MetricCardSkeleton, ErrorAlert, HelpTip, TabBar } from "@shared/ui";
import { fmtNum, fmtPct } from "@quant/shared";
import { useAlphaResearch } from "./hooks/useAlphaResearch";
import { AlphaConfigForm } from "./components/AlphaConfigForm";
import { FactorSummaryTable } from "./components/FactorSummaryTable";
import { FactorICChart } from "./components/FactorICChart";
import { QuantileReturnChart } from "./components/QuantileReturnChart";
import { AllocationPage } from "@feat/allocation";
import { BacktestPage } from "@feat/backtest";

type Tab = "backtest" | "research" | "allocation";

/** Known ETF tickers (US-listed) */
const KNOWN_ETF_TICKERS = new Set([
  "SPY","QQQ","IWM","DIA","VOO","VTI",
  "XLK","XLF","XLV","XLE","XLY","XLP","XLI","XLU","XLB","XLRE","SMH",
  "EFA","EEM","VWO","FXI","EWJ","EWT",
  "TLT","IEF","SHY","LQD","HYG","AGG",
  "GLD","SLV","USO","DBA",
]);

function classifySymbol(s: string): "stock" | "etf" | "futures" {
  if (s.endsWith("=F")) return "futures";
  const base = s.replace(".TW", "");
  if (s.endsWith(".TW") && /^0/.test(base)) return "etf";
  if (KNOWN_ETF_TICKERS.has(s)) return "etf";
  return "stock";
}

function getUniverseLabel(
  universe: string[] | undefined,
  labels: { stocks: string; etfs: string; futures: string; instruments: string },
): string {
  if (!universe || universe.length === 0) return labels.instruments;
  const types = new Set(universe.map(classifySymbol));
  if (types.size === 1) {
    if (types.has("stock")) return labels.stocks;
    if (types.has("etf")) return labels.etfs;
    if (types.has("futures")) return labels.futures;
  }
  return labels.instruments;
}

export function AlphaPage() {
  const { t } = useT();
  const [tab, setTab] = useState<Tab>("backtest");
  const [selectedFactor, setSelectedFactor] = useState<string | null>(null);
  const { running, result, error, progress, submit } = useAlphaResearch();

  const tabs: { id: Tab; label: string }[] = [
    { id: "backtest",   label: t.nav.backtest },
    { id: "research",   label: t.alpha.tabResearch },
    { id: "allocation", label: t.alpha.tabAllocation },
  ];

  const detailFactor = result?.factors.find((f) => f.name === selectedFactor) ?? result?.factors[0] ?? null;

  const universeLabel = useMemo(
    () =>
      getUniverseLabel(result?.universe, {
        stocks: t.alpha.stocks,
        etfs: t.alpha.etfs,
        futures: t.alpha.futures,
        instruments: t.alpha.instruments,
      }),
    [result?.universe, t],
  );

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Microscope size={22} className="text-blue-500" />
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">{t.alpha.title}</h1>
      </div>

      {/* Mode tabs */}
      <TabBar tabs={tabs} active={tab} onChange={setTab} />

      {/* Research tab */}
      {tab === "research" && (
        <div className="space-y-6">
          <AlphaConfigForm onSubmit={submit} running={running} />

          {/* Progress */}
          {running && progress && (
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400">
                <span>{t.alpha.running}</span>
                <span>{progress.current} / {progress.total}</span>
              </div>
              <div className="h-1.5 bg-slate-200 dark:bg-surface-light rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${(progress.current / progress.total) * 100}%` }}
                />
              </div>
            </div>
          )}

          {running && !progress && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => <MetricCardSkeleton key={i} />)}
            </div>
          )}

          {error && <ErrorAlert message={error} />}

          {/* Results */}
          {result && (
            <div className="space-y-5">
              {/* Summary metrics */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <MetricCard label={`${t.alpha.universeSize} (${universeLabel})`} value={String(result.universe_size)} />
                <MetricCard label="Factors" value={String(result.factors.length)} />
                {result.composite_ic && (
                  <>
                    <MetricCard
                      label={`${t.alpha.compositeAlpha} IC`}
                      value={(result.composite_ic.ic_mean > 0 ? "+" : "") + fmtNum(result.composite_ic.ic_mean, 4)}
                      help={<HelpTip term="ic_mean" />}
                    />
                    <MetricCard
                      label={`${t.alpha.compositeAlpha} ICIR`}
                      value={(result.composite_ic.icir > 0 ? "+" : "") + fmtNum(result.composite_ic.icir, 2)}
                      help={<HelpTip term="icir" />}
                    />
                  </>
                )}
              </div>

              {/* Regime / attribution (renders for any universe type) */}
              {result.regime && (
                <div className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-xl shadow-sm p-5">
                  <h2 className="font-semibold text-slate-800 dark:text-slate-100 mb-2">
                    {t.allocation.regime}
                  </h2>
                  <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                    result.regime === "bull" ? "bg-emerald-100 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                      : result.regime === "bear" ? "bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-400"
                      : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                  }`}>
                    {(t.allocation.regimeLabels as Record<string, string>)[result.regime] ?? result.regime}
                  </span>
                </div>
              )}

              {/* Factor summary table */}
              <div className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-xl shadow-sm p-5 space-y-3">
                <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t.alpha.factorSummary}</h2>
                <p className="text-xs text-slate-400">{t.alpha.clickRowHint}</p>
                <FactorSummaryTable
                  factors={result.factors}
                  selected={selectedFactor ?? result.factors[0]?.name ?? null}
                  onSelect={setSelectedFactor}
                />
              </div>

              {/* Per-factor charts */}
              {detailFactor && (
                <div className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-xl shadow-sm p-5 space-y-6">
                  <h2 className="font-semibold text-slate-800 dark:text-slate-100">
                    {(t.alpha.factorNames as Record<string, string>)[detailFactor.name] ?? detailFactor.name}
                    <span className="ml-2 text-sm font-normal text-slate-400">
                      {t.alpha.breakevenCost}: {fmtNum(detailFactor.turnover.breakeven_cost_bps, 0)} bps
                      <HelpTip term="breakeven_cost" />
                    </span>
                  </h2>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {detailFactor.ic.ic_series && detailFactor.ic.ic_series.length > 0 && (
                      <FactorICChart ic={detailFactor.ic} factorName={detailFactor.name} />
                    )}
                    {detailFactor.quantile_returns.length > 0 && (
                      <QuantileReturnChart quantileReturns={detailFactor.quantile_returns} factorName={detailFactor.name} />
                    )}
                  </div>
                </div>
              )}

              {/* Composite quantile chart */}
              {result.composite_quantile_returns && result.composite_quantile_returns.length > 0 && (
                <div className="bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-xl shadow-sm p-5">
                  <h2 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">{t.alpha.compositeAlpha}</h2>
                  <QuantileReturnChart
                    quantileReturns={result.composite_quantile_returns}
                    factorName="composite"
                  />
                  {result.composite_long_short_sharpe != null && (
                    <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
                      L/S Sharpe: <span className={result.composite_long_short_sharpe > 0 ? "text-emerald-500 font-medium" : "text-red-400 font-medium"}>
                        {fmtNum(result.composite_long_short_sharpe, 2)}
                      </span>
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Backtest tab */}
      {tab === "backtest" && <BacktestPage />}

      {/* Allocation tab */}
      {tab === "allocation" && <AllocationPage />}

    </div>
  );
}
