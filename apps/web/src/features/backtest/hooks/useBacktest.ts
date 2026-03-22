import { useState, useRef, useEffect } from "react";
import { backtestApi } from "../api";
import type { BacktestRequest, BacktestResult } from "../types";

export function useBacktest() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const submit = async (form: BacktestRequest): Promise<void> => {
    if (form.initial_cash <= 0 || form.universe.length === 0 || !form.strategy.trim()) return;

    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const summary = await backtestApi.submit(form);
      const poll = async (): Promise<void> => {
        if (!mountedRef.current) return;
        const s = await backtestApi.status(summary.task_id);
        if (!mountedRef.current) return;
        if (s.status === "running") {
          await new Promise((r) => setTimeout(r, 2000));
          return poll();
        }
        if (s.status === "completed") {
          const r = await backtestApi.result(summary.task_id);
          if (mountedRef.current) setResult(r);
        } else {
          if (mountedRef.current) setError("Backtest failed");
        }
      };
      await poll();
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : "Request failed");
      }
    } finally {
      if (mountedRef.current) setRunning(false);
    }
  };

  return { running, result, error, submit };
}
