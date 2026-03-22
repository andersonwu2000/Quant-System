import { useState, useEffect, useCallback } from "react";
import type { Portfolio } from "../types";
import { portfolio as portfolioApi } from "../api/endpoints";
import { WSManager } from "../api/ws";

export function usePortfolio(autoRefreshMs = 10000) {
  const [data, setData] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await portfolioApi.get();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load portfolio");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, autoRefreshMs);
    return () => clearInterval(interval);
  }, [refresh, autoRefreshMs]);

  // WebSocket real-time updates
  useEffect(() => {
    const ws = new WSManager("portfolio");
    ws.connect();
    const unsubscribe = ws.subscribe((update) => {
      setData((prev) => (prev ? { ...prev, ...(update as Partial<Portfolio>) } : prev));
    });
    return () => {
      unsubscribe();
      ws.disconnect();
    };
  }, []);

  return { data, loading, error, refresh };
}
