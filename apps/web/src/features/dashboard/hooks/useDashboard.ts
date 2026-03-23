import { useCallback, useState } from "react";
import { useApi, useWs } from "@core/hooks";
import { portfolioApi, strategiesApi } from "../api";
import type { Portfolio, StrategyInfo } from "@core/api";

export function useDashboard() {
  const { data: pf, error, refresh, setData: setPf } = useApi<Portfolio>(portfolioApi.get);
  const { data: strats } = useApi<StrategyInfo[]>(strategiesApi.list);
  const [navHistory, setNavHistory] = useState<{ time: string; nav: number }[]>([]);

  const { connected } = useWs("portfolio", useCallback((msg: unknown) => {
    // Type guard: verify WS message structure before casting
    if (!msg || typeof msg !== "object" || !("nav" in msg) || typeof (msg as Record<string, unknown>).nav !== "number") return;
    const d = msg as Partial<Portfolio>;
    setPf((prev) => prev ? { ...prev, ...d } as Portfolio : prev);
    setNavHistory((prev) => {
      const entry = {
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        nav: (msg as Record<string, unknown>).nav as number,
      };
      return [...prev.slice(-59), entry];
    });
  }, [setPf]));

  const running = strats?.filter((s) => s.status === "running").length ?? 0;

  return { pf, error, refresh, navHistory, running, connected };
}
