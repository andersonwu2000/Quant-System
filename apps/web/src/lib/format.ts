export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', maximumFractionDigits: 0 }).format(value);
}

export function formatPercent(value: number, decimals = 2): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(decimals)}%`;
}

export function formatNumber(value: number, decimals = 0): string {
  return new Intl.NumberFormat('zh-TW', { maximumFractionDigits: decimals }).format(value);
}

export function changeType(value: number): 'profit' | 'loss' | 'neutral' {
  // Taiwan convention: positive = profit (red), negative = loss (green)
  if (value > 0) return 'profit';
  if (value < 0) return 'loss';
  return 'neutral';
}

export function relativeTime(date: string | Date): string {
  const diff = Date.now() - new Date(date).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s 前`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m 前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h 前`;
  const days = Math.floor(hours / 24);
  return `${days}d 前`;
}
