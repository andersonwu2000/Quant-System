import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { formatCurrency, formatPercent, changeType } from '../lib/format';
import { MetricCard } from '../shared/ui/MetricCard';
import { Card } from '../shared/ui/Card';
import { Badge } from '../shared/ui/Badge';
import { Skeleton } from '../shared/ui/Skeleton';

export default function OverviewPage() {
  const { data: portfolio, isLoading: loadingPortfolio, isError: portfolioError, error: portfolioErrorMsg } = useQuery({
    queryKey: ['portfolio'],
    queryFn: api.portfolio,
    refetchInterval: 60_000,
  });

  const { data: regime } = useQuery({
    queryKey: ['regime'],
    queryFn: api.regime,
    refetchInterval: 300_000,
  });

  const { data: dataStatus } = useQuery({
    queryKey: ['dataStatus'],
    queryFn: api.dataStatus,
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 30_000,
  });

  if (loadingPortfolio) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-3 gap-6">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  if (portfolioError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold text-white">總覽</h1>
        <Card className="border-red-500/30 bg-red-500/5">
          <p className="text-sm text-red-400">
            無法載入投資組合資料：{portfolioErrorMsg instanceof Error ? portfolioErrorMsg.message : '未知錯誤'}
          </p>
        </Card>
      </div>
    );
  }

  const nav = portfolio?.total_value ?? 0;
  const cash = portfolio?.cash ?? 0;
  const positions = portfolio?.positions ?? [];
  const dailyPnl = portfolio?.daily_pnl ?? 0;
  const dailyReturn = nav > 0 ? dailyPnl / nav : 0;

  const regimeLabel = regime?.regime === 'bull' ? '🟢 Bull' : regime?.regime === 'bear' ? '🔴 Bear' : regime?.regime === 'sideways' ? '🟡 Sideways' : '—';
  const regimeVariant = regime?.regime === 'bull' ? 'info' : regime?.regime === 'bear' ? 'loss' : 'warning';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-white">總覽</h1>
        <Badge variant={regimeVariant as any}>{regimeLabel}</Badge>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <MetricCard
          label="淨資產 (NAV)"
          value={formatCurrency(nav)}
          subtitle={`${positions.length} 檔持倉`}
        />
        <MetricCard
          label="今日損益"
          value={formatCurrency(dailyPnl)}
          change={formatPercent(dailyReturn)}
          changeType={changeType(dailyPnl)}
        />
        <MetricCard
          label="現金"
          value={formatCurrency(cash)}
          subtitle={nav > 0 ? `${((cash / nav) * 100).toFixed(0)}% 現金比` : ''}
        />
      </div>

      {/* Positions Table */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-white">持倉明細</h2>
          <span className="text-xs text-neutral-500">{positions.length} 檔</span>
        </div>

        {positions.length === 0 ? (
          <p className="text-sm text-neutral-500 py-8 text-center">尚無持倉</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left">
                <th className="pb-3 text-xs font-medium uppercase tracking-wider text-neutral-500">標的</th>
                <th className="pb-3 text-right text-xs font-medium uppercase tracking-wider text-neutral-500">市值</th>
                <th className="pb-3 text-right text-xs font-medium uppercase tracking-wider text-neutral-500">權重</th>
                <th className="pb-3 text-right text-xs font-medium uppercase tracking-wider text-neutral-500">損益</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {positions.slice(0, 10).map((pos: any) => {
                const weight = nav > 0 ? (pos.market_value / nav) : 0;
                const pnlType = changeType(pos.unrealized_pnl ?? 0);
                return (
                  <tr key={pos.symbol} className="transition-colors duration-150 hover:bg-white/5">
                    <td className="py-3 font-medium text-white">{pos.symbol}</td>
                    <td className="py-3 text-right font-data text-white">{formatCurrency(pos.market_value ?? 0)}</td>
                    <td className="py-3 text-right font-data text-neutral-400">{(weight * 100).toFixed(1)}%</td>
                    <td className={`py-3 text-right font-data ${pnlType === 'profit' ? 'text-profit' : pnlType === 'loss' ? 'text-loss' : 'text-neutral-400'}`}>
                      {formatPercent(pos.unrealized_pnl_pct ?? 0)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      {/* System Status Footer */}
      <div className="flex items-center gap-6 text-xs text-neutral-500">
        <span className="inline-flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${health ? 'bg-emerald-500 animate-pulse-dot' : 'bg-red-500'}`} />
          API {health ? 'OK' : 'Error'}
        </span>
        {dataStatus && (
          <>
            <span>價格: {dataStatus.market_symbols} 支</span>
            <span>營收: {dataStatus.revenue_symbols} 支</span>
            {dataStatus.latest_revenue_date && <span>最新營收: {dataStatus.latest_revenue_date}</span>}
          </>
        )}
      </div>
    </div>
  );
}
