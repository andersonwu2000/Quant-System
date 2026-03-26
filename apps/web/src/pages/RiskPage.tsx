import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Card } from '../shared/ui/Card';
import { Badge } from '../shared/ui/Badge';
import { MetricCard } from '../shared/ui/MetricCard';
import { Skeleton } from '../shared/ui/Skeleton';

/* ── Kill Switch ───────────────────────────────────────────── */

function KillSwitchCard() {
  const queryClient = useQueryClient();
  const { data: rules } = useQuery({ queryKey: ['riskRules'], queryFn: api.riskRules });
  const [confirming, setConfirming] = useState(false);

  const killSwitch = useMutation({
    mutationFn: (activate: boolean) => api.killSwitch(activate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['riskRules'] });
      setConfirming(false);
    },
  });

  const isActive = rules?.some?.((r: any) => r.name === 'kill_switch' && r.triggered);

  const handleClick = () => {
    if (confirming) {
      killSwitch.mutate(!isActive);
    } else {
      setConfirming(true);
    }
  };

  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-white">Kill Switch</h2>
          <p className="text-xs text-neutral-500 mt-1">緊急停止所有交易</p>
        </div>
        <div className="flex items-center gap-2">
          {confirming && (
            <button
              onClick={() => setConfirming(false)}
              className="rounded-lg px-3 py-2 text-sm font-medium text-neutral-400 border border-white/10 hover:bg-white/5 transition-colors duration-150"
            >
              取消
            </button>
          )}
          <button
            onClick={handleClick}
            disabled={killSwitch.isPending}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-150 ${
              confirming
                ? 'bg-red-600 text-white border border-red-500 hover:bg-red-500'
                : isActive
                  ? 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30'
                  : 'bg-[#262626] text-neutral-300 border border-white/10 hover:bg-white/10'
            }`}
          >
            {confirming
              ? (isActive ? '確認解除?' : '確認停止?')
              : (isActive ? '已啟動 — 點擊解除' : '未啟動')}
          </button>
        </div>
      </div>
    </Card>
  );
}

/* ── Rules List ────────────────────────────────────────────── */

function RulesList() {
  const { data: rules, isLoading } = useQuery({ queryKey: ['riskRules'], queryFn: api.riskRules });

  if (isLoading) return <Skeleton className="h-60" />;

  return (
    <Card>
      <h2 className="text-base font-semibold text-white mb-4">風控規則</h2>
      <div className="divide-y divide-white/5">
        {(rules ?? []).map((rule: any) => (
          <div key={rule.name} className="flex items-center justify-between py-3">
            <div>
              <span className="text-sm font-medium text-white">{rule.name}</span>
              {rule.description && (
                <p className="text-xs text-neutral-500 mt-0.5">{rule.description}</p>
              )}
            </div>
            <Badge variant={rule.triggered ? 'loss' : rule.enabled ? 'profit' : 'default'}>
              {rule.triggered ? '觸發' : rule.enabled ? '啟用' : '停用'}
            </Badge>
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ── Alerts ─────────────────────────────────────────────────── */

function AlertsList() {
  const { data: alerts, isLoading } = useQuery({ queryKey: ['riskAlerts'], queryFn: api.riskAlerts });

  if (isLoading) return <Skeleton className="h-40" />;

  const items = alerts?.alerts ?? alerts ?? [];

  return (
    <Card>
      <h2 className="text-base font-semibold text-white mb-4">歷史告警</h2>
      {items.length === 0 ? (
        <p className="text-sm text-neutral-500 text-center py-6">無告警紀錄</p>
      ) : (
        <div className="divide-y divide-white/5 max-h-80 overflow-auto">
          {items.slice(0, 20).map((alert: any, i: number) => (
            <div key={i} className="flex items-start gap-3 py-3">
              <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${
                alert.level === 'critical' ? 'bg-red-500' : alert.level === 'warning' ? 'bg-amber-500' : 'bg-blue-500'
              }`} />
              <div className="min-w-0">
                <p className="text-sm text-white truncate">{alert.message}</p>
                <p className="text-xs text-neutral-500">{alert.timestamp ?? alert.time ?? ''}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ── Page ──────────────────────────────────────────────────── */

export default function RiskPage() {
  const { data: realtime } = useQuery({
    queryKey: ['riskRealtime'],
    queryFn: api.riskRealtime,
    refetchInterval: 10_000,
  });

  const drawdown = realtime?.current_drawdown ?? 0;
  const ddLimit = realtime?.limit ?? 0.05;
  const ddPct = Math.min(Math.abs(drawdown) / ddLimit, 1);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">風控</h1>

      {/* KPI */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <MetricCard
          label="當日 Drawdown"
          value={`${(drawdown * 100).toFixed(2)}%`}
          subtitle={`上限 ${(ddLimit * 100).toFixed(0)}%`}
          changeType={Math.abs(drawdown) > ddLimit * 0.6 ? 'loss' : 'neutral'}
        />
        <MetricCard
          label="告警數"
          value={String(realtime?.active_alerts ?? 0)}
          subtitle="active"
        />
        <MetricCard
          label="風控狀態"
          value={realtime?.kill_switch_active ? '⛔ 停止' : '✅ 正常'}
          changeType={realtime?.kill_switch_active ? 'loss' : 'profit'}
        />
      </div>

      {/* Drawdown bar */}
      <Card>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-neutral-400">Drawdown 使用率</span>
          <span className="font-data text-white">{(ddPct * 100).toFixed(0)}%</span>
        </div>
        <div className="h-3 rounded-full bg-[#111111] overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              ddPct > 0.8 ? 'bg-red-500' : ddPct > 0.5 ? 'bg-amber-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${ddPct * 100}%` }}
          />
        </div>
      </Card>

      {/* Kill Switch */}
      <KillSwitchCard />

      {/* Rules */}
      <RulesList />

      {/* Alerts */}
      <AlertsList />
    </div>
  );
}
