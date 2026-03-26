import { Card } from './Card';

interface MetricCardProps {
  label: string;
  value: string;
  change?: string;
  changeType?: 'profit' | 'loss' | 'neutral';
  subtitle?: string;
}

export function MetricCard({ label, value, change, changeType = 'neutral', subtitle }: MetricCardProps) {
  const changeColor = changeType === 'profit' ? 'text-profit' : changeType === 'loss' ? 'text-loss' : 'text-neutral-400';
  const arrow = changeType === 'profit' ? '▲' : changeType === 'loss' ? '▼' : '';

  return (
    <Card>
      <p className="text-sm font-medium text-neutral-400">{label}</p>
      <p className="mt-1 text-3xl font-bold tabular-nums tracking-tight text-white">{value}</p>
      {change && (
        <span className={`mt-1 inline-flex items-center gap-1 text-xs ${changeColor}`}>
          {arrow} {change}
        </span>
      )}
      {subtitle && <p className="mt-1 text-xs text-neutral-500">{subtitle}</p>}
    </Card>
  );
}
