import { useState, useEffect, useCallback } from "react";
import type { RiskAlert } from "../types";
import { risk } from "../api/endpoints";
import { WSManager } from "../api/ws";

export function useAlerts() {
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const result = await risk.alerts();
      setAlerts(result);
    } catch {
      // silently fail, alerts will update via WebSocket
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Real-time alerts via WebSocket
  useEffect(() => {
    const ws = new WSManager("alerts");
    ws.connect();
    const unsubscribe = ws.subscribe((data) => {
      const alert = data as RiskAlert;
      setAlerts((prev) => [alert, ...prev]);
    });
    return () => {
      unsubscribe();
      ws.disconnect();
    };
  }, []);

  return { alerts, loading, refresh };
}
