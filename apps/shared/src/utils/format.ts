/**
 * Platform-agnostic formatting utilities.
 * Color helpers (pnlColor, pnlBg) stay in each platform since
 * web uses Tailwind classes and mobile uses hex colors.
 */

export function fmtCurrency(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `$${(value / 1_000).toFixed(1)}K`;
  }
  return `$${value.toFixed(2)}`;
}

export function fmtPct(value: number, decimals = 2): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(decimals)}%`;
}

export function fmtNum(value: number, decimals = 2): string {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function fmtDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString("en-CA");
}

export function fmtTime(isoString: string): string {
  return new Date(isoString).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}
