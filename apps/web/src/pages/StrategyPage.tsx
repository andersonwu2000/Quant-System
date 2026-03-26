import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { formatPercent } from '../lib/format';
import { Card } from '../shared/ui/Card';
import { Badge } from '../shared/ui/Badge';
import { Skeleton } from '../shared/ui/Skeleton';
import { useState } from 'react';

/* ── Regime Panel ──────────────────────────────────────────── */

function RegimePanel({ data }: { data: any }) {
  if (!data) return <Skeleton className="h-40" />;

  const { regime, reason, indicators } = data;
  const color = regime === 'bull' ? 'text-emerald-400' : regime === 'bear' ? 'text-red-400' : 'text-amber-400';
  const emoji = regime === 'bull' ? '🟢' : regime === 'bear' ? '🔴' : '🟡';
  const positionScale = regime === 'bull' ? '100%' : regime === 'bear' ? '0%' : '30%';

  return (
    <Card>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <p className="text-sm font-medium text-neutral-400">空頭偵測</p>
          <p className={`mt-2 text-2xl font-semibold ${color}`}>{emoji} {regime?.toUpperCase()}</p>
          <p className="mt-1 text-xs text-neutral-500">{reason}</p>
          <div className="mt-4 space-y-2 text-sm">
            {indicators?.current_price != null && (
              <div className="flex justify-between">
                <span className="text-neutral-400">0050 現價</span>
                <span className="font-data text-white">{indicators.current_price}</span>
              </div>
            )}
            {indicators?.ma200 != null && (
              <div className="flex justify-between">
                <span className="text-neutral-400">MA200</span>
                <span className="font-data text-white">
                  {indicators.ma200}
                  <span className="ml-2 text-xs text-neutral-500">({formatPercent(indicators.price_vs_ma200)})</span>
                </span>
              </div>
            )}
            {indicators?.vol_20d != null && (
              <div className="flex justify-between">
                <span className="text-neutral-400">Vol 20d</span>
                <span className="font-data text-white">{(indicators.vol_20d * 100).toFixed(1)}%</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-neutral-400">倉位</span>
              <span className={`font-data ${color}`}>{positionScale}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-center rounded-lg border border-white/5 bg-[#111111] p-8 min-h-[160px]">
          <p className="text-xs text-neutral-600">0050 vs MA200 Chart (TBD)</p>
        </div>
      </div>
    </Card>
  );
}

/* ── Selection Table ───────────────────────────────────────── */

function SelectionTable({ selection, drift }: { selection: any; drift: any }) {
  if (!selection?.weights || Object.keys(selection.weights).length === 0) {
    return (
      <Card>
        <p className="text-sm text-neutral-500 text-center py-8">尚無選股結果</p>
      </Card>
    );
  }

  const weights: Record<string, number> = selection.weights;
  const driftMap: Record<string, any> = {};
  if (drift?.drift) {
    for (const d of drift.drift) driftMap[d.symbol] = d;
  }

  const entries = Object.entries(weights).sort(([, a], [, b]) => b - a);

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-white">{selection.date} 選股結果</h2>
          <p className="text-xs text-neutral-500 mt-1">{selection.n_targets} 檔 · {selection.strategy}</p>
        </div>
        {drift && (
          <Badge variant={drift.max_drift > 0.03 ? 'warning' : 'default'}>
            最大偏差 {(drift.max_drift * 100).toFixed(1)}%
          </Badge>
        )}
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 text-left">
            <th className="pb-3 text-xs font-medium uppercase tracking-wider text-neutral-500">標的</th>
            <th className="pb-3 text-right text-xs font-medium uppercase tracking-wider text-neutral-500">目標%</th>
            <th className="pb-3 text-right text-xs font-medium uppercase tracking-wider text-neutral-500">實際%</th>
            <th className="pb-3 text-right text-xs font-medium uppercase tracking-wider text-neutral-500">偏差</th>
            <th className="pb-3 text-center text-xs font-medium uppercase tracking-wider text-neutral-500">狀態</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {entries.map(([symbol, weight]) => {
            const d = driftMap[symbol];
            const actual = d?.actual_weight ?? 0;
            const driftVal = d?.drift ?? (actual - weight);
            const status = d?.status ?? (actual > 0 ? 'held' : 'new');
            const driftColor = Math.abs(driftVal) > 0.02 ? (driftVal > 0 ? 'text-profit' : 'text-loss') : 'text-neutral-500';

            return (
              <tr key={symbol} className="transition-colors duration-150 hover:bg-white/5">
                <td className="py-3 font-medium text-white">{symbol}</td>
                <td className="py-3 text-right font-data text-neutral-300">{(weight * 100).toFixed(1)}%</td>
                <td className="py-3 text-right font-data text-neutral-400">{(actual * 100).toFixed(1)}%</td>
                <td className={`py-3 text-right font-data ${driftColor}`}>
                  {driftVal >= 0 ? '+' : ''}{(driftVal * 100).toFixed(1)}%
                </td>
                <td className="py-3 text-center">
                  {status === 'new' && <Badge variant="info">新進</Badge>}
                  {status === 'exit' && <Badge variant="loss">退出</Badge>}
                  {status === 'held' && <Badge variant="default">持有</Badge>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

/* ── History ───────────────────────────────────────────────── */

function SelectionHistory({ data }: { data: any[] | undefined }) {
  if (!data || data.length === 0) return null;
  return (
    <Card>
      <h2 className="text-base font-semibold text-white mb-4">歷史選股</h2>
      <div className="divide-y divide-white/5">
        {data.map((item) => (
          <div key={item.date} className="flex items-center justify-between py-3">
            <div>
              <span className="text-sm font-medium text-white">{item.date}</span>
              <span className="ml-3 text-xs text-neutral-500">{item.n_targets} 檔</span>
            </div>
            <Badge variant="default">{item.strategy}</Badge>
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ── Page ──────────────────────────────────────────────────── */

export default function StrategyPage() {
  const queryClient = useQueryClient();
  const [showConfirm, setShowConfirm] = useState(false);

  const { data: info } = useQuery({ queryKey: ['strategyInfo'], queryFn: api.strategyInfo });
  const { data: regime, isLoading: regimeLoading } = useQuery({ queryKey: ['regime'], queryFn: api.regime, refetchInterval: 300_000 });
  const { data: selection } = useQuery({ queryKey: ['selectionLatest'], queryFn: api.selectionLatest });
  const { data: drift } = useQuery({ queryKey: ['drift'], queryFn: api.drift });
  const { data: history } = useQuery({ queryKey: ['selectionHistory'], queryFn: () => api.selectionHistory(6) });

  const rebalanceMutation = useMutation({
    mutationFn: api.rebalance,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['drift'] });
      queryClient.invalidateQueries({ queryKey: ['selectionLatest'] });
      setShowConfirm(false);
    },
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">策略中心</h1>
          <p className="text-sm text-neutral-500 mt-1">{info?.name ?? 'revenue_momentum_hedged'}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowConfirm(true)}
            disabled={rebalanceMutation.isPending}
            className="rounded-lg border border-white/10 bg-[#1a1a1a] px-4 py-2 text-sm font-medium text-white
                       hover:bg-[#262626] hover:border-white/15 transition-colors duration-150
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            📋 預覽再平衡
          </button>
          {showConfirm && (
            <button
              onClick={() => rebalanceMutation.mutate()}
              disabled={rebalanceMutation.isPending}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white
                         hover:bg-blue-500 transition-colors duration-150
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {rebalanceMutation.isPending ? '執行中...' : '🔄 確認執行'}
            </button>
          )}
        </div>
      </div>

      {/* Feedback */}
      {rebalanceMutation.isSuccess && (
        <Card className="border-emerald-500/30 bg-emerald-500/5">
          <p className="text-sm text-emerald-400">
            ✓ 再平衡完成：{rebalanceMutation.data?.n_approved ?? 0} 筆成交，
            {rebalanceMutation.data?.n_rejected ?? 0} 筆拒絕
          </p>
        </Card>
      )}
      {rebalanceMutation.isError && (
        <Card className="border-red-500/30 bg-red-500/5">
          <p className="text-sm text-red-400">✗ {(rebalanceMutation.error as Error).message}</p>
        </Card>
      )}

      {/* Regime */}
      {regimeLoading ? <Skeleton className="h-40" /> : <RegimePanel data={regime} />}

      {/* Selection */}
      <SelectionTable selection={selection} drift={drift} />

      {/* History */}
      <SelectionHistory data={history} />
    </div>
  );
}
