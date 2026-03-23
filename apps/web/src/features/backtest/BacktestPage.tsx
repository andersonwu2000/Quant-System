import { useState, useCallback, useMemo } from "react";
import { ChevronDown } from "lucide-react";
import { MetricCard } from "@shared/ui";
import { fmtPct, fmtNum, fmtCurrency } from "@core/utils";
import { useT } from "@core/i18n";
import { useApi } from "@core/hooks";
import type { BacktestRequest, StrategyInfo } from "@core/api";
import { useBacktest } from "./hooks/useBacktest";
import { useBacktestHistory } from "./hooks/useBacktestHistory";
import type { BacktestHistoryEntry } from "./hooks/useBacktestHistory";
import { strategiesApi } from "@feat/strategies/api";
import { AnimatedSelect } from "./components/AnimatedSelect";
import { UniversePicker } from "./components/UniversePicker";
import { ResultChart } from "./components/ResultChart";
import { DrawdownChart } from "./components/DrawdownChart";
import { MonthlyHeatmap } from "./components/MonthlyHeatmap";
import { TradeTable } from "./components/TradeTable";
import { ParamsEditor } from "./components/ParamsEditor";
import { HistoryPanel } from "./components/HistoryPanel";
import { CompareTable } from "./components/CompareTable";
import { CompareChart } from "./components/CompareChart";

type AnalysisTab = "nav" | "drawdown" | "monthly" | "trades";

function createDefaultForm(): BacktestRequest {
  return {
    strategy: "momentum_12_1",
    universe: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
    start: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
    end: new Date().toISOString().slice(0, 10),
    initial_cash: 1_000_000,
    params: {},
    slippage_bps: 5,
    commission_rate: 0.001,
    rebalance_freq: "weekly",
  };
}

