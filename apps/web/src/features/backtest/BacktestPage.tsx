import { useState } from "react";
import { MetricCard } from "@shared/ui";
import { fmtPct, fmtNum, fmtCurrency } from "@core/utils";
import { useT } from "@core/i18n";
import { useBacktest } from "./hooks/useBacktest";
import { AnimatedSelect } from "./components/AnimatedSelect";
import { ResultChart } from "./components/ResultChart";
import type { BacktestRequest } from "./types";

const defaultForm: BacktestRequest = {
  strategy: "momentum",
  universe: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
  start: "2023-01-01",
  end: "2024-01-01",
  initial_cash: 1_000_000,
  params: {},
  slippage_bps: 5,
  commission_rate: 0.001,
  rebalance_freq: "weekly",
};

export function BacktestPage() {
  const { t } = useT();
  const [form, setForm] = useState(defaultForm);
  const { running, result, error, submit } = useBacktest();

  const set = (key: keyof BacktestRequest, val: unknown) =>
    setForm((f) => ({ ...f, [key]: val }));

  const strategyOptions = [
    { value: "momentum", label: "momentum" },
    { value: "mean_reversion", label: "mean_reversion" },
  ];

  const rebalanceOptions = [
    { value: "daily", label: t.backtest.daily },
    { value: "weekly", label: t.backtest.weekly },
    { value: "monthly", label: t.backtest.monthly },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">{t.backtest.title}</h2>

      <form
        onSubmit={(e) => { e.preventDefault(); submit(form); }}
        className="bg-surface rounded-xl p-5 grid grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <div className="space-y-1">
          <span className="text-sm text-slate-400">{t.backtest.strategy}</span>
          <AnimatedSelect value={form.strategy} options={strategyOptions} onChange={(v) => set("strategy", v)} />
        </div>
        <label className="space-y-1">
          <span className="text-sm text-slate-400">{t.backtest.universe}</span>
          <input value={form.universe.join(",")} required
            onChange={(e) => set("universe", e.target.value.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean))}
            className="w-full bg-surface-dark border border-surface-light rounded-lg px-3 py-2 text-sm" />
        </label>
        <label className="space-y-1">
          <span className="text-sm text-slate-400">{t.backtest.start}</span>
          <input type="date" value={form.start} onChange={(e) => set("start", e.target.value)} required
            className="w-full bg-surface-dark border border-surface-light rounded-lg px-3 py-2 text-sm" />
        </label>
        <label className="space-y-1">
          <span className="text-sm text-slate-400">{t.backtest.end}</span>
          <input type="date" value={form.end} onChange={(e) => set("end", e.target.value)} required
            className="w-full bg-surface-dark border border-surface-light rounded-lg px-3 py-2 text-sm" />
        </label>
        <label className="space-y-1">
          <span className="text-sm text-slate-400">{t.backtest.initialCash}</span>
          <input type="number" value={form.initial_cash} min={1} onChange={(e) => set("initial_cash", +e.target.value)}
            className="w-full bg-surface-dark border border-surface-light rounded-lg px-3 py-2 text-sm" />
        </label>
        <label className="space-y-1">
          <span className="text-sm text-slate-400">{t.backtest.slippage}</span>
          <input type="number" value={form.slippage_bps} min={0} onChange={(e) => set("slippage_bps", +e.target.value)}
            className="w-full bg-surface-dark border border-surface-light rounded-lg px-3 py-2 text-sm" />
        </label>
        <label className="space-y-1">
          <span className="text-sm text-slate-400">{t.backtest.commissionRate}</span>
          <input type="number" step="0.0001" value={form.commission_rate} min={0} max={1}
            onChange={(e) => set("commission_rate", +e.target.value)}
            className="w-full bg-surface-dark border border-surface-light rounded-lg px-3 py-2 text-sm" />
        </label>
        <div className="space-y-1">
          <span className="text-sm text-slate-400">{t.backtest.rebalance}</span>
          <AnimatedSelect value={form.rebalance_freq} options={rebalanceOptions} onChange={(v) => set("rebalance_freq", v)} />
        </div>

        <div className="col-span-full">
          <button type="submit" disabled={running}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
            {running ? t.backtest.running : t.backtest.run}
          </button>
        </div>
      </form>

      {error && <div className="bg-red-500/10 text-red-400 rounded-xl p-4 text-sm">{error}</div>}

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
            <ResultChart data={result.nav_series} />
          )}
        </>
      )}
    </div>
  );
}
