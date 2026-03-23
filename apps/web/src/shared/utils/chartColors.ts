export function getChartColors(isDark: boolean) {
  return {
    grid: isDark ? "#334155" : "#e2e8f0",
    tick: isDark ? "#94a3b8" : "#64748b",
    tooltip: {
      bg: isDark ? "#1e293b" : "#ffffff",
      border: isDark ? "#334155" : "#e2e8f0",
    },
  };
}
