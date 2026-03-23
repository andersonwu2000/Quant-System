import { useCallback, useState } from "react";
import { useApi, useWs } from "@core/hooks";
import { portfolioApi, strategiesApi } from "../api";
import type { Portfolio, StrategyInfo } from "@core/api";

export function useDashboard() {
  const { data: pf, error, refresh, setData: setPf } = useApi<Portfolio>(portfolioApi.get);
  const { data: strats } = useApi<StrategyInfo[]>(strategiesApi.list);
  const [navHistory, setNavHistory] = useState<{ time: string; nav: number }[]>([]);

  const { connected } = useWs("portfolio", useCallback((msg: unknown) => {
    if (!msg || typeof msg !== "object") return;
    const raw = msg as Record<string, unknown>;
    if (typeof raw.nav !== "number") return;
    // Only spread known numeric fields to avoid overwriting complex objects with undefined
    const patch: Partial<Portfolio> = {};
    if (typeof raw.nav === "number") patch.nav = raw.nav;
    if (typeof raw.cash === "number") patch.cash = raw.cash;
    if (typeof raw.daily_pnl === "number") patch.daily_pnl = raw.daily_pnl;
    if (typeof raw.daily_pnl_pct === "number") patch.daily_pnl_pct = raw.daily_pnl_pct;
    if (typeof raw.gross_exposure === "number") patch.gross_exposure = raw.gross_exposure;
    if (typeof raw.net_exposure === "number") patch.net_exposure = raw.net_exposure;
    if (typeof raw.positions_count === "number") patch.positions_count = raw.positions_count;
    if (Array.isArray(raw.positions)) patch.positions = raw.positions as Portfolio["positions"];
    setPf((prev) => prev ? { ...prev, ...patch } : prev);
    setNavHistory((prev) => {
      const entry = {
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        nav: raw.nav as number,
      };
      return [...prev.slice(-59), entry];
    });
  }, [setPf]));

  const running = strats?.filter((s) => s.status === "running").length ?? 0;

  return { pf, error, refresh, navHistory, running, connected };
}
