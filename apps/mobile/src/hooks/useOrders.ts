import { useState, useEffect, useCallback } from "react";
import { orders } from "@quant/shared";
import type { OrderInfo } from "@quant/shared";

export function useOrders(filter?: string) {
  const [data, setData] = useState<OrderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await orders.list(filter === "all" ? undefined : filter as "open" | "filled");
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load orders");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { refresh(); }, [refresh]);

  return { data, loading, error, refresh };
}
