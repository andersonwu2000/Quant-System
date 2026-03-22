// Re-export platform-agnostic formatters from shared
export { fmtCurrency, fmtPct, fmtNum, fmtDate, fmtTime } from "@quant/shared";

// Mobile-specific: hex color helpers (not shareable with web's Tailwind classes)
export function pnlColor(value: number): string {
  if (value > 0) return "#22C55E";
  if (value < 0) return "#EF4444";
  return "#94A3B8";
}
