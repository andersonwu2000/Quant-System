import { useCallback, useState } from "react";
import { useApi, useWs } from "@core/hooks";
import { portfolioApi, strategiesApi } from "../api";
import type { Portfolio, StrategyInfo } from "@core/types";

export function useDashboard() {
  const { data: pf, error, refresh, setData: setPf } = useApi<Portfolio>(portfolioApi.get);
  const { data: strats } = useApi<StrategyInfo[]>(strategiesApi.list);
  const [navHistory, setNavHistory] = useState<{ time: string; nav: number }[]>([]);

  useWs("portfolio", useCallback((msg: unknown) => {
    const d = msg as Portfolio;
    if (d && typeof d.nav === "number") {
      setPf(d);
      setNavHistory((prev) => {
        const entry = {
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          nav: d.nav,
        };
        return [...prev.slice(-59), entry];
      });
    }
  }, [setPf]));

  const running = strats?.filter((s) => s.status === "running").length ?? 0;

  return { pf, error, refresh, navHistory, running };
}
