import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../lib/api';
import { formatPercent, formatCurrency } from '../lib/format';
import { Card } from '../shared/ui/Card';
import { Badge } from '../shared/ui/Badge';
import { Skeleton } from '../shared/ui/Skeleton';

export default function BacktestPage() {
  const [strategy, setStrategy] = useState('revenue_momentum_hedged');
  const [start, setStart] = useState('2018-01-01');
  const [end, setEnd] = useState('2024-12-31');
  const [result, setResult] = useState<any>(null);

  const btMutation = useMutation({
    mutationFn: async () => {
      const res = await api.backtest({
        strategy,
        start,
        end,
        universe: [
          '2330.TW','2317.TW','2454.TW','2303.TW','2308.TW',
          '2881.TW','2882.TW','2886.TW','2891.TW','1301.TW',
          '1303.TW','1101.TW','2002.TW','3008.TW','3034.TW',
          '2412.TW','2379.TW','2603.TW','5871.TW','2880.TW',
        ],
        rebalance_freq: 'monthly',
      });
      // Poll for result
      const taskId = res.task_id;
      if (!taskId) return res;

      for (let i = 0; i < 60; i++) {
        await new Promise(r => setTimeout(r, 3000));
        try {
          const r2 = await api.backtestResult(taskId);
          if (r2) return r2;
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
            // still running — continue polling
            continue;
          }
          throw err;
        }
      }
      throw new Error('回測超時');
    },
    onSuccess: (data) => setResult(data),
  });

  const inputClass = "rounded-md border border-white/15 bg-[#262626] px-3 py-2 text-sm text-white placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">回測</h1>

      {/* Form */}
      <Card>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <div>
            <label className="block text-xs font-medium text-neutral-400 mb-1">策略</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className={inputClass + ' w-full'}
            >
              <option value="revenue_momentum_hedged">Revenue Momentum Hedged</option>
              <option value="revenue_momentum">Revenue Momentum</option>
              <option value="momentum_12_1">Momentum 12-1</option>
              <option value="mean_reversion">Mean Reversion</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-neutral-400 mb-1">開始</label>
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={inputClass + ' w-full'} />
          </div>
          <div>
            <label className="block text-xs font-medium text-neutral-400 mb-1">結束</label>
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={inputClass + ' w-full'} />
          </div>
          <div className="flex items-end">
            <button
              onClick={() => btMutation.mutate()}
              disabled={btMutation.isPending}
              className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors duration-150 disabled:opacity-50"
            >
              {btMutation.isPending ? '執行中...' : '🚀 執行回測'}
            </button>
          </div>
        </div>
      </Card>

      {/* Loading */}
      {btMutation.isPending && <Skeleton className="h-60" />}

      {/* Error */}
      {btMutation.isError && (
        <Card className="border-red-500/30 bg-red-500/5">
          <p className="text-sm text-red-400">{btMutation.error instanceof Error ? btMutation.error.message : JSON.stringify(btMutation.error)}</p>
        </Card>
      )}

      {/* Result */}
      {result && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Card>
              <p className="text-xs text-neutral-400">CAGR</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-white">{formatPercent(result.annual_return ?? result.cagr ?? 0)}</p>
            </Card>
            <Card>
              <p className="text-xs text-neutral-400">Sharpe</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-white">{(result.sharpe ?? 0).toFixed(3)}</p>
            </Card>
            <Card>
              <p className="text-xs text-neutral-400">Max Drawdown</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-white">{formatPercent(-(result.max_drawdown ?? 0))}</p>
            </Card>
            <Card>
              <p className="text-xs text-neutral-400">Trades</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-white">{result.total_trades ?? 0}</p>
            </Card>
          </div>

          {result.sortino != null && (
            <Card>
              <h2 className="text-base font-semibold text-white mb-3">詳細指標</h2>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 text-sm">
                {[
                  ['Sortino', result.sortino?.toFixed(3)],
                  ['Calmar', result.calmar?.toFixed(3)],
                  ['勝率', result.win_rate ? `${(result.win_rate * 100).toFixed(1)}%` : '—'],
                  ['總報酬', formatPercent(result.total_return ?? 0)],
                  ['波動率', result.volatility ? `${(result.volatility * 100).toFixed(1)}%` : '—'],
                  ['交易次數', result.total_trades],
                ].map(([label, value]) => (
                  <div key={String(label)}>
                    <span className="text-neutral-400">{label}</span>
                    <p className="font-data text-white mt-0.5">{value ?? '—'}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