export function BacktestPage() {
  const { t } = useT();
  const [form, setForm] = useState(createDefaultForm);
  const [formOpen, setFormOpen] = useState(true);
  const { running, result, error, progress, submit } = useBacktest();
  const { history, addEntry, removeEntry, clearHistory } = useBacktestHistory();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [analysisTab, setAnalysisTab] = useState<AnalysisTab>("nav");

  const { data: strategies } = useApi<StrategyInfo[]>(() => strategiesApi.list());
  const effectiveStrategyOptions = useMemo(() => {
    const opts = (strategies || []).map((s) => ({ value: s.name, label: s.name }));
    return opts.length > 0 ? opts : [{ value: "momentum_12_1", label: "momentum_12_1" }];
  }, [strategies]);

  const set = (key: keyof BacktestRequest, val: unknown) =>
    setForm((f) => ({ ...f, [key]: val }));

  const formErrors: string[] = [];
  if (form.start >= form.end) formErrors.push(t.backtest.errorEndDate);
  if (form.initial_cash <= 0) formErrors.push(t.backtest.errorCash);
  if (form.universe.length === 0) formErrors.push(t.backtest.errorUniverse);
  const formValid = formErrors.length === 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await submit(form);
    if (res) {
      addEntry(form, res);
    }
  };

  const handleSelectHistory = useCallback((entry: BacktestHistoryEntry) => {
    setForm(entry.request);
  }, []);

  const handleToggleCompare = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleClearHistory = useCallback(() => {
    clearHistory();
    setSelectedIds(new Set());
  }, [clearHistory]);

  const handleRemoveEntry = useCallback((id: string) => {
    removeEntry(id);
    setSelectedIds((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, [removeEntry]);

  const compareEntries = useMemo(
    () => history.filter((e) => selectedIds.has(e.id)),
    [history, selectedIds],
  );

  const rebalanceOptions = [
    { value: "daily", label: t.backtest.daily },
    { value: "weekly", label: t.backtest.weekly },
    { value: "monthly", label: t.backtest.monthly },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">{t.backtest.title}</h2>

      <form
        onSubmit={handleSubmit}
        aria-busy={running}
        className="bg-slate-50 dark:bg-surface rounded-xl border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none overflow-hidden"
      >
        <button
          type="button"
          onClick={() => setFormOpen((v) => !v)}
          className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-slate-100 dark:hover:bg-surface-light/30 transition-colors"
        >
          <span className="text-base font-semibold text-slate-500 dark:text-slate-400">{t.backtest.strategyParams}</span>
          <ChevronDown
            size={16}
            className={`text-slate-400 transition-transform duration-200 ${formOpen ? "rotate-180" : ""}`}
          />
        </button>

        {formOpen && (
          <div className="px-5 pb-5 pt-1 grid grid-cols-2 lg:grid-cols-4 gap-4 border-t border-slate-200 dark:border-surface-light/40">
            <div className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.backtest.strategy}</span>
              <AnimatedSelect value={form.strategy} options={effectiveStrategyOptions} onChange={(v) => set("strategy", v)} />
            </div>
            <UniversePicker value={form.universe} onChange={(v) => set("universe", v)} />
            <label className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.backtest.start}</span>
              <input type="date" value={form.start} onChange={(e) => set("start", e.target.value)} required
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm" />
            </label>
            <label className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.backtest.end}</span>
              <input type="date" value={form.end} onChange={(e) => set("end", e.target.value)} required
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm" />
            </label>
            <label className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.backtest.initialCash}</span>
              <input type="number" value={form.initial_cash} min={1} onChange={(e) => set("initial_cash", +e.target.value)}
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm" />
            </label>
            <label className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.backtest.slippage}</span>
              <input type="number" value={form.slippage_bps} min={0} onChange={(e) => set("slippage_bps", +e.target.value)}
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm" />
            </label>
            <label className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.backtest.commissionRate}</span>
              <input type="number" step="0.0001" value={form.commission_rate} min={0} max={1}
                onChange={(e) => set("commission_rate", +e.target.value)}
                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-surface-light rounded-lg px-3 py-2 text-sm" />
            </label>
            <div className="space-y-1">
              <span className="text-sm text-slate-500 dark:text-slate-400">{t.backtest.rebalance}</span>
              <AnimatedSelect value={form.rebalance_freq} options={rebalanceOptions} onChange={(v) => set("rebalance_freq", v)} />
            </div>

            <ParamsEditor params={form.params} onChange={(p) => set("params", p)} />

            <div className="col-span-full space-y-2">
              {formErrors.length > 0 && (
                <ul className="text-sm text-amber-400 list-disc list-inside">
                  {formErrors.map((e) => <li key={e}>{e}</li>)}
                </ul>
              )}
              <button type="submit" disabled={running || !formValid}
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors">
                {running
                  ? (progress ? `${t.backtest.running} (${progress.current}/${progress.total})` : t.backtest.running)
                  : t.backtest.run}
              </button>
            </div>
          </div>
        )}
      </form>

      {error && <div aria-live="polite" className="bg-red-500/10 text-red-400 rounded-xl p-4 text-sm">{error}</div>}

      {result && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label={t.backtest.totalReturn} value={fmtPct(result.total_return)} />
            <MetricCard label={t.backtest.annualReturn} value={fmtPct(result.annual_return)} />
            <MetricCard label={t.backtest.sharpe} value={fmtNum(result.sharpe)} />
            <MetricCard label={t.backtest.maxDrawdown} value={fmtPct(result.max_drawdown)} />
            <MetricCard label={t.backtest.sortino} value={fmtNum(result.sortino)} />
            <MetricCard label={t.backtest.calmar} value={fmtNum(result.calmar)} />
            <MetricCard label={t.backtest.winRate} value={fmtPct(result.win_rate)} />
            <MetricCard label={t.backtest.totalTrades} value={String(result.total_trades)} sub={`Comm: ${fmtCurrency(result.total_commission)}`} />
          </div>

          {result.nav_series && result.nav_series.length > 0 && (
            <>
              <div className="flex gap-1 bg-slate-200 dark:bg-surface rounded-xl p-1">
                {(
                  [
                    { key: "nav", label: t.backtest.navCurve },
                    { key: "drawdown", label: t.backtest.drawdown },
                    { key: "monthly", label: t.backtest.monthlyReturns },
                    { key: "trades", label: t.backtest.tradeDetail },
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setAnalysisTab(tab.key)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      analysisTab === tab.key
                        ? "bg-blue-600 text-white"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-300 dark:hover:bg-surface-light"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {analysisTab === "nav" && <ResultChart data={result.nav_series} />}
              {analysisTab === "drawdown" && <DrawdownChart data={result.nav_series} />}
              {analysisTab === "monthly" && <MonthlyHeatmap data={result.nav_series} />}
              {analysisTab === "trades" && (
                result.trades
                  ? <TradeTable trades={result.trades} />
                  : <div className="bg-slate-50 dark:bg-surface rounded-xl p-5 text-sm text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-transparent">{t.common.noData}</div>
              )}
            </>
          )}
        </>
      )}

      <HistoryPanel
        history={history}
        onSelect={handleSelectHistory}
        onRemove={handleRemoveEntry}
        onClear={handleClearHistory}
        selectedIds={selectedIds}
        onToggleCompare={handleToggleCompare}
      />

      {compareEntries.length >= 2 && (
        <>
          <CompareChart entries={compareEntries} />
          <CompareTable entries={compareEntries} />
        </>
      )}
    </div>
  );
}
