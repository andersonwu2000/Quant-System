import { useState, useRef, useEffect } from "react";
import { backtestApi } from "../api";
import type { BacktestRequest, BacktestResult } from "@quant/shared";

export function useBacktest() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const submit = async (form: BacktestRequest): Promise<BacktestResult | null> => {
    if (form.initial_cash <= 0 || form.universe.length === 0 || !form.strategy.trim()) return null;

    setRunning(true);
    setError(null);
    setResult(null);
    setProgress(null);
    try {
      const summary = await backtestApi.submit(form);

      // Iterative polling with 30-minute timeout
      const MAX_POLL_MS = 30 * 60 * 1000;
      const pollStart = Date.now();
      let status = summary.status;
      while (status === "running" && mountedRef.current) {
        if (Date.now() - pollStart > MAX_POLL_MS) {
          setError("Backtest timed out (30 minutes)");
          return null;
        }
        await new Promise((r) => setTimeout(r, 2000));
        if (!mountedRef.current) break;
        const s = await backtestApi.status(summary.task_id);
        status = s.status;
        if (s.progress_current != null && s.progress_total != null) {
          setProgress({ current: s.progress_current, total: s.progress_total });
        }
      }

      if (!mountedRef.current) return null;

      if (status === "completed") {
        const r = await backtestApi.result(summary.task_id);
        if (mountedRef.current) setResult(r);
        return r;
      } else if (status === "failed") {
        if (mountedRef.current) setError("Backtest failed");
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : "Request failed");
      }
    } finally {
      if (mountedRef.current) {
        setRunning(false);
        setProgress(null);
      }
    }
    return null;
  };

  return { running, result, error, progress, submit };
}
